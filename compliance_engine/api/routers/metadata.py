"""
Metadata Router
================
Endpoints for countries, purposes, processes, and dropdown values.
"""

import logging
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


@router.get("/all-dropdown-values")
async def get_all_dropdown_values(db=Depends(get_db)):
    """Get all dropdown values in one call."""
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

    cache.set("all_dropdown_values", result, "metadata", ttl=600)
    return result
