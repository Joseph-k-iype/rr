"""
Compliance Engine API
=====================
FastAPI application for data transfer compliance evaluation.
Pydantic v2 compatible with lifespan events.
"""

import json
import logging
import time
from typing import Optional
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from models.schemas import (
    RulesEvaluationRequest,
    RulesEvaluationResponse,
    SearchCasesRequest,
    SearchCasesResponse,
    AIRuleGenerationRequest,
    AIRuleGenerationResponse,
    RulesOverviewResponse,
    RuleOverview,
    StatsResponse,
    HealthCheckResponse,
    ErrorResponse,
    CaseMatch,
    AgentActionEntry,
    AgentSessionSummary,
    ReferenceDataResult,
    AgentApprovalRequest,
)
from services.database import get_db_service
from services.cache import get_cache_service
from services.rules_evaluator import get_rules_evaluator
from agents.ai_service import get_ai_service
from agents.rule_generator import get_rule_generator
from services.agent_audit import get_agent_audit_trail
from rules.dictionaries.rules_definitions import (
    get_enabled_case_matching_rules,
    get_enabled_transfer_rules,
    get_enabled_attribute_rules,
)
from rules.templates.cypher_templates import list_templates


# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager"""
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")

    # Initialize services
    db = get_db_service()
    if db.check_connection():
        logger.info("Database connection established")
    else:
        logger.warning("Database connection failed")

    # Initialize cache
    get_cache_service()
    logger.info(f"Cache initialized (enabled={settings.cache.enable_cache})")

    # Initialize AI service
    ai = get_ai_service()
    logger.info(f"AI service initialized (enabled={ai.is_enabled})")

    yield  # Application runs here

    # Shutdown
    logger.info("Shutting down application")
    cache = get_cache_service()
    cache.clear()


# Create FastAPI app with lifespan
app = FastAPI(
    title=settings.app_name,
    description="Scalable compliance engine for cross-border data transfer evaluation",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_path = settings.paths.static_dir
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Setup templates
templates_path = settings.paths.html_templates_dir
templates = Jinja2Templates(directory=str(templates_path)) if templates_path.exists() else None


# =============================================================================
# DEPENDENCIES
# =============================================================================

def get_db():
    """Dependency for database service"""
    return get_db_service()


def get_evaluator():
    """Dependency for rules evaluator"""
    return get_rules_evaluator()


def get_cache():
    """Dependency for cache service"""
    return get_cache_service()


# =============================================================================
# HEALTH & STATUS ENDPOINTS
# =============================================================================

@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint"""
    db = get_db_service()
    ai = get_ai_service()

    return HealthCheckResponse(
        status="healthy",
        version=settings.app_version,
        database_connected=db.check_connection(),
        rules_graph_loaded=db.check_rules_graph(),
        data_graph_loaded=db.check_data_graph(),
        ai_service_available=ai.is_enabled and ai.check_availability(),
        timestamp=datetime.now()
    )


@app.get("/api/stats", response_model=StatsResponse)
async def get_stats(db=Depends(get_db)):
    """Get dashboard statistics"""
    cache = get_cache_service()

    # Try cache first
    cached_stats = cache.get("dashboard_stats", "metadata")
    if cached_stats:
        return StatsResponse(**cached_stats)

    # Query statistics
    try:
        # Case statistics
        case_query = """
        MATCH (c:Case)
        WHERE c.case_status IN ['Completed', 'Complete', 'Active', 'Published']
        RETURN count(c) as total_cases,
               count(CASE WHEN c.pia_status = 'Completed' THEN 1 END) as pia_completed,
               count(CASE WHEN c.tia_status = 'Completed' THEN 1 END) as tia_completed,
               count(CASE WHEN c.hrpr_status = 'Completed' THEN 1 END) as hrpr_completed
        """
        case_result = db.execute_data_query(case_query)
        case_data = case_result[0] if case_result else {}

        # Country counts
        country_query = "MATCH (c:Country) RETURN count(c) as count"
        country_result = db.execute_data_query(country_query)
        country_count = country_result[0].get('count', 0) if country_result else 0

        # Jurisdiction counts
        jurisdiction_query = "MATCH (j:Jurisdiction) RETURN count(j) as count"
        jurisdiction_result = db.execute_data_query(jurisdiction_query)
        jurisdiction_count = jurisdiction_result[0].get('count', 0) if jurisdiction_result else 0

        # Purpose counts
        purpose_query = "MATCH (p:Purpose) RETURN count(p) as count"
        purpose_result = db.execute_data_query(purpose_query)
        purpose_count = purpose_result[0].get('count', 0) if purpose_result else 0

        # Rules count
        rules_count = (
            len(get_enabled_case_matching_rules()) +
            len(get_enabled_transfer_rules()) +
            len(get_enabled_attribute_rules())
        )

        stats = {
            "total_cases": case_data.get('total_cases', 0),
            "total_countries": country_count,
            "total_jurisdictions": jurisdiction_count,
            "total_purposes": purpose_count,
            "pia_completed_count": case_data.get('pia_completed', 0),
            "tia_completed_count": case_data.get('tia_completed', 0),
            "hrpr_completed_count": case_data.get('hrpr_completed', 0),
            "rules_count": rules_count,
            "cache_hit_rate": cache.get_all_stats().get('queries', {}).get('hit_rate', 0)
        }

        # Cache the stats
        cache.set("dashboard_stats", stats, "metadata", ttl=60)

        return StatsResponse(**stats)

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# RULES EVALUATION ENDPOINTS
# =============================================================================

@app.post("/api/evaluate-rules", response_model=RulesEvaluationResponse)
async def evaluate_rules(
    request: RulesEvaluationRequest,
    evaluator=Depends(get_evaluator)
):
    """
    Evaluate compliance rules for a data transfer.

    This endpoint evaluates both sets of rules:
    - SET 1: Case-matching rules (precedent-based)
    - SET 2: Generic rules (transfer and attribute-based)
    """
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


@app.post("/api/search-cases", response_model=SearchCasesResponse)
async def search_cases(
    request: SearchCasesRequest,
    db=Depends(get_db)
):
    """Search for historical precedent cases"""
    start_time = time.time()

    try:
        # Build query
        query_parts = [
            "MATCH (c:Case)",
            "WHERE c.case_status IN ['Completed', 'Complete', 'Active', 'Published']"
        ]

        # Add filters
        if request.origin_country:
            query_parts.append(
                f"MATCH (c)-[:ORIGINATES_FROM]->(origin:Country {{name: '{request.origin_country}'}})"
            )
        if request.receiving_country:
            query_parts.append(
                f"MATCH (c)-[:TRANSFERS_TO]->(receiving:Jurisdiction {{name: '{request.receiving_country}'}})"
            )
        if request.purposes:
            purposes_str = "', '".join(request.purposes)
            query_parts.append(
                f"MATCH (c)-[:HAS_PURPOSE]->(p:Purpose) WHERE p.name IN ['{purposes_str}']"
            )
        if request.pii is not None:
            query_parts.append(f"AND c.pii = {str(request.pii).lower()}")

        # Count query
        count_query = "\n".join(query_parts) + "\nRETURN count(c) as total"
        count_result = db.execute_data_query(count_query)
        total_count = count_result[0].get('total', 0) if count_result else 0

        # Data query with pagination
        data_query = "\n".join(query_parts)
        data_query += f"\nRETURN c SKIP {request.offset} LIMIT {request.limit}"
        data_result = db.execute_data_query(data_query)

        # Build response
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


# =============================================================================
# RULES OVERVIEW ENDPOINTS
# =============================================================================

@app.get("/api/rules-overview", response_model=RulesOverviewResponse)
async def get_rules_overview():
    """Get overview of all enabled rules"""
    case_matching = get_enabled_case_matching_rules()
    transfer = get_enabled_transfer_rules()
    attribute = get_enabled_attribute_rules()

    def build_overview(rule, rule_type: str) -> RuleOverview:
        """Build overview from any rule type"""
        if rule_type == "case_matching":
            origin_scope = rule.origin_group or str(rule.origin_countries) if rule.origin_countries else "Any"
            receiving_scope = rule.receiving_group or str(rule.receiving_countries) if rule.receiving_countries else "Any"
            required = rule.required_assessments.to_list()
            conditions = []
            if rule.requires_pii:
                conditions.append("Requires PII")
            if rule.requires_personal_data:
                conditions.append("Requires Personal Data")
        elif rule_type == "transfer":
            origin_scope = rule.origin_group or "Specific countries"
            receiving_scope = rule.receiving_group or "Specific countries"
            required = rule.required_actions
            conditions = []
            if rule.requires_pii:
                conditions.append("Requires PII")
            if rule.requires_any_data:
                conditions.append("Any data")
        else:  # attribute
            origin_scope = rule.origin_group or str(rule.origin_countries) if rule.origin_countries else "Any"
            receiving_scope = rule.receiving_group or str(rule.receiving_countries) if rule.receiving_countries else "Any"
            required = []
            conditions = [f"Attribute: {rule.attribute_name}"]
            if rule.requires_pii:
                conditions.append("Requires PII")

        return RuleOverview(
            rule_id=rule.rule_id,
            name=rule.name,
            description=rule.description,
            rule_type=rule_type,
            priority=rule.priority,
            origin_scope=origin_scope,
            receiving_scope=receiving_scope,
            outcome=rule.odrl_type,
            required_assessments=required,
            conditions=conditions,
            enabled=rule.enabled
        )

    return RulesOverviewResponse(
        total_rules=len(case_matching) + len(transfer) + len(attribute),
        case_matching_rules=[build_overview(r, "case_matching") for r in case_matching.values()],
        transfer_rules=[build_overview(r, "transfer") for r in transfer.values()],
        attribute_rules=[build_overview(r, "attribute") for r in attribute.values()],
    )


@app.get("/api/cypher-templates")
async def get_cypher_templates():
    """Get list of available Cypher query templates"""
    return list_templates()


# =============================================================================
# AI RULE GENERATION ENDPOINTS
# =============================================================================

@app.post("/api/ai/generate-rule", response_model=AIRuleGenerationResponse)
async def generate_rule_with_ai(request: AIRuleGenerationRequest):
    """
    Generate a rule definition using AI from natural language description.

    Requires AI service to be enabled and configured.
    For attribute-level rules, also generates the attribute detection configuration
    including keywords, patterns, and categories for metadata detection.

    When agentic_mode=True, the AI agent will autonomously:
    - Detect missing reference data (country groups, attribute configs, keyword dictionaries)
    - Generate the required reference data
    - Track all actions in the audit trail for traceability
    """
    generator = get_rule_generator()
    ai_service = get_ai_service()

    if not ai_service.is_enabled:
        return AIRuleGenerationResponse(
            success=False,
            message="AI service is not enabled. Enable it in settings.",
            review_required=False
        )

    # Check if agentic mode is allowed
    agentic_mode = request.agentic_mode and settings.ai.enable_agentic_mode

    try:
        # Generate the rule (with agentic mode if enabled)
        generated = generator.generate_rule(
            rule_text=request.rule_text,
            rule_country=request.rule_country,
            rule_type_hint=request.rule_type,
            agentic_mode=agentic_mode,
        )

        if not generated.is_valid:
            # Build agent session summary if available
            agent_session = _build_agent_session_summary(generated.audit_session_id)

            return AIRuleGenerationResponse(
                success=False,
                validation_errors=generated.validation_errors,
                message="Rule generation completed but validation failed",
                review_required=True,
                agentic_mode=agentic_mode,
                agent_session=agent_session,
            )

        # Test in temporary graph if requested
        test_results = None
        if request.test_in_temp_graph:
            test_results = generator.test_rule_in_temp_graph(generated)

        # Export for review (don't auto-save attribute config - require approval)
        export = generator.export_rule_for_review(generated, save_attribute_config=False)

        # Build attribute config response for attribute-level rules
        attribute_config = None
        attribute_config_json = None
        if export.get("attribute_config"):
            from models.schemas import AttributeConfigResponse
            ac = export["attribute_config"]
            attribute_config = AttributeConfigResponse(
                attribute_name=ac.get("attribute_name", ""),
                keywords=ac.get("keywords", []),
                patterns=ac.get("patterns", []),
                categories=ac.get("categories", []),
                detection_settings=ac.get("detection_settings", {}),
            )
            attribute_config_json = export.get("attribute_config_json")

        # Build reference data results from agentic actions
        reference_data_created = []
        for ref_item in generated.reference_data:
            reference_data_created.append(ReferenceDataResult(
                created=ref_item.created,
                data_type=ref_item.data_type,
                name=ref_item.name,
                details=ref_item.details,
                requires_approval=ref_item.requires_approval,
                approval_status=ref_item.approval_status,
            ))

        # Build agent session summary
        agent_session = _build_agent_session_summary(generated.audit_session_id)

        # Build message based on rule type and agentic mode
        rule_type = generated.rule_definition.get("rule_type")
        if agentic_mode and reference_data_created:
            ref_summary = ", ".join(f"{r.data_type}:{r.name}" for r in reference_data_created)
            message = (
                f"Rule generated successfully with agentic reference data creation. "
                f"Created: {ref_summary}. Review all generated artifacts before deploying."
            )
        elif rule_type == "attribute":
            message = (
                "Attribute rule generated successfully. Review the rule definition and "
                "attribute detection configuration, then add to rules_definitions.py "
                "and save the config JSON to config/ directory."
            )
        else:
            message = "Rule generated successfully. Review and add to rules_definitions.py"

        return AIRuleGenerationResponse(
            success=True,
            rule_id=generated.rule_definition.get("rule_id"),
            rule_type=rule_type,
            generated_dictionary=generated.rule_definition,
            generated_cypher=export.get("cypher_queries"),
            generated_python_code=export.get("python_code"),
            attribute_config=attribute_config,
            attribute_config_json=attribute_config_json,
            test_results=test_results,
            message=message,
            review_required=True,
            agentic_mode=agentic_mode,
            reference_data_created=reference_data_created,
            agent_session=agent_session,
        )

    except Exception as e:
        logger.error(f"Error generating rule with AI: {e}")
        return AIRuleGenerationResponse(
            success=False,
            message=f"Error: {str(e)}",
            review_required=False
        )


def _build_agent_session_summary(session_id: Optional[str]) -> Optional[AgentSessionSummary]:
    """Build an AgentSessionSummary from audit trail data"""
    if not session_id:
        return None

    audit = get_agent_audit_trail()
    session_data = audit.get_session(session_id)
    if not session_data:
        return None

    actions = []
    for entry in session_data.get("entries", []):
        actions.append(AgentActionEntry(
            entry_id=entry.get("entry_id", ""),
            action_type=entry.get("action_type", ""),
            agent_name=entry.get("agent_name", ""),
            status=entry.get("status", ""),
            input_summary=entry.get("input_summary", ""),
            output_summary=entry.get("output_summary", ""),
            duration_ms=entry.get("duration_ms", 0.0),
            requires_approval=entry.get("requires_approval", False),
            error_message=entry.get("error_message"),
            timestamp=entry.get("timestamp", ""),
        ))

    return AgentSessionSummary(
        session_id=session_data.get("session_id", ""),
        correlation_id=session_data.get("correlation_id", ""),
        session_type=session_data.get("session_type", ""),
        status=session_data.get("status", ""),
        total_actions=session_data.get("total_actions", 0),
        successful_actions=session_data.get("successful_actions", 0),
        failed_actions=session_data.get("failed_actions", 0),
        pending_approvals=session_data.get("pending_approvals", 0),
        agentic_mode=session_data.get("agentic_mode", False),
        actions=actions,
        created_at=session_data.get("created_at", ""),
        completed_at=session_data.get("completed_at"),
    )


@app.get("/api/ai/status")
async def get_ai_status():
    """Get AI service status"""
    ai = get_ai_service()
    return {
        "enabled": ai.is_enabled,
        "available": ai.check_availability() if ai.is_enabled else False,
        "model": settings.ai.llm_model,
    }


# =============================================================================
# AGENT AUDIT & TRACEABILITY ENDPOINTS
# =============================================================================

@app.get("/api/agent/sessions")
async def get_agent_sessions(
    limit: int = 50,
    session_type: Optional[str] = None,
    status: Optional[str] = None,
):
    """Get recent agent sessions for audit/traceability"""
    audit = get_agent_audit_trail()
    return audit.get_recent_sessions(
        limit=limit, session_type=session_type, status=status
    )


@app.get("/api/agent/sessions/{session_id}")
async def get_agent_session(session_id: str):
    """Get detailed agent session with all actions"""
    audit = get_agent_audit_trail()
    session = audit.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.get("/api/agent/pending-approvals")
async def get_pending_approvals():
    """Get all agent actions pending approval"""
    audit = get_agent_audit_trail()
    return audit.get_pending_approvals()


@app.post("/api/agent/approve")
async def approve_or_reject_action(request: AgentApprovalRequest):
    """Approve or reject a pending agent action"""
    audit = get_agent_audit_trail()

    if request.action == "approve":
        success = audit.approve_action(
            entry_id=request.entry_id,
            approved_by=request.approved_by,
        )
    elif request.action == "reject":
        success = audit.reject_action(
            entry_id=request.entry_id,
            rejected_by=request.approved_by,
            reason=request.reason or "",
        )
    else:
        raise HTTPException(status_code=400, detail="Action must be 'approve' or 'reject'")

    if not success:
        raise HTTPException(status_code=404, detail="Action entry not found")

    return {"success": True, "message": f"Action {request.action}d successfully"}


@app.get("/api/agent/stats")
async def get_agent_stats():
    """Get agent audit trail statistics"""
    audit = get_agent_audit_trail()
    return audit.get_stats()


@app.get("/api/agent/sessions/{session_id}/export")
async def export_agent_session(session_id: str):
    """Export an agent session as JSON for compliance reporting"""
    audit = get_agent_audit_trail()
    export = audit.export_session(session_id)
    if not export:
        raise HTTPException(status_code=404, detail="Session not found")
    return JSONResponse(
        content=json.loads(export),
        headers={"Content-Disposition": f"attachment; filename=agent_session_{session_id}.json"},
    )


# =============================================================================
# METADATA ENDPOINTS
# =============================================================================

@app.get("/api/countries")
async def get_countries(db=Depends(get_db)):
    """Get list of all countries"""
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


@app.get("/api/purposes")
async def get_purposes(db=Depends(get_db)):
    """Get list of all purposes"""
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


@app.get("/api/processes")
async def get_processes(db=Depends(get_db)):
    """Get list of all processes by level"""
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


@app.get("/api/all-dropdown-values")
async def get_all_dropdown_values(db=Depends(get_db)):
    """Get all dropdown values in one call"""
    cache = get_cache_service()
    cached = cache.get("all_dropdown_values", "metadata")
    if cached:
        return cached

    try:
        # Get all in parallel (sequentially for simplicity)
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


# =============================================================================
# CACHE MANAGEMENT ENDPOINTS
# =============================================================================

@app.get("/api/cache/clear")
async def clear_cache():
    """Clear all caches"""
    cache = get_cache_service()
    cleared = cache.clear()
    return {"message": f"Cleared {cleared} cache entries"}


@app.get("/api/cache/stats")
async def get_cache_stats():
    """Get cache statistics"""
    cache = get_cache_service()
    return cache.get_all_stats()


# =============================================================================
# UI ROUTES
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page"""
    if templates is None:
        return HTMLResponse(content="<h1>Dashboard templates not found</h1>")

    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "version": settings.app_version}
    )


@app.get("/rules", response_class=HTMLResponse)
async def rules_page(request: Request):
    """Rules overview page"""
    if templates is None:
        return HTMLResponse(content="<h1>Rules templates not found</h1>")

    return templates.TemplateResponse(
        "rules_overview.html",
        {"request": request, "version": settings.app_version}
    )


# =============================================================================
# ERROR HANDLERS
# =============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            code=str(exc.status_code),
        ).model_dump()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            detail=str(exc) if settings.environment == "development" else None,
        ).model_dump()
    )


# =============================================================================
# RUN SERVER
# =============================================================================

def run():
    """Run the API server"""
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.reload,
        workers=settings.api.workers if not settings.api.reload else 1,
        log_level=settings.log_level.lower()
    )


if __name__ == "__main__":
    run()
