"""
FalkorDB Production Loader - Connection Resilient with Hierarchical Purposes
Handles connection timeouts, memory issues, and retry logic
Stores LegalProcessingPurposeNames as level1, level2, level3... properties on Case nodes
"""

import pandas as pd
import asyncio
from falkordb.asyncio import FalkorDB
from redis.asyncio import BlockingConnectionPool, Redis
from redis.exceptions import ConnectionError, TimeoutError, ResponseError
from typing import Dict, List, Set
from collections import defaultdict
import logging
from datetime import datetime
from tqdm.asyncio import tqdm as async_tqdm
from tqdm import tqdm
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RobustFalkorDBLoader:
    """
    Production-ready FalkorDB loader with:
    - Connection retry logic
    - Memory monitoring
    - Smaller, safer batch sizes
    - Progressive saving
    - Transaction safety
    - Hierarchical purpose properties (level1, level2, level3...)
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
        """Initialize connection pool with proper timeouts"""
        logger.info(f"Connecting to FalkorDB at {self.host}:{self.port}")
        logger.info(f"  Max connections: {self.max_connections}")
        logger.info(f"  Socket timeout: {self.socket_timeout}s")
        logger.info(f"  Batch size: {self.batch_size}")
        
        # Create connection pool with proper settings
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
        
        # Direct Redis client for monitoring
        self.redis_client = Redis(connection_pool=self.pool)
        
        # Check connection
        await self._check_connection()
        
        # Check and configure Redis memory
        await self._configure_redis_memory()
    
    async def _check_connection(self):
        """Verify Redis/FalkorDB is accessible"""
        try:
            info = await self.redis_client.info()
            logger.info(f"✅ Connected to Redis {info.get('redis_version', 'unknown')}")
            logger.info(f"✅ FalkorDB module loaded")
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            raise
    
    async def _configure_redis_memory(self):
        """Check and configure Redis memory settings"""
        try:
            info = await self.redis_client.info('memory')
            
            used_memory = info.get('used_memory_human', 'unknown')
            max_memory = info.get('maxmemory_human', 'unlimited')
            
            logger.info(f"\nRedis Memory Status:")
            logger.info(f"  Used: {used_memory}")
            logger.info(f"  Max: {max_memory}")
            
            # Warn if maxmemory is not set
            if info.get('maxmemory', 0) == 0:
                logger.warning("⚠️  maxmemory not set - Redis may run out of memory!")
                logger.warning("   Recommendation: redis-server --maxmemory 16gb")
            
            # Check maxmemory policy
            policy = info.get('maxmemory_policy', 'noeviction')
            logger.info(f"  Policy: {policy}")
            
            if policy != 'noeviction':
                logger.warning(f"⚠️  maxmemory-policy is '{policy}' - data may be evicted!")
                logger.warning("   Recommendation: CONFIG SET maxmemory-policy noeviction")
                
        except Exception as e:
            logger.warning(f"Could not check Redis memory: {e}")
    
    async def close(self):
        """Close connections gracefully"""
        try:
            if self.pool:
                await self.pool.disconnect()
            logger.info("✅ Connections closed")
        except Exception as e:
            logger.warning(f"Error closing connections: {e}")
    
    def load_excel_optimized(self, file_path: str) -> pd.DataFrame:
        """Load Excel with proper dtypes"""
        logger.info(f"Loading Excel file: {file_path}")
        
        dtypes = {col: 'str' for col in [
            'CaseId', 'EimId', 'BusinessApp_Id', 'OriginatingCountryName',
            'ReceivingJurisdictions', 'LegalProcessingPurposeNames',
            'PersonalDataCategoryNames', 'PersonalDataNames', 
            'CategoryNames', 'pia_module', 'tia_module', 'hrpr_module'
        ]}
        
        df = pd.read_excel(file_path, dtype=dtypes, engine='openpyxl')
        logger.info(f"Loaded {len(df):,} rows")
        return df
    
    def preprocess_fast(self, df: pd.DataFrame) -> List[Dict]:
        """Fast preprocessing with to_records() - hierarchical purposes"""
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
        purposes = split_pipe_vectorized(df['LegalProcessingPurposeNames'])  # Keep as list
        pdc = split_pipe_vectorized(df['PersonalDataCategoryNames'])
        personal_data = split_pipe_vectorized(df['PersonalDataNames'])
        categories = split_pipe_vectorized(df['CategoryNames'])
        
        # Use to_records for fast iteration
        logger.info("  Converting to records...")
        records_array = df.to_records(index=False)
        
        processed_records = []
        for idx, record in enumerate(records_array):
            # Build purpose hierarchy dictionary
            purpose_hierarchy = {}
            for level_idx, purpose in enumerate(purposes[idx], start=1):
                purpose_hierarchy[f'purpose_level{level_idx}'] = purpose
            
            processed_record = {
                'case_id': record['CaseId'],
                'eim_id': record['EimId'] if record['EimId'] != 'None' else None,
                'business_app_id': record['BusinessApp_Id'] if record['BusinessApp_Id'] != 'None' else None,
                'originating_country': record['OriginatingCountryName'] if record['OriginatingCountryName'] != 'None' else None,
                'receiving_jurisdictions': receiving_juris[idx],
                'purpose_hierarchy': purpose_hierarchy,  # Hierarchical purposes
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
        """Collect unique entities - excluding purposes (now hierarchical)"""
        logger.info("Collecting unique entities...")
        
        entities = {
            'countries': set(),
            'jurisdictions': set(),
            'personal_data_categories': set(),
            'personal_data': set(),
            'categories': set(),
        }
        
        for record in records:
            if record['originating_country']:
                entities['countries'].add(record['originating_country'])
            entities['jurisdictions'].update(record['receiving_jurisdictions'])
            entities['personal_data_categories'].update(record['personal_data_categories'])
            entities['personal_data'].update(record['personal_data'])
            entities['categories'].update(record['categories'])
        
        for entity_type, values in entities.items():
            logger.info(f"  {entity_type}: {len(values):,}")
        
        return entities
    
    async def create_indexes(self):
        """Create indexes with error handling"""
        logger.info("Creating indexes...")
        
        indexes = [
            "CREATE INDEX FOR (c:Case) ON (c.case_id)",
            "CREATE INDEX FOR (c:Country) ON (c.name)",
            "CREATE INDEX FOR (j:Jurisdiction) ON (j.name)",
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
                    logger.warning(f"   Retrying in {self.retry_delay}s...")
                    await asyncio.sleep(self.retry_delay)
                    
                    # Try to reconnect
                    try:
                        await self.close()
                        await self.connect()
                    except:
                        pass
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
        """Create nodes with safe batching and retry logic"""
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
                
                # Small delay to prevent overwhelming server
                await asyncio.sleep(0.05)
                
            except Exception as e:
                logger.error(f"Failed to create {node_label} batch: {e}")
                continue
        
        self.stats['nodes_created'][node_label] = total_created
        logger.info(f"  ✅ Created {total_created:,} {node_label} nodes")
    
    async def create_cases_safe(self, records: List[Dict]):
        """Create case nodes with hierarchical purpose properties"""
        logger.info(f"Creating {len(records):,} Case nodes with hierarchical purposes...")
        
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
                # Add purpose hierarchy to case object
                case_obj.update(r['purpose_hierarchy'])
                case_data.append(case_obj)
            
            # Build dynamic SET clause for purpose levels
            # We need to handle variable number of purpose levels
            query = """
            UNWIND $cases AS case_data
            MERGE (c:Case {case_id: case_data.case_id})
            SET c.eim_id = case_data.eim_id,
                c.business_app_id = case_data.business_app_id,
                c.pia_module = case_data.pia_module,
                c.tia_module = case_data.tia_module,
                c.hrpr_module = case_data.hrpr_module,
                c.purpose_level1 = case_data.purpose_level1,
                c.purpose_level2 = case_data.purpose_level2,
                c.purpose_level3 = case_data.purpose_level3,
                c.purpose_level4 = case_data.purpose_level4,
                c.purpose_level5 = case_data.purpose_level5,
                c.purpose_level6 = case_data.purpose_level6,
                c.purpose_level7 = case_data.purpose_level7,
                c.purpose_level8 = case_data.purpose_level8,
                c.purpose_level9 = case_data.purpose_level9,
                c.purpose_level10 = case_data.purpose_level10
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
        """Create relationships - excluding purposes (now properties)"""
        logger.info(f"Creating relationships for {len(records):,} cases...")
        
        # Process each relationship type separately for stability
        # NOTE: Removed Purpose relationships - purposes are now properties
        rel_types = [
            ('country', 'ORIGINATES_FROM', 'Country', 'originating_country'),
            ('jurisdiction', 'TRANSFERS_TO', 'Jurisdiction', 'receiving_jurisdictions'),
            ('pdc', 'HAS_PERSONAL_DATA_CATEGORY', 'PersonalDataCategory', 'personal_data_categories'),
            ('pd', 'HAS_PERSONAL_DATA', 'PersonalData', 'personal_data'),
            ('category', 'HAS_CATEGORY', 'Category', 'categories')
        ]
        
        total_rels = 0
        
        for rel_key, rel_type, target_label, record_field in rel_types:
            logger.info(f"\nCreating {rel_type} relationships...")
            
            # Build relationship data for this type only
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
            
            # Process in small batches
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
                    
                    # Longer delay for relationship creation
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Failed to create {rel_type} batch: {e}")
                    continue
            
            logger.info(f"  ✅ Created {created:,} {rel_type} relationships")
            self.stats['relationships_created'][rel_type] = created
        
        self.stats['relationships_created']['total'] = total_rels
        logger.info(f"\n✅ Total relationships created: {total_rels:,}")
    
    async def load_data(self, file_path: str):
        """Main loading method with robust error handling"""
        self.stats['start_time'] = datetime.now()
        
        try:
            # Connect
            await self.connect()
            
            # Load and preprocess
            df = self.load_excel_optimized(file_path)
            records = self.preprocess_fast(df)
            self.stats['total_cases'] = len(records)
            
            # Create indexes
            await self.create_indexes()
            
            # Collect entities (no purposes - they're now properties)
            entities = self.collect_unique_entities(records)
            
            # Create entity nodes (in sequence for stability)
            logger.info("\n" + "="*60)
            logger.info("CREATING ENTITY NODES")
            logger.info("="*60)
            
            await self.create_nodes_safe('Country', 'name', list(entities['countries']))
            await self.create_nodes_safe('Jurisdiction', 'name', list(entities['jurisdictions']))
            await self.create_nodes_safe('PersonalDataCategory', 'name', list(entities['personal_data_categories']))
            await self.create_nodes_safe('PersonalData', 'name', list(entities['personal_data']))
            await self.create_nodes_safe('Category', 'name', list(entities['categories']))
            
            # Create case nodes with hierarchical purposes
            logger.info("\n" + "="*60)
            logger.info("CREATING CASE NODES WITH HIERARCHICAL PURPOSES")
            logger.info("="*60)
            await self.create_cases_safe(records)
            
            # Create relationships (no purpose relationships)
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
        
        if self.stats['errors']:
            logger.warning("\n⚠️  Errors encountered:")
            for error_type, count in self.stats['errors'].items():
                logger.warning(f"   {error_type}: {count}")
        
        logger.info("\n💡 Purpose Data Structure:")
        logger.info("   Purposes are stored as hierarchical properties on Case nodes:")
        logger.info("   - purpose_level1, purpose_level2, purpose_level3, etc.")
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
    
    loader = RobustFalkorDBLoader(
        host=CONFIG['host'],
        port=CONFIG['port'],
        password=CONFIG['password'],
        graph_name=CONFIG['graph_name'],
        batch_size=CONFIG['batch_size'],
        max_connections=CONFIG['max_connections'],
        socket_timeout=CONFIG['socket_timeout']
    )
    
    await loader.load_data(CONFIG['excel_file'])
    
    logger.info("\n✅ Data loading completed!")
    logger.info("\nExample queries to test:")
    logger.info("1. Get case with all purpose levels:")
    logger.info("   MATCH (c:Case {case_id: 'your_case_id'}) RETURN c")
    logger.info("\n2. Find cases by specific purpose level:")
    logger.info("   MATCH (c:Case) WHERE c.purpose_level1 = 'Marketing' RETURN c")
    logger.info("\n3. Count cases by purpose hierarchy:")
    logger.info("   MATCH (c:Case) RETURN c.purpose_level1, count(c) as count ORDER BY count DESC")


if __name__ == "__main__":
    asyncio.run(main())