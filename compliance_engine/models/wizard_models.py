"""
Wizard Models
=============
Pydantic models for the rule ingestion wizard.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
from datetime import datetime


class WizardStep(str, Enum):
    """Wizard step identifiers"""
    COUNTRY_SELECTION = "country_selection"
    SCENARIO_TYPE = "scenario_type"
    RULE_INPUT = "rule_input"
    AI_ANALYSIS = "ai_analysis"
    AI_DICTIONARY = "ai_dictionary"
    REVIEW = "review"
    EDIT = "edit"
    SANDBOX_LOAD = "sandbox_load"
    SANDBOX_TEST = "sandbox_test"
    APPROVAL = "approval"


class ScenarioType(str, Enum):
    """Types of compliance scenarios"""
    TRANSFER = "transfer"
    ATTRIBUTE = "attribute"


class WizardSessionStatus(str, Enum):
    """Status of a wizard session"""
    ACTIVE = "active"
    PROCESSING = "processing"
    AWAITING_REVIEW = "awaiting_review"
    SANDBOX_LOADED = "sandbox_loaded"
    APPROVED = "approved"
    CANCELLED = "cancelled"
    FAILED = "failed"


class WizardStartRequest(BaseModel):
    """Request to start a new wizard session"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "analyst_01"
            }
        }
    )
    user_id: str = Field(default="anonymous", description="User starting the session")


class WizardStartResponse(BaseModel):
    """Response when a wizard session is created"""
    session_id: str
    status: WizardSessionStatus = WizardSessionStatus.ACTIVE
    current_step: int = 1
    created_at: str


class WizardStepSubmission(BaseModel):
    """Data submitted at each wizard step"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "step": 1,
                "data": {
                    "origin_country": "United Kingdom",
                    "receiving_countries": ["India", "China"]
                }
            }
        }
    )
    step: int = Field(..., ge=1, le=10, description="Step number (1-10)")
    data: Dict[str, Any] = Field(..., description="Step-specific data")


class WizardSessionState(BaseModel):
    """Full state of a wizard session"""
    session_id: str
    user_id: str = "anonymous"
    status: WizardSessionStatus = WizardSessionStatus.ACTIVE
    current_step: int = 1
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    # Step 1: Country selection
    origin_country: Optional[str] = None
    receiving_countries: List[str] = Field(default_factory=list)

    # Step 2: Scenario type
    scenario_type: Optional[ScenarioType] = None
    data_categories: List[str] = Field(default_factory=list)

    # Step 3: Rule text input
    rule_text: Optional[str] = None
    is_pii_related: bool = False

    # Steps 4-5: AI-generated results
    analysis_result: Optional[Dict[str, Any]] = None
    dictionary_result: Optional[Dict[str, Any]] = None

    # Step 6: Review snapshot
    review_snapshot: Optional[Dict[str, Any]] = None

    # Step 7: User edits
    edited_rule_definition: Optional[Dict[str, Any]] = None
    edited_terms_dictionary: Optional[Dict[str, Any]] = None

    # Step 8: Sandbox
    sandbox_graph_name: Optional[str] = None

    # Step 9: Sandbox test results
    sandbox_test_results: List[Dict[str, Any]] = Field(default_factory=list)

    # Step 10: Approval
    approved: bool = False
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None

    # Error tracking
    error_message: Optional[str] = None


class WizardSessionResponse(BaseModel):
    """Response for getting wizard session state"""
    session_id: str
    status: WizardSessionStatus
    current_step: int
    origin_country: Optional[str] = None
    receiving_countries: List[str] = Field(default_factory=list)
    scenario_type: Optional[str] = None
    data_categories: List[str] = Field(default_factory=list)
    rule_text: Optional[str] = None
    analysis_result: Optional[Dict[str, Any]] = None
    dictionary_result: Optional[Dict[str, Any]] = None
    edited_rule_definition: Optional[Dict[str, Any]] = None
    edited_terms_dictionary: Optional[Dict[str, Any]] = None
    sandbox_graph_name: Optional[str] = None
    sandbox_test_results: List[Dict[str, Any]] = Field(default_factory=list)
    approved: bool = False
    error_message: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


class RuleEditRequest(BaseModel):
    """Request to edit a rule definition in step 7"""
    rule_definition: Dict[str, Any] = Field(..., description="Edited rule definition")


class TermsEditRequest(BaseModel):
    """Request to edit terms dictionary in step 7"""
    terms_dictionary: Dict[str, Any] = Field(..., description="Edited terms dictionary")


class SandboxEvaluationRequest(BaseModel):
    """Request to evaluate rules in the sandbox"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "origin_country": "United Kingdom",
                "receiving_country": "India",
                "pii": True,
                "purposes": ["Marketing"],
            }
        }
    )
    origin_country: str
    receiving_country: str
    pii: bool = False
    purposes: Optional[List[str]] = None
    process_l1: Optional[List[str]] = None
    process_l2: Optional[List[str]] = None
    process_l3: Optional[List[str]] = None
    personal_data_names: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class WizardApprovalRequest(BaseModel):
    """Request to approve the wizard output and load to main graph"""
    approved_by: str = Field(default="admin", description="Who is approving")
    notes: Optional[str] = None
