"""
Evaluation Router
==================
Endpoints for rule evaluation and case search.
"""

import logging
import time
from fastapi import APIRouter, HTTPException, Depends

from models.schemas import (
    RulesEvaluationRequest,
    RulesEvaluationResponse,
    SearchCasesRequest,
    SearchCasesResponse,
    CaseMatch,
)
from services.database import get_db_service
from services.rules_evaluator import get_rules_evaluator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["evaluation"])


def get_db():
    return get_db_service()


def get_evaluator():
    return get_rules_evaluator()


@router.post("/evaluate-rules", response_model=RulesEvaluationResponse)
async def evaluate_rules(
    request: RulesEvaluationRequest,
    evaluator=Depends(get_evaluator),
):
    """Evaluate compliance rules for a data transfer."""
    try:
        result = evaluator.evaluate(
            origin_country=request.origin_country,
            receiving_country=request.receiving_country,
            pii=request.pii,
            purposes=request.purposes,
            process_l1=request.process_l1,
            process_l2=request.process_l2,
            process_l3=request.process_l3,
            personal_data_names=request.personal_data_names,
            metadata=request.metadata,
        )
        return result

    except Exception as e:
        logger.error(f"Error evaluating rules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search-cases", response_model=SearchCasesResponse)
async def search_cases(
    request: SearchCasesRequest,
    db=Depends(get_db),
):
    """Search for historical precedent cases."""
    start_time = time.time()

    try:
        match_parts = ["MATCH (c:Case)"]
        where_conditions = ["c.case_status IN ['Completed', 'Complete', 'Active', 'Published']"]
        params = {}

        if request.origin_country:
            match_parts.append(
                "MATCH (c)-[:ORIGINATES_FROM]->(origin:Country {name: $origin_country})"
            )
            params["origin_country"] = request.origin_country
        if request.receiving_country:
            match_parts.append(
                "MATCH (c)-[:TRANSFERS_TO]->(receiving:Jurisdiction {name: $receiving_country})"
            )
            params["receiving_country"] = request.receiving_country
        if request.purposes:
            match_parts.append(
                "MATCH (c)-[:HAS_PURPOSE]->(p:Purpose)"
            )
            where_conditions.append("p.name IN $purposes")
            params["purposes"] = request.purposes
        if request.pii is not None:
            where_conditions.append("c.pii = $pii")
            params["pii"] = request.pii

        base_query = "\n".join(match_parts)
        if where_conditions:
            base_query += "\nWHERE " + " AND ".join(where_conditions)

        count_query = base_query + "\nRETURN count(c) as total"
        count_result = db.execute_data_query(count_query, params=params or None)
        total_count = count_result[0].get('total', 0) if count_result else 0

        params["skip_offset"] = request.offset
        params["page_limit"] = request.limit
        data_query = base_query + "\nRETURN c SKIP $skip_offset LIMIT $page_limit"
        data_result = db.execute_data_query(data_query, params=params)

        cases = []
        for row in data_result:
            case_data = row.get('c', {})
            if case_data:
                cases.append(CaseMatch(
                    case_id=str(case_data.get('case_id', '')),
                    case_ref_id=str(case_data.get('case_ref_id', '')),
                    case_status=str(case_data.get('case_status', '')),
                    origin_country=request.origin_country or "",
                    receiving_country=request.receiving_country or "",
                    pia_status=case_data.get('pia_status'),
                    tia_status=case_data.get('tia_status'),
                    hrpr_status=case_data.get('hrpr_status'),
                    is_compliant=(
                        case_data.get('pia_status') == 'Completed' and
                        (case_data.get('tia_status') == 'Completed' or not case_data.get('tia_status')) and
                        (case_data.get('hrpr_status') == 'Completed' or not case_data.get('hrpr_status'))
                    ),
                ))

        return SearchCasesResponse(
            total_count=total_count,
            returned_count=len(cases),
            cases=cases,
            query_time_ms=(time.time() - start_time) * 1000
        )

    except Exception as e:
        logger.error(f"Error searching cases: {e}")
        raise HTTPException(status_code=500, detail=str(e))
