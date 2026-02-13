"""
Wizard Router
==============
6-step rule ingestion wizard with save/resume support.
Steps: 1. Country, 2. Metadata, 3. Rule, 4. Review, 5. Sandbox Test, 6. Approve
"""

import uuid
import logging
from typing import Dict
from datetime import datetime
from fastapi import APIRouter, HTTPException

from models.wizard_models import (
    WizardStartRequest,
    WizardStartResponse,
    WizardStepSubmission,
    WizardSessionState,
    WizardSessionResponse,
    WizardSessionStatus,
    RuleEditRequest,
    TermsEditRequest,
    WizardApprovalRequest,
    SavedSessionSummary,
)
from services.sandbox_service import get_sandbox_service
from services.session_store import get_session_store
from agents.workflows.rule_ingestion_workflow import run_rule_ingestion

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/wizard", tags=["wizard"])

# In-memory session store (production would use Redis/DB)
_sessions: Dict[str, WizardSessionState] = {}


@router.post("/start-session", response_model=WizardStartResponse)
async def start_session(request: WizardStartRequest):
    """Start a new wizard session."""
    session_id = f"wiz_{uuid.uuid4().hex[:12]}"
    now = datetime.now().isoformat()

    session = WizardSessionState(
        session_id=session_id,
        user_id=request.user_id,
        status=WizardSessionStatus.ACTIVE,
        current_step=1,
        created_at=now,
        updated_at=now,
    )
    _sessions[session_id] = session

    logger.info(f"Wizard session started: {session_id}")
    return WizardStartResponse(
        session_id=session_id,
        status=WizardSessionStatus.ACTIVE,
        current_step=1,
        created_at=now,
    )


@router.post("/submit-step")
async def submit_step(session_id: str, submission: WizardStepSubmission):
    """Submit step data. Triggers AI agents at step 3."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    data = submission.data
    step = submission.step
    session.updated_at = datetime.now().isoformat()

    if step == 1:
        # Country step
        session.origin_country = data.get("origin_country")
        session.receiving_countries = data.get("receiving_countries", [])
        session.origin_legal_entity = data.get("origin_legal_entity")
        session.receiving_legal_entity = data.get("receiving_legal_entity")
        session.current_step = 2

    elif step == 2:
        # Metadata step
        session.data_categories = data.get("data_categories", [])
        session.purposes_of_processing = data.get("purposes_of_processing", [])
        session.process_l1 = data.get("process_l1", [])
        session.process_l2 = data.get("process_l2", [])
        session.process_l3 = data.get("process_l3", [])
        session.group_data_categories = data.get("group_data_categories", [])
        session.valid_until = data.get("valid_until")
        session.current_step = 3

    elif step == 3:
        # Rule step - triggers AI agents
        session.rule_text = data.get("rule_text")
        session.is_pii_related = data.get("is_pii_related", False)
        session.status = WizardSessionStatus.PROCESSING
        session.current_step = 4

        try:
            result = run_rule_ingestion(
                origin_country=session.origin_country,
                scenario_type="transfer",
                receiving_countries=session.receiving_countries,
                rule_text=session.rule_text,
                data_categories=session.data_categories,
                is_pii_related=session.is_pii_related,
                thread_id=session_id,
            )

            session.analysis_result = result.analysis_result
            session.dictionary_result = result.dictionary_result

            if result.success:
                session.edited_rule_definition = result.rule_definition
                # Add valid_until to rule definition
                if session.valid_until and session.edited_rule_definition:
                    session.edited_rule_definition['valid_until'] = session.valid_until
                session.status = WizardSessionStatus.AWAITING_REVIEW
                session.current_step = 4
            else:
                session.error_message = result.error_message
                session.status = WizardSessionStatus.FAILED

        except Exception as e:
            logger.error(f"AI agent error: {e}")
            session.error_message = str(e)
            session.status = WizardSessionStatus.FAILED

    elif step == 4:
        # Review step - user confirms edited rule
        session.review_snapshot = {
            "rule_definition": session.edited_rule_definition,
            "dictionary": session.dictionary_result,
        }
        session.current_step = 5

    elif step == 5:
        # Sandbox test step - go to approve
        session.current_step = 6

    else:
        raise HTTPException(status_code=400, detail=f"Invalid step: {step}")

    return {
        "session_id": session_id,
        "status": session.status,
        "current_step": session.current_step,
        "message": f"Step {step} submitted successfully",
    }


@router.get("/session/{session_id}", response_model=WizardSessionResponse)
async def get_session(session_id: str):
    """Get wizard session state."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return WizardSessionResponse(
        session_id=session.session_id,
        status=session.status,
        current_step=session.current_step,
        origin_country=session.origin_country,
        receiving_countries=session.receiving_countries,
        origin_legal_entity=session.origin_legal_entity,
        receiving_legal_entity=session.receiving_legal_entity,
        data_categories=session.data_categories,
        purposes_of_processing=session.purposes_of_processing,
        process_l1=session.process_l1,
        process_l2=session.process_l2,
        process_l3=session.process_l3,
        group_data_categories=session.group_data_categories,
        valid_until=session.valid_until,
        rule_text=session.rule_text,
        analysis_result=session.analysis_result,
        dictionary_result=session.dictionary_result,
        edited_rule_definition=session.edited_rule_definition,
        edited_terms_dictionary=session.edited_terms_dictionary,
        sandbox_graph_name=session.sandbox_graph_name,
        sandbox_test_results=session.sandbox_test_results,
        approved=session.approved,
        error_message=session.error_message,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.put("/session/{session_id}/edit-rule")
async def edit_rule(session_id: str, request: RuleEditRequest):
    """Edit rule definition (step 4)."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.edited_rule_definition = request.rule_definition
    session.updated_at = datetime.now().isoformat()

    return {"message": "Rule definition updated", "session_id": session_id}


@router.put("/session/{session_id}/edit-terms")
async def edit_terms(session_id: str, request: TermsEditRequest):
    """Edit terms dictionary (step 4)."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.edited_terms_dictionary = request.terms_dictionary
    session.updated_at = datetime.now().isoformat()

    return {"message": "Terms dictionary updated", "session_id": session_id}


@router.post("/session/{session_id}/load-sandbox")
async def load_sandbox(session_id: str):
    """Load rule into sandbox graph (step 5)."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.edited_rule_definition:
        raise HTTPException(status_code=400, detail="No rule definition to load")

    sandbox = get_sandbox_service()

    try:
        graph_name = sandbox.create_sandbox(session_id)
        success = sandbox.add_rule_to_sandbox(
            graph_name,
            session.edited_rule_definition,
            dictionary_result=session.dictionary_result,
        )

        if success:
            session.sandbox_graph_name = graph_name
            session.status = WizardSessionStatus.SANDBOX_LOADED
            session.current_step = 5
            session.updated_at = datetime.now().isoformat()
            return {
                "message": "Rule loaded into sandbox",
                "sandbox_graph": graph_name,
                "session_id": session_id,
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to add rule to sandbox")

    except Exception as e:
        logger.error(f"Sandbox load error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/{session_id}/sandbox-evaluate")
async def sandbox_evaluate(session_id: str, request: dict):
    """Test rule in sandbox (step 5)."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.sandbox_graph_name:
        raise HTTPException(status_code=400, detail="No sandbox loaded")

    sandbox = get_sandbox_service()

    try:
        result = sandbox.evaluate_in_sandbox(
            graph_name=session.sandbox_graph_name,
            origin_country=request.get("origin_country", ""),
            receiving_country=request.get("receiving_country", ""),
            pii=request.get("pii", False),
            purposes=request.get("purposes"),
            process_l1=request.get("process_l1"),
            process_l2=request.get("process_l2"),
            process_l3=request.get("process_l3"),
            personal_data_names=request.get("personal_data_names"),
            metadata=request.get("metadata"),
        )

        # Clear previous results and set new one (fresh run each time)
        session.sandbox_test_results = [result]
        session.updated_at = datetime.now().isoformat()

        return {"result": result, "test_number": 1}

    except Exception as e:
        logger.error(f"Sandbox evaluation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/{session_id}/approve")
async def approve_rule(session_id: str, request: WizardApprovalRequest):
    """Approve & load rule to main graph (step 6)."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.edited_rule_definition:
        raise HTTPException(status_code=400, detail="No rule definition to approve")

    sandbox = get_sandbox_service()

    try:
        success = sandbox.promote_to_main(
            graph_name=session.sandbox_graph_name or "",
            rule_def=session.edited_rule_definition,
        )

        if success:
            session.approved = True
            session.approved_by = request.approved_by
            session.approved_at = datetime.now().isoformat()
            session.status = WizardSessionStatus.APPROVED
            session.current_step = 6
            session.updated_at = datetime.now().isoformat()

            # Cleanup sandbox
            if session.sandbox_graph_name:
                sandbox.cleanup_session(session_id)

            # Delete saved session if exists
            store = get_session_store()
            store.delete_session(session_id)

            return {
                "message": "Rule approved and loaded to main graph",
                "rule_id": session.edited_rule_definition.get("rule_id"),
                "session_id": session_id,
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to promote rule")

    except Exception as e:
        logger.error(f"Approval error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Save/Resume endpoints ─────────────────────────────────────────────

@router.post("/save-session")
async def save_session(session_id: str):
    """Save current wizard session for later resume."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    store = get_session_store()
    state_dict = session.model_dump()
    state_dict["status"] = WizardSessionStatus.SAVED.value
    store.save_session(session_id, state_dict)

    session.status = WizardSessionStatus.SAVED
    session.updated_at = datetime.now().isoformat()

    return {"message": "Session saved", "session_id": session_id}


@router.get("/saved-sessions")
async def list_saved_sessions(user_id: str = None):
    """List all saved wizard sessions."""
    store = get_session_store()
    return store.list_sessions(user_id)


@router.get("/resume-session/{session_id}")
async def resume_session(session_id: str):
    """Resume a previously saved wizard session."""
    # Check in-memory first
    if session_id in _sessions:
        session = _sessions[session_id]
        session.status = WizardSessionStatus.ACTIVE
        session.updated_at = datetime.now().isoformat()
        return WizardSessionResponse(
            session_id=session.session_id,
            status=session.status,
            current_step=session.current_step,
            origin_country=session.origin_country,
            receiving_countries=session.receiving_countries,
            origin_legal_entity=session.origin_legal_entity,
            receiving_legal_entity=session.receiving_legal_entity,
            data_categories=session.data_categories,
            purposes_of_processing=session.purposes_of_processing,
            process_l1=session.process_l1,
            process_l2=session.process_l2,
            process_l3=session.process_l3,
            group_data_categories=session.group_data_categories,
            valid_until=session.valid_until,
            rule_text=session.rule_text,
            analysis_result=session.analysis_result,
            dictionary_result=session.dictionary_result,
            edited_rule_definition=session.edited_rule_definition,
            edited_terms_dictionary=session.edited_terms_dictionary,
            sandbox_graph_name=session.sandbox_graph_name,
            sandbox_test_results=session.sandbox_test_results,
            approved=session.approved,
            error_message=session.error_message,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )

    # Load from file store
    store = get_session_store()
    state_dict = store.load_session(session_id)
    if not state_dict:
        raise HTTPException(status_code=404, detail="Saved session not found")

    state_dict["status"] = WizardSessionStatus.ACTIVE.value
    session = WizardSessionState(**state_dict)
    _sessions[session_id] = session

    return WizardSessionResponse(
        session_id=session.session_id,
        status=session.status,
        current_step=session.current_step,
        origin_country=session.origin_country,
        receiving_countries=session.receiving_countries,
        origin_legal_entity=session.origin_legal_entity,
        receiving_legal_entity=session.receiving_legal_entity,
        data_categories=session.data_categories,
        purposes_of_processing=session.purposes_of_processing,
        process_l1=session.process_l1,
        process_l2=session.process_l2,
        process_l3=session.process_l3,
        group_data_categories=session.group_data_categories,
        valid_until=session.valid_until,
        rule_text=session.rule_text,
        analysis_result=session.analysis_result,
        dictionary_result=session.dictionary_result,
        edited_rule_definition=session.edited_rule_definition,
        edited_terms_dictionary=session.edited_terms_dictionary,
        sandbox_graph_name=session.sandbox_graph_name,
        sandbox_test_results=session.sandbox_test_results,
        approved=session.approved,
        error_message=session.error_message,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.delete("/saved-session/{session_id}")
async def delete_saved_session(session_id: str):
    """Delete a saved wizard session."""
    store = get_session_store()
    deleted = store.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session deleted", "session_id": session_id}


@router.delete("/session/{session_id}")
async def cancel_session(session_id: str):
    """Cancel wizard session & cleanup."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Cleanup sandbox if exists
    if session.sandbox_graph_name:
        sandbox = get_sandbox_service()
        sandbox.cleanup_session(session_id)

    session.status = WizardSessionStatus.CANCELLED
    session.updated_at = datetime.now().isoformat()

    return {"message": "Session cancelled", "session_id": session_id}
