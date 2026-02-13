"""
Metadata Router
================
Endpoints for countries, purposes, processes, legal entities, and dropdown values.
"""

import json
import logging
from pathlib import Path
from fastapi import APIRouter, Depends

from services.database import get_db_service
from services.cache import get_cache_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["metadata"])


def get_db():
    return get_db_service()


@router.get("/countries")
async def get_countries(db=Depends(get_db)):
    """Get list of all countries."""
    cache = get_cache_service()
    cached = cache.get("countries_list", "metadata")
    if cached:
        return cached

    try:
        query = "MATCH (c:Country) RETURN c.name as name ORDER BY c.name"
        result = db.execute_data_query(query)
        countries = [r.get('name') for r in result if r.get('name')]
    except Exception as e:
        logger.warning(f"Error fetching countries: {e}")
        countries = []

    cache.set("countries_list", countries, "metadata", ttl=600)
    return countries


@router.get("/purposes")
async def get_purposes(db=Depends(get_db)):
    """Get list of all purposes."""
    cache = get_cache_service()
    cached = cache.get("purposes_list", "metadata")
    if cached:
        return cached

    try:
        query = "MATCH (p:Purpose) RETURN p.name as name ORDER BY p.name"
        result = db.execute_data_query(query)
        purposes = [r.get('name') for r in result if r.get('name')]
    except Exception as e:
        logger.warning(f"Error fetching purposes: {e}")
        purposes = []

    cache.set("purposes_list", purposes, "metadata", ttl=600)
    return purposes


@router.get("/processes")
async def get_processes(db=Depends(get_db)):
    """Get list of all processes by level."""
    cache = get_cache_service()
    cached = cache.get("processes_list", "metadata")
    if cached:
        return cached

    processes = {"l1": [], "l2": [], "l3": []}

    for level in ["L1", "L2", "L3"]:
        try:
            query = f"MATCH (p:Process{level}) RETURN p.name as name ORDER BY p.name"
            result = db.execute_data_query(query)
            processes[level.lower()] = [r.get('name') for r in result if r.get('name')]
        except Exception as e:
            logger.warning(f"Error fetching processes {level}: {e}")
            processes[level.lower()] = []

    cache.set("processes_list", processes, "metadata", ttl=600)
    return processes


@router.get("/legal-entities")
async def get_legal_entities():
    """Get all legal entities with country mapping."""
    cache = get_cache_service()
    cached = cache.get("legal_entities", "metadata")
    if cached:
        return cached

    le_file = Path(__file__).parent.parent.parent / "rules" / "data_dictionaries" / "legal_entities.json"
    try:
        with open(le_file) as f:
            data = json.load(f)
        result = data.get("entities", {})
    except Exception as e:
        logger.warning(f"Error loading legal entities: {e}")
        result = {}

    cache.set("legal_entities", result, "metadata", ttl=600)
    return result


@router.get("/legal-entities/{country}")
async def get_legal_entities_for_country(country: str):
    """Get legal entities for a specific country."""
    le_file = Path(__file__).parent.parent.parent / "rules" / "data_dictionaries" / "legal_entities.json"
    try:
        with open(le_file) as f:
            data = json.load(f)
        entities = data.get("entities", {})
        # Case-insensitive lookup
        for key, value in entities.items():
            if key.lower() == country.lower():
                return value
        return []
    except Exception as e:
        logger.warning(f"Error loading legal entities for {country}: {e}")
        return []


@router.get("/purpose-of-processing")
async def get_purpose_of_processing():
    """Get the purpose of processing reference list."""
    pop_file = Path(__file__).parent.parent.parent / "rules" / "data_dictionaries" / "purpose_of_processing.json"
    try:
        with open(pop_file) as f:
            data = json.load(f)
        return data.get("purposes", [])
    except Exception as e:
        logger.warning(f"Error loading purpose of processing: {e}")
        return []


@router.get("/group-data-categories")
async def get_group_data_categories(db=Depends(get_db)):
    """Get group data categories from the rules graph."""
    cache = get_cache_service()
    cached = cache.get("group_data_categories", "metadata")
    if cached:
        return cached

    try:
        query = "MATCH (n:GDC) RETURN n.name as name, n.category as category ORDER BY n.category, n.name"
        result = db.execute_rules_query(query)
        categories = [{"name": r["name"], "category": r.get("category", "")} for r in result if r.get("name")]
    except Exception as e:
        logger.warning(f"Error fetching group data categories: {e}")
        categories = []

    cache.set("group_data_categories", categories, "metadata", ttl=600)
    return categories


@router.get("/all-dropdown-values")
async def get_all_dropdown_values(db=Depends(get_db)):
    """Get all dropdown values in one call including legal entities and purpose of processing."""
    cache = get_cache_service()
    cached = cache.get("all_dropdown_values", "metadata")
    if cached:
        return cached

    try:
        countries = await get_countries(db)
        purposes = await get_purposes(db)
        processes = await get_processes(db)

        result = {
            "countries": countries if countries else [],
            "purposes": purposes if purposes else [],
            "processes": processes if processes else {"l1": [], "l2": [], "l3": []}
        }
    except Exception as e:
        logger.warning(f"Error fetching dropdown values: {e}")
        result = {
            "countries": [],
            "purposes": [],
            "processes": {"l1": [], "l2": [], "l3": []}
        }

    # Fetch dictionary-based values from the rules graph
    for node_type, key in [("Process", "processes_dict"), ("Purpose", "purposes_dict"),
                            ("DataSubject", "data_subjects"), ("GDC", "gdc")]:
        try:
            query = f"MATCH (n:{node_type}) RETURN n.name as name, n.category as category ORDER BY n.category, n.name"
            raw = db.execute_rules_query(query)
            values = [{"name": r["name"], "category": r.get("category", "")} for r in raw if r.get("name")]
        except Exception:
            values = []
        result[key] = values

    # Legal entities
    try:
        legal_entities = await get_legal_entities()
        result["legal_entities"] = legal_entities
    except Exception:
        result["legal_entities"] = {}

    # Purpose of processing reference list
    try:
        pop = await get_purpose_of_processing()
        result["purpose_of_processing"] = pop
    except Exception:
        result["purpose_of_processing"] = []

    # Group data categories
    try:
        gdc = await get_group_data_categories(db)
        result["group_data_categories"] = gdc
    except Exception:
        result["group_data_categories"] = []

    cache.set("all_dropdown_values", result, "metadata", ttl=600)
    return result
