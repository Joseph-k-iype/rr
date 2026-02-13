"""
Evaluation Router
==================
Endpoints for rule evaluation and case search.
Supports legal entity parameters, multi-select, case-insensitive matching.
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
    """Evaluate compliance rules for a data transfer.
    Supports multi-select receiving countries - evaluates each and merges results.
    If ANY rule is a prohibition, overall result is PROHIBITION.
    """
    try:
        receiving_countries = request.get_receiving_countries()

        if len(receiving_countries) <= 1:
            receiving = receiving_countries[0] if receiving_countries else ""
            result = evaluator.evaluate(
                origin_country=request.origin_country,
                receiving_country=receiving,
                pii=request.pii,
                purposes=request.purposes,
                process_l1=request.process_l1,
                process_l2=request.process_l2,
                process_l3=request.process_l3,
                personal_data_names=request.personal_data_names,
                metadata=request.metadata,
                origin_legal_entity=request.origin_legal_entity,
                receiving_legal_entity=request.receiving_legal_entity[0] if request.receiving_legal_entity else None,
            )
            return result

        # Multi-select: evaluate each receiving country
        all_results = []
        for rc in receiving_countries:
            r = evaluator.evaluate(
                origin_country=request.origin_country,
                receiving_country=rc,
                pii=request.pii,
                purposes=request.purposes,
                process_l1=request.process_l1,
                process_l2=request.process_l2,
                process_l3=request.process_l3,
                personal_data_names=request.personal_data_names,
                metadata=request.metadata,
                origin_legal_entity=request.origin_legal_entity,
            )
            all_results.append(r)

        # Merge: if any is PROHIBITED, overall is PROHIBITED
        merged_triggered = []
        merged_duties = []
        merged_prohibition_reasons = []
        has_prohibition = False

        for r in all_results:
            merged_triggered.extend(r.triggered_rules)
            merged_duties.extend(r.consolidated_duties)
            merged_prohibition_reasons.extend(r.prohibition_reasons)
            if r.transfer_status.value == "PROHIBITED":
                has_prohibition = True

        from models.schemas import TransferStatus
        final_status = TransferStatus.PROHIBITED if has_prohibition else all_results[0].transfer_status

        return RulesEvaluationResponse(
            transfer_status=final_status,
            origin_country=request.origin_country,
            receiving_country=", ".join(receiving_countries),
            pii=request.pii,
            triggered_rules=merged_triggered,
            precedent_validation=all_results[0].precedent_validation if all_results else None,
            assessment_compliance=all_results[0].assessment_compliance if all_results else None,
            detected_attributes=all_results[0].detected_attributes if all_results else [],
            consolidated_duties=list(set(merged_duties)),
            prohibition_reasons=merged_prohibition_reasons,
            evidence_summary=all_results[0].evidence_summary if all_results else None,
            message=f"Evaluated {len(receiving_countries)} receiving countries. Status: {final_status.value}",
            evaluation_time_ms=sum(r.evaluation_time_ms for r in all_results),
        )

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
