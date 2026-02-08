"""
Graph Data Router
==================
Endpoints for graph visualization data.
"""

import logging
from fastapi import APIRouter, Depends

from services.database import get_db_service
from services.cache import get_cache_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/graph", tags=["graph"])


def get_db():
    return get_db_service()


@router.get("/rules-network")
async def get_rules_network(db=Depends(get_db)):
    """
    Get rules network data for React Flow visualization.
    Returns countries, rules, and their relationships as nodes/edges.
    """
    cache = get_cache_service()
    cached = cache.get("rules_network", "metadata")
    if cached:
        return cached

    try:
        # Get all rules with their country group connections
        rules_query = """
        MATCH (r:Rule)
        OPTIONAL MATCH (r)-[:TRIGGERED_BY_ORIGIN]->(og:CountryGroup)
        OPTIONAL MATCH (r)-[:TRIGGERED_BY_RECEIVING]->(rg:CountryGroup)
        OPTIONAL MATCH (r)-[:HAS_PERMISSION]->(perm:Permission)
        OPTIONAL MATCH (r)-[:HAS_PROHIBITION]->(prohib:Prohibition)
        RETURN r.rule_id as rule_id,
               r.priority as priority,
               r.odrl_type as odrl_type,
               r.origin_match_type as origin_match_type,
               r.receiving_match_type as receiving_match_type,
               r.has_pii_required as has_pii_required,
               og.name as origin_group,
               rg.name as receiving_group,
               perm.name as permission_name,
               prohib.name as prohibition_name
        """
        rules_result = db.execute_rules_query(rules_query)

        # Get country groups with their countries
        groups_query = """
        MATCH (cg:CountryGroup)
        OPTIONAL MATCH (c:Country)-[:BELONGS_TO]->(cg)
        RETURN cg.name as group_name,
               collect(c.name) as countries
        """
        groups_result = db.execute_rules_query(groups_query)

        # Build nodes and edges
        nodes = []
        edges = []
        node_id_counter = 0

        # Add country group nodes as swimlane containers
        group_map = {}
        for group in groups_result:
            group_name = group.get('group_name', '')
            if group_name:
                node_id = f"group_{node_id_counter}"
                node_id_counter += 1
                group_map[group_name] = node_id
                nodes.append({
                    "id": node_id,
                    "type": "countryGroup",
                    "data": {
                        "label": group_name,
                        "countries": group.get('countries', []),
                        "country_count": len(group.get('countries', [])),
                    },
                    "position": {"x": 0, "y": 0},
                })

        # Add rule nodes
        for rule in rules_result:
            rule_id = rule.get('rule_id', '')
            if not rule_id:
                continue

            node_id = f"rule_{node_id_counter}"
            node_id_counter += 1
            odrl_type = rule.get('odrl_type', 'Permission')

            nodes.append({
                "id": node_id,
                "type": "ruleNode",
                "data": {
                    "rule_id": rule_id,
                    "priority": rule.get('priority', 0),
                    "odrl_type": odrl_type,
                    "has_pii_required": rule.get('has_pii_required', False),
                    "permission_name": rule.get('permission_name'),
                    "prohibition_name": rule.get('prohibition_name'),
                    "outcome": "prohibition" if odrl_type == "Prohibition" else "permission",
                },
                "position": {"x": 0, "y": 0},
            })

            # Add edges from origin group
            origin_group = rule.get('origin_group')
            if origin_group and origin_group in group_map:
                edges.append({
                    "id": f"edge_{len(edges)}",
                    "source": group_map[origin_group],
                    "target": node_id,
                    "type": "ruleEdge",
                    "data": {"relationship": "TRIGGERED_BY_ORIGIN"},
                })

            # Add edges to receiving group
            receiving_group = rule.get('receiving_group')
            if receiving_group and receiving_group in group_map:
                edges.append({
                    "id": f"edge_{len(edges)}",
                    "source": node_id,
                    "target": group_map[receiving_group],
                    "type": "ruleEdge",
                    "data": {"relationship": "TRIGGERED_BY_RECEIVING"},
                })

        result = {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "total_rules": len([n for n in nodes if n["type"] == "ruleNode"]),
                "total_groups": len([n for n in nodes if n["type"] == "countryGroup"]),
                "total_edges": len(edges),
            }
        }

        cache.set("rules_network", result, "metadata", ttl=300)
        return result

    except Exception as e:
        logger.error(f"Error fetching rules network: {e}")
        return {"nodes": [], "edges": [], "stats": {"total_rules": 0, "total_groups": 0, "total_edges": 0}}


@router.get("/country-groups")
async def get_country_groups(db=Depends(get_db)):
    """Get all country groups with their member countries."""
    cache = get_cache_service()
    cached = cache.get("country_groups", "metadata")
    if cached:
        return cached

    try:
        query = """
        MATCH (cg:CountryGroup)
        OPTIONAL MATCH (c:Country)-[:BELONGS_TO]->(cg)
        RETURN cg.name as group_name,
               collect(c.name) as countries
        ORDER BY cg.name
        """
        result = db.execute_rules_query(query)

        groups = {}
        for row in result:
            group_name = row.get('group_name', '')
            if group_name:
                groups[group_name] = row.get('countries', [])

        cache.set("country_groups", groups, "metadata", ttl=600)
        return groups

    except Exception as e:
        logger.error(f"Error fetching country groups: {e}")
        return {}
