#!/usr/bin/env python3
"""
FalkorDB Enhanced Loader - With Purpose and Process Nodes
- Purposes as separate nodes (not properties)
- Process hierarchy from Processes_L1_L2_L3 column
- Multiple relationships from Case to Purpose/Process nodes
"""

import pandas as pd
import asyncio
from falkordb.asyncio import FalkorDB
from redis.asyncio import BlockingConnectionPool
from redis.exceptions import ConnectionError, TimeoutError, ResponseError
from typing import Dict, List, Set
from collections import defaultdict
import logging
from datetime import datetime
from tqdm.asyncio import tqdm as async_tqdm
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EnhancedFalkorDBLoader:
    """
    Enhanced loader with:
    - Purpose nodes (not properties)
    - Process hierarchy (L1-L2-L3)
    - Multiple edges for purposes and processes
    """

    def __init__(
        self,
        host: str = 'localhost',
        port: int = 6379,
        password: str = None,
        graph_name: str = 'DataTransferGraph',
        batch_size: int = 1000,
        max_connections: int = 8,
        socket_timeout: int = 300,
        socket_connect_timeout: int = 30,
        retry_attempts: int = 3,
        retry_delay: int = 2
    ):
        self.host = host
        self.port = port
        self.password = password
        self.graph_name = graph_name
        self.batch_size = batch_size
        self.max_connections = max_connections
        self.socket_timeout = socket_timeout
        self.socket_connect_timeout = socket_connect_timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay

        self.pool = None
        self.db = None
        self.graph = None
        self.redis_client = None

        self.stats = {
            'total_cases': 0,
            'nodes_created': defaultdict(int),
            'relationships_created': defaultdict(int),
            'errors': defaultdict(int),
            'retries': 0,
            'start_time': None,
            'end_time': None
        }

    async def connect(self):
        """Initialize connection pool"""
        logger.info(f"Connecting to FalkorDB at {self.host}:{self.port}")

        self.pool = BlockingConnectionPool(
            host=self.host,
            port=self.port,
            password=self.password,
            max_connections=self.max_connections,
            timeout=self.socket_timeout,
            socket_timeout=self.socket_timeout,
            socket_connect_timeout=self.socket_connect_timeout,
            decode_responses=True,
            health_check_interval=30,
            retry_on_timeout=True
        )

        self.db = FalkorDB(connection_pool=self.pool)
        self.graph = self.db.select_graph(self.graph_name)

        logger.info(f"✅ Connected to FalkorDB")

    async def close(self):
        """Close connections"""
        try:
            if self.pool:
                await self.pool.disconnect()
            logger.info("✅ Connections closed")
        except Exception as e:
            logger.warning(f"Error closing connections: {e}")

    def load_excel_optimized(self, file_path: str) -> pd.DataFrame:
        """Load Excel with proper dtypes including new Processes column"""
        logger.info(f"Loading Excel file: {file_path}")

        dtypes = {col: 'str' for col in [
            'CaseId', 'EimId', 'BusinessApp_Id', 'OriginatingCountryName',
            'ReceivingJurisdictions', 'LegalProcessingPurposeNames',
            'Processes_L1_L2_L3',  # NEW COLUMN
            'PersonalDataCategoryNames', 'PersonalDataNames',
            'CategoryNames', 'pia_module', 'tia_module', 'hrpr_module'
        ]}

        df = pd.read_excel(file_path, dtype=dtypes, engine='openpyxl')
        logger.info(f"Loaded {len(df):,} rows")
        return df

    def parse_process_hierarchy(self, process_string: str) -> Dict:
        """
        Parse Processes_L1_L2_L3 column
        Format: "L1-L2-L3" or "L1-L2" or "L1"
        Example: "Back Office-HR-Payroll"
        """
        if not process_string or process_string == 'None' or not process_string.strip():
            return {'l1': None, 'l2': None, 'l3': None}

        parts = [p.strip() for p in process_string.split('-') if p.strip()]

        return {
            'l1': parts[0] if len(parts) > 0 else None,
            'l2': parts[1] if len(parts) > 1 else None,
            'l3': parts[2] if len(parts) > 2 else None
        }

    def preprocess_fast(self, df: pd.DataFrame) -> List[Dict]:
        """Fast preprocessing with Purpose and Process nodes"""
        logger.info(f"Preprocessing {len(df):,} records...")
        start_time = datetime.now()

        # Convert to string and handle nulls
        df = df.astype(str).replace('nan', None)

        # Vectorized splitting function
        def split_pipe_vectorized(series):
            series = series.fillna('')
            split_series = series.str.split('|')
            result = []
            for values in split_series:
                if values and values != ['']:
                    cleaned = []
                    seen = set()
                    for v in values:
                        v_stripped = v.strip()
                        if v_stripped and v_stripped not in seen:
                            seen.add(v_stripped)
                            cleaned.append(v_stripped)
                    result.append(cleaned)
                else:
                    result.append([])
            return result

        logger.info("  Splitting pipe-delimited values...")
        receiving_juris = split_pipe_vectorized(df['ReceivingJurisdictions'])
        purposes = split_pipe_vectorized(df['LegalProcessingPurposeNames'])  # Now as list of purposes
        pdc = split_pipe_vectorized(df['PersonalDataCategoryNames'])
        personal_data = split_pipe_vectorized(df['PersonalDataNames'])
        categories = split_pipe_vectorized(df['CategoryNames'])

        # Parse processes
        logger.info("  Parsing process hierarchies...")
        processes = []
        if 'Processes_L1_L2_L3' in df.columns:
            for proc_str in df['Processes_L1_L2_L3']:
                processes.append(self.parse_process_hierarchy(proc_str))
        else:
            processes = [{'l1': None, 'l2': None, 'l3': None} for _ in range(len(df))]

        # Use to_records for fast iteration
        logger.info("  Converting to records...")
        records_array = df.to_records(index=False)

        processed_records = []
        for idx, record in enumerate(records_array):
            processed_record = {
                'case_id': record['CaseId'],
                'eim_id': record['EimId'] if record['EimId'] != 'None' else None,
                'business_app_id': record['BusinessApp_Id'] if record['BusinessApp_Id'] != 'None' else None,
                'originating_country': record['OriginatingCountryName'] if record['OriginatingCountryName'] != 'None' else None,
                'receiving_jurisdictions': receiving_juris[idx],
                'purposes': purposes[idx],  # List of purpose names
                'process_hierarchy': processes[idx],  # {l1, l2, l3}
                'personal_data_categories': pdc[idx],
                'personal_data': personal_data[idx],
                'categories': categories[idx],
                'pia_module': record['pia_module'] if record['pia_module'] != 'None' else None,
                'tia_module': record['tia_module'] if record['tia_module'] != 'None' else None,
                'hrpr_module': record['hrpr_module'] if record['hrpr_module'] != 'None' else None,
            }
            processed_records.append(processed_record)

        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Preprocessed {len(processed_records):,} records in {duration:.2f}s")

        return processed_records

    def collect_unique_entities(self, records: List[Dict]) -> Dict[str, Set]:
        """Collect unique entities including purposes and processes"""
        logger.info("Collecting unique entities...")

        entities = {
            'countries': set(),
            'jurisdictions': set(),
            'purposes': set(),  # NEW: Purpose nodes
            'process_l1': set(),  # NEW: Process L1 nodes
            'process_l2': set(),  # NEW: Process L2 nodes
            'process_l3': set(),  # NEW: Process L3 nodes
            'personal_data_categories': set(),
            'personal_data': set(),
            'categories': set(),
        }

        for record in records:
            if record['originating_country']:
                entities['countries'].add(record['originating_country'])
            entities['jurisdictions'].update(record['receiving_jurisdictions'])
            entities['purposes'].update(record['purposes'])  # Add all purposes

            # Add process hierarchy
            if record['process_hierarchy']['l1']:
                entities['process_l1'].add(record['process_hierarchy']['l1'])
            if record['process_hierarchy']['l2']:
                entities['process_l2'].add(record['process_hierarchy']['l2'])
            if record['process_hierarchy']['l3']:
                entities['process_l3'].add(record['process_hierarchy']['l3'])

            entities['personal_data_categories'].update(record['personal_data_categories'])
            entities['personal_data'].update(record['personal_data'])
            entities['categories'].update(record['categories'])

        for entity_type, values in entities.items():
            logger.info(f"  {entity_type}: {len(values):,}")

        return entities

    async def create_indexes(self):
        """Create indexes"""
        logger.info("Creating indexes...")

        indexes = [
            "CREATE INDEX FOR (c:Case) ON (c.case_id)",
            "CREATE INDEX FOR (c:Country) ON (c.name)",
            "CREATE INDEX FOR (j:Jurisdiction) ON (j.name)",
            "CREATE INDEX FOR (p:Purpose) ON (p.name)",  # NEW
            "CREATE INDEX FOR (p1:ProcessL1) ON (p1.name)",  # NEW
            "CREATE INDEX FOR (p2:ProcessL2) ON (p2.name)",  # NEW
            "CREATE INDEX FOR (p3:ProcessL3) ON (p3.name)",  # NEW
            "CREATE INDEX FOR (pdc:PersonalDataCategory) ON (pdc.name)",
            "CREATE INDEX FOR (pd:PersonalData) ON (pd.name)",
            "CREATE INDEX FOR (cat:Category) ON (cat.name)",
        ]

        for idx_query in indexes:
            try:
                await self.graph.query(idx_query)
                logger.info(f"  ✅ {idx_query}")
            except Exception as e:
                logger.debug(f"  Index exists or error: {e}")

    async def execute_with_retry(self, query: str, params: dict, operation_name: str):
        """Execute query with retry logic"""
        for attempt in range(self.retry_attempts):
            try:
                result = await self.graph.query(query, params=params)
                return result
            except (ConnectionError, TimeoutError) as e:
                self.stats['retries'] += 1
                if attempt < self.retry_attempts - 1:
                    logger.warning(f"⚠️  {operation_name} failed (attempt {attempt + 1}/{self.retry_attempts}): {e}")
                    await asyncio.sleep(self.retry_delay)
                else:
                    logger.error(f"❌ {operation_name} failed after {self.retry_attempts} attempts")
                    self.stats['errors'][operation_name] += 1
                    raise
            except ResponseError as e:
                logger.error(f"❌ Query error in {operation_name}: {e}")
                self.stats['errors'][operation_name] += 1
                raise
            except Exception as e:
                logger.error(f"❌ Unexpected error in {operation_name}: {e}")
                self.stats['errors'][operation_name] += 1
                raise

    async def create_nodes_safe(self, node_label: str, property_name: str, values: List[str]):
        """Create nodes with safe batching"""
        if not values:
            return

        logger.info(f"Creating {len(values):,} {node_label} nodes...")

        total_created = 0
        for i in tqdm(range(0, len(values), self.batch_size), desc=f"Creating {node_label}"):
            batch = values[i:i + self.batch_size]

            query = f"""
            UNWIND $values AS value
            MERGE (n:{node_label} {{{property_name}: value}})
            RETURN count(n) as count
            """

            try:
                result = await self.execute_with_retry(
                    query,
                    {'values': batch},
                    f"Create {node_label} batch"
                )
                count = result.result_set[0][0] if result.result_set else 0
                total_created += count
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.error(f"Failed to create {node_label} batch: {e}")
                continue

        self.stats['nodes_created'][node_label] = total_created
        logger.info(f"  ✅ Created {total_created:,} {node_label} nodes")

    async def create_cases_safe(self, records: List[Dict]):
        """Create case nodes WITHOUT purpose/process properties"""
        logger.info(f"Creating {len(records):,} Case nodes...")

        total_created = 0
        for i in tqdm(range(0, len(records), self.batch_size), desc="Creating Cases"):
            batch = records[i:i + self.batch_size]

            case_data = []
            for r in batch:
                case_obj = {
                    'case_id': r['case_id'],
                    'eim_id': r['eim_id'],
                    'business_app_id': r['business_app_id'],
                    'pia_module': r['pia_module'],
                    'tia_module': r['tia_module'],
                    'hrpr_module': r['hrpr_module']
                }
                case_data.append(case_obj)

            query = """
            UNWIND $cases AS case_data
            MERGE (c:Case {case_id: case_data.case_id})
            SET c.eim_id = case_data.eim_id,
                c.business_app_id = case_data.business_app_id,
                c.pia_module = case_data.pia_module,
                c.tia_module = case_data.tia_module,
                c.hrpr_module = case_data.hrpr_module
            RETURN count(c) as count
            """

            try:
                result = await self.execute_with_retry(
                    query,
                    {'cases': case_data},
                    f"Create Cases batch"
                )
                count = result.result_set[0][0] if result.result_set else 0
                total_created += count
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.error(f"Failed to create Cases batch: {e}")
                continue

        self.stats['nodes_created']['Case'] = total_created
        logger.info(f"  ✅ Created {total_created:,} Case nodes")

    async def create_relationships_safe(self, records: List[Dict]):
        """Create relationships including Purpose and Process edges"""
        logger.info(f"Creating relationships for {len(records):,} cases...")

        rel_types = [
            ('country', 'ORIGINATES_FROM', 'Country', 'originating_country'),
            ('jurisdiction', 'TRANSFERS_TO', 'Jurisdiction', 'receiving_jurisdictions'),
            ('purpose', 'HAS_PURPOSE', 'Purpose', 'purposes'),  # NEW
            ('pdc', 'HAS_PERSONAL_DATA_CATEGORY', 'PersonalDataCategory', 'personal_data_categories'),
            ('pd', 'HAS_PERSONAL_DATA', 'PersonalData', 'personal_data'),
            ('category', 'HAS_CATEGORY', 'Category', 'categories')
        ]

        total_rels = 0

        for rel_key, rel_type, target_label, record_field in rel_types:
            logger.info(f"\nCreating {rel_type} relationships...")

            rel_data = []
            for record in records:
                case_id = record['case_id']

                if record_field in ['originating_country']:
                    if record[record_field]:
                        rel_data.append({
                            'case_id': case_id,
                            'value': record[record_field]
                        })
                else:
                    for value in record[record_field]:
                        rel_data.append({
                            'case_id': case_id,
                            'value': value
                        })

            if not rel_data:
                continue

            batch_size = min(self.batch_size, 500)
            created = 0

            for i in tqdm(range(0, len(rel_data), batch_size), desc=f"  {rel_type}"):
                batch = rel_data[i:i + batch_size]

                query = f"""
                UNWIND $rels AS rel
                MATCH (c:Case {{case_id: rel.case_id}})
                MATCH (t:{target_label} {{name: rel.value}})
                MERGE (c)-[:{rel_type}]->(t)
                RETURN count(*) as cnt
                """

                try:
                    result = await self.execute_with_retry(
                        query,
                        {'rels': batch},
                        f"Create {rel_type}"
                    )
                    count = result.result_set[0][0] if result.result_set else 0
                    created += count
                    total_rels += count
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error(f"Failed to create {rel_type} batch: {e}")
                    continue

            logger.info(f"  ✅ Created {created:,} {rel_type} relationships")
            self.stats['relationships_created'][rel_type] = created

        # Create Process hierarchy relationships
        await self.create_process_relationships(records)

        self.stats['relationships_created']['total'] = total_rels
        logger.info(f"\n✅ Total relationships created: {total_rels:,}")

    async def create_process_relationships(self, records: List[Dict]):
        """Create Process L1/L2/L3 relationships"""
        logger.info("\nCreating Process hierarchy relationships...")

        # Process L1 relationships
        process_l1_data = []
        process_l2_data = []
        process_l3_data = []

        for record in records:
            case_id = record['case_id']
            proc = record['process_hierarchy']

            if proc['l1']:
                process_l1_data.append({'case_id': case_id, 'value': proc['l1']})
            if proc['l2']:
                process_l2_data.append({'case_id': case_id, 'value': proc['l2']})
            if proc['l3']:
                process_l3_data.append({'case_id': case_id, 'value': proc['l3']})

        # Create L1 relationships
        if process_l1_data:
            logger.info(f"  Creating {len(process_l1_data)} ProcessL1 relationships...")
            for i in tqdm(range(0, len(process_l1_data), 500), desc="  HAS_PROCESS_L1"):
                batch = process_l1_data[i:i+500]
                query = """
                UNWIND $rels AS rel
                MATCH (c:Case {case_id: rel.case_id})
                MATCH (p:ProcessL1 {name: rel.value})
                MERGE (c)-[:HAS_PROCESS_L1]->(p)
                """
                try:
                    await self.execute_with_retry(query, {'rels': batch}, "Create ProcessL1")
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error(f"Failed ProcessL1 batch: {e}")

        # Create L2 relationships
        if process_l2_data:
            logger.info(f"  Creating {len(process_l2_data)} ProcessL2 relationships...")
            for i in tqdm(range(0, len(process_l2_data), 500), desc="  HAS_PROCESS_L2"):
                batch = process_l2_data[i:i+500]
                query = """
                UNWIND $rels AS rel
                MATCH (c:Case {case_id: rel.case_id})
                MATCH (p:ProcessL2 {name: rel.value})
                MERGE (c)-[:HAS_PROCESS_L2]->(p)
                """
                try:
                    await self.execute_with_retry(query, {'rels': batch}, "Create ProcessL2")
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error(f"Failed ProcessL2 batch: {e}")

        # Create L3 relationships
        if process_l3_data:
            logger.info(f"  Creating {len(process_l3_data)} ProcessL3 relationships...")
            for i in tqdm(range(0, len(process_l3_data), 500), desc="  HAS_PROCESS_L3"):
                batch = process_l3_data[i:i+500]
                query = """
                UNWIND $rels AS rel
                MATCH (c:Case {case_id: rel.case_id})
                MATCH (p:ProcessL3 {name: rel.value})
                MERGE (c)-[:HAS_PROCESS_L3]->(p)
                """
                try:
                    await self.execute_with_retry(query, {'rels': batch}, "Create ProcessL3")
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error(f"Failed ProcessL3 batch: {e}")

    async def load_data(self, file_path: str):
        """Main loading method"""
        self.stats['start_time'] = datetime.now()

        try:
            await self.connect()

            df = self.load_excel_optimized(file_path)
            records = self.preprocess_fast(df)
            self.stats['total_cases'] = len(records)

            await self.create_indexes()

            entities = self.collect_unique_entities(records)

            logger.info("\n" + "="*60)
            logger.info("CREATING ENTITY NODES")
            logger.info("="*60)

            await self.create_nodes_safe('Country', 'name', list(entities['countries']))
            await self.create_nodes_safe('Jurisdiction', 'name', list(entities['jurisdictions']))
            await self.create_nodes_safe('Purpose', 'name', list(entities['purposes']))  # NEW
            await self.create_nodes_safe('ProcessL1', 'name', list(entities['process_l1']))  # NEW
            await self.create_nodes_safe('ProcessL2', 'name', list(entities['process_l2']))  # NEW
            await self.create_nodes_safe('ProcessL3', 'name', list(entities['process_l3']))  # NEW
            await self.create_nodes_safe('PersonalDataCategory', 'name', list(entities['personal_data_categories']))
            await self.create_nodes_safe('PersonalData', 'name', list(entities['personal_data']))
            await self.create_nodes_safe('Category', 'name', list(entities['categories']))

            logger.info("\n" + "="*60)
            logger.info("CREATING CASE NODES")
            logger.info("="*60)
            await self.create_cases_safe(records)

            logger.info("\n" + "="*60)
            logger.info("CREATING RELATIONSHIPS")
            logger.info("="*60)
            await self.create_relationships_safe(records)

            self.stats['end_time'] = datetime.now()
            self.print_statistics()

        except Exception as e:
            logger.error(f"\n❌ FATAL ERROR: {e}")
            raise
        finally:
            await self.close()

    def print_statistics(self):
        """Print comprehensive statistics"""
        duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()

        logger.info("\n" + "="*70)
        logger.info("LOADING COMPLETE - STATISTICS")
        logger.info("="*70)
        logger.info(f"\n✅ Successfully processed {self.stats['total_cases']:,} cases")
        logger.info(f"⏱️  Total time: {duration:.2f}s ({duration/60:.1f} minutes)")
        logger.info(f"🔄 Retries: {self.stats['retries']}")

        logger.info("\n📊 Nodes created:")
        for node_type, count in sorted(self.stats['nodes_created'].items()):
            logger.info(f"   {node_type}: {count:,}")

        logger.info(f"\n🔗 Relationships created:")
        for rel_type, count in sorted(self.stats['relationships_created'].items()):
            logger.info(f"   {rel_type}: {count:,}")

        logger.info("\n💡 New Data Structure:")
        logger.info("   - Purposes: Separate nodes with HAS_PURPOSE edges")
        logger.info("   - Processes: Hierarchical L1/L2/L3 nodes")
        logger.info("   - Cases can have multiple purposes and processes")
        logger.info("="*70)


async def main():
    """Main execution"""
    CONFIG = {
        'host': 'localhost',
        'port': 6379,
        'password': None,
        'graph_name': 'DataTransferGraph',
        'batch_size': 1000,
        'max_connections': 8,
        'socket_timeout': 300,
        'excel_file': 'sample_data_comprehensive.xlsx'  # Update this path
    }

    loader = EnhancedFalkorDBLoader(
        host=CONFIG['host'],
        port=CONFIG['port'],
        password=CONFIG['password'],
        graph_name=CONFIG['graph_name'],
        batch_size=CONFIG['batch_size'],
        max_connections=CONFIG['max_connections'],
        socket_timeout=CONFIG['socket_timeout']
    )

    await loader.load_data(CONFIG['excel_file'])

    logger.info("\n✅ Enhanced data loading completed!")
    logger.info("\nNew structure:")
    logger.info("  - Purpose nodes (not properties)")
    logger.info("  - Process L1/L2/L3 hierarchy")
    logger.info("  - Multiple edges per case")


if __name__ == "__main__":
    asyncio.run(main())
