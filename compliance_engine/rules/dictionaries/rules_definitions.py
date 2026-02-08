"""
Rules Definitions Dictionary
=============================
This file contains two sets of rules:

SET 1: Case-Matching Rules
--------------------------
These rules require finding at least one historical case that matches the given
parameters. If a perfect match is found with completed assessments, transfer is ALLOWED.

SET 2: Generic Country-Specific Rules
-------------------------------------
Category A: Transfer Rules - Country to country transfer permissions/prohibitions
Category B: Attribute Rules - Attribute-level restrictions (e.g., health data)

Developers can add/modify rules here without changing core logic.
"""

from typing import Dict, List, Optional, Set, Tuple, Any, FrozenSet
from dataclasses import dataclass, field
from enum import Enum


class RuleType(Enum):
    """Type of rule"""
    CASE_MATCHING = "case_matching"  # SET 1: Requires case matching
    TRANSFER = "transfer"            # SET 2A: Transfer rules
    ATTRIBUTE = "attribute"          # SET 2B: Attribute-level rules


class RuleOutcome(Enum):
    """Outcome if rule conditions are met"""
    PERMISSION = "permission"
    PROHIBITION = "prohibition"


class AssessmentType(Enum):
    """Types of assessments that can be required"""
    PIA = "pia"       # Privacy Impact Assessment
    TIA = "tia"       # Transfer Impact Assessment
    HRPR = "hrpr"     # High Risk Processing Review


@dataclass
class RequiredAssessments:
    """Assessment requirements for a rule"""
    pia_required: bool = False
    tia_required: bool = False
    hrpr_required: bool = False

    def to_list(self) -> List[str]:
        """Return list of required assessment names"""
        assessments = []
        if self.pia_required:
            assessments.append("PIA")
        if self.tia_required:
            assessments.append("TIA")
        if self.hrpr_required:
            assessments.append("HRPR")
        return assessments


@dataclass
class CaseMatchingRule:
    """
    SET 1: Case-Matching Rule Definition

    These rules search for historical cases that match the parameters.
    If at least one case matches with completed assessments, transfer is ALLOWED.
    """
    rule_id: str
    name: str
    description: str
    priority: int  # Lower number = higher priority

    # Country matching
    origin_countries: Optional[FrozenSet[str]] = None  # None = any country
    origin_group: Optional[str] = None  # Reference to COUNTRY_GROUPS key
    receiving_countries: Optional[FrozenSet[str]] = None  # None = any country
    receiving_group: Optional[str] = None
    receiving_not_in: Optional[FrozenSet[str]] = None  # Exclude these countries

    # Assessment requirements
    required_assessments: RequiredAssessments = field(default_factory=RequiredAssessments)

    # PII condition
    requires_pii: bool = False
    requires_personal_data: bool = False  # PersonalDataNames is not None

    # Rule status
    enabled: bool = True

    # ODRL properties
    odrl_type: str = "Permission"
    odrl_action: str = "transfer"
    odrl_target: str = "Data"


@dataclass
class TransferRule:
    """
    SET 2A: Transfer Rule Definition

    Country-to-country transfer permissions/prohibitions.
    These rules define whether data transfer between specific countries is allowed.
    """
    rule_id: str
    name: str
    description: str
    priority: int

    # Transfer specification (can use tuples or groups)
    # Format: List of (origin, receiving) tuples
    transfer_pairs: List[Tuple[str, str]] = field(default_factory=list)

    # Or use country groups
    origin_group: Optional[str] = None
    receiving_group: Optional[str] = None
    receiving_countries: Optional[FrozenSet[str]] = None  # Specific receiving countries
    bidirectional: bool = False  # If True, applies both ways

    # Outcome
    outcome: RuleOutcome = RuleOutcome.PERMISSION

    # Conditions
    requires_pii: bool = False
    requires_any_data: bool = False  # True = applies to all data

    # Actions/Duties (if permission, these are duties to fulfill)
    required_actions: List[str] = field(default_factory=list)

    # Rule status
    enabled: bool = True

    # ODRL properties
    odrl_type: str = "Permission"
    odrl_action: str = "transfer"
    odrl_target: str = "Data"


@dataclass
class AttributeRule:
    """
    SET 2B: Attribute-Level Rule Definition

    Rules that apply based on specific data attributes (e.g., health data).
    These rules check for specific metadata/attribute matches.
    """
    rule_id: str
    name: str
    description: str
    priority: int

    # Attribute specification
    attribute_name: str  # e.g., "health_data", "financial_data"
    attribute_keywords: List[str] = field(default_factory=list)
    attribute_patterns: List[str] = field(default_factory=list)  # Regex patterns

    # Link to attribute config file (for complex detection)
    attribute_config_file: Optional[str] = None

    # Country restrictions
    origin_countries: Optional[FrozenSet[str]] = None
    origin_group: Optional[str] = None
    receiving_countries: Optional[FrozenSet[str]] = None
    receiving_group: Optional[str] = None

    # Outcome
    outcome: RuleOutcome = RuleOutcome.PROHIBITION

    # Additional conditions
    requires_pii: bool = False

    # Rule status
    enabled: bool = True

    # ODRL properties
    odrl_type: str = "Prohibition"
    odrl_action: str = "transfer"
    odrl_target: str = "Data"


# =============================================================================
# SET 1: CASE-MATCHING RULES
# =============================================================================
# These rules require finding historical cases that match parameters.

CASE_MATCHING_RULES: Dict[str, CaseMatchingRule] = {
    # Rule 1: EU/EEA/UK/Crown/Switzerland Internal Transfers
    "RULE_1_EU_INTERNAL": CaseMatchingRule(
        rule_id="RULE_1",
        name="EU/EEA/UK/Crown/Switzerland Internal Transfers",
        description="Transfers within EU/EEA, UK, Crown Dependencies, and Switzerland require PIA completion",
        priority=10,
        origin_group="EU_EEA_UK_CROWN_CH",
        receiving_group="EU_EEA_UK_CROWN_CH",
        required_assessments=RequiredAssessments(pia_required=True),
    ),

    # Rule 2: EU/EEA to Adequacy Countries
    "RULE_2_EU_ADEQUACY": CaseMatchingRule(
        rule_id="RULE_2",
        name="EU/EEA to Adequacy Countries",
        description="Transfers from EU/EEA to adequacy countries require PIA completion",
        priority=20,
        origin_group="EU_EEA",
        receiving_group="ADEQUACY_COUNTRIES",
        required_assessments=RequiredAssessments(pia_required=True),
    ),

    # Rule 3: Crown Dependencies to Adequacy + EU/EEA
    "RULE_3_CROWN_ADEQUACY": CaseMatchingRule(
        rule_id="RULE_3",
        name="Crown Dependencies to Adequacy + EU/EEA",
        description="Transfers from Crown Dependencies to adequacy countries or EU/EEA require PIA",
        priority=30,
        origin_group="CROWN_DEPENDENCIES",
        receiving_group="ADEQUACY_PLUS_EU",
        required_assessments=RequiredAssessments(pia_required=True),
    ),

    # Rule 4: UK to Adequacy + EU/EEA
    "RULE_4_UK_ADEQUACY": CaseMatchingRule(
        rule_id="RULE_4",
        name="UK to Adequacy + EU/EEA",
        description="Transfers from UK to adequacy countries or EU/EEA require PIA",
        priority=40,
        origin_countries=frozenset({"United Kingdom"}),
        receiving_group="ADEQUACY_PLUS_EU",
        required_assessments=RequiredAssessments(pia_required=True),
    ),

    # Rule 5: Switzerland to Approved Countries
    "RULE_5_SWITZERLAND": CaseMatchingRule(
        rule_id="RULE_5",
        name="Switzerland to Approved Countries",
        description="Transfers from Switzerland to approved jurisdictions require PIA",
        priority=50,
        origin_countries=frozenset({"Switzerland"}),
        receiving_group="SWITZERLAND_APPROVED",
        required_assessments=RequiredAssessments(pia_required=True),
    ),

    # Rule 6: EU/EEA/Adequacy/UK to Rest of World
    "RULE_6_REST_OF_WORLD": CaseMatchingRule(
        rule_id="RULE_6",
        name="EU/EEA/Adequacy/UK to Rest of World",
        description="Transfers to non-adequacy countries require PIA and TIA",
        priority=60,
        origin_group="EU_EEA_ADEQUACY_UK",
        receiving_not_in=frozenset({"EU_EEA_ADEQUACY_UK"}),  # Marker: not in this group
        required_assessments=RequiredAssessments(pia_required=True, tia_required=True),
    ),

    # Rule 7: BCR Countries to Any
    "RULE_7_BCR": CaseMatchingRule(
        rule_id="RULE_7",
        name="BCR Countries Transfer",
        description="Transfers from BCR countries require PIA and HRPR",
        priority=70,
        origin_group="BCR_COUNTRIES",
        receiving_countries=None,  # Any country
        required_assessments=RequiredAssessments(pia_required=True, hrpr_required=True),
    ),

    # Rule 8: Any transfer with Personal Data
    "RULE_8_PERSONAL_DATA": CaseMatchingRule(
        rule_id="RULE_8",
        name="Personal Data Transfer",
        description="Any transfer with personal data requires PIA",
        priority=80,
        origin_countries=None,  # Any
        receiving_countries=None,  # Any
        requires_personal_data=True,
        required_assessments=RequiredAssessments(pia_required=True),
    ),
}


# =============================================================================
# SET 2A: TRANSFER RULES
# =============================================================================
# Country-to-country transfer permissions/prohibitions

TRANSFER_RULES: Dict[str, TransferRule] = {
    # US to Restricted Countries (PII)
    "RULE_9_US_RESTRICTED_PII": TransferRule(
        rule_id="RULE_9",
        name="US PII to Restricted Countries",
        description="Transfer of PII from US to restricted countries is prohibited",
        priority=1,  # Highest priority
        origin_group=None,
        receiving_group="US_RESTRICTED",
        transfer_pairs=[
            ("United States", "China"),
            ("United States", "Hong Kong"),
            ("United States", "Macao"),
            ("United States", "Cuba"),
            ("United States", "Iran"),
            ("United States", "North Korea"),
            ("United States", "Russia"),
            ("United States", "Venezuela"),
            ("United States of America", "China"),
            ("United States of America", "Hong Kong"),
            ("United States of America", "Macao"),
            ("United States of America", "Cuba"),
            ("United States of America", "Iran"),
            ("United States of America", "North Korea"),
            ("United States of America", "Russia"),
            ("United States of America", "Venezuela"),
        ],
        outcome=RuleOutcome.PROHIBITION,
        requires_pii=True,
        required_actions=["Obtain Legal Exemption", "Document Business Justification"],
        odrl_type="Prohibition",
        odrl_target="PII",
    ),

    # US to China Cloud Storage (Any Data)
    "RULE_10_US_CHINA_CLOUD": TransferRule(
        rule_id="RULE_10",
        name="US to China Cloud Storage",
        description="Cloud storage of any data from US in China/HK/Macao is prohibited",
        priority=1,
        transfer_pairs=[
            ("United States", "China"),
            ("United States", "Hong Kong"),
            ("United States", "Macao"),
            ("United States of America", "China"),
            ("United States of America", "Hong Kong"),
            ("United States of America", "Macao"),
        ],
        outcome=RuleOutcome.PROHIBITION,
        requires_any_data=True,
        required_actions=["Obtain Regional CTO Approval", "Alternative Storage Location Required"],
        odrl_type="Prohibition",
        odrl_action="store",
        odrl_target="Data",
    ),

    # Example: EU to Russia (sanctions)
    "RULE_EU_RUSSIA": TransferRule(
        rule_id="RULE_EU_RUSSIA",
        name="EU to Russia Data Transfer",
        description="Data transfers from EU to Russia are restricted",
        priority=2,
        origin_group="EU_EEA",
        receiving_countries=frozenset({"Russia"}),
        outcome=RuleOutcome.PROHIBITION,
        requires_any_data=True,
        required_actions=["Sanctions Compliance Check", "Legal Review Required"],
        odrl_type="Prohibition",
        enabled=True,
    ),
}


# =============================================================================
# SET 2B: ATTRIBUTE RULES
# =============================================================================
# Attribute-level rules based on data characteristics

ATTRIBUTE_RULES: Dict[str, AttributeRule] = {
    # US Health Data Transfer Prohibition
    "RULE_11_US_HEALTH": AttributeRule(
        rule_id="RULE_11",
        name="US Health Data Transfer",
        description="Transfer of US health data is restricted",
        priority=1,
        attribute_name="health_data",
        attribute_config_file="health_data_config.json",
        origin_countries=frozenset({"United States", "United States of America"}),
        receiving_countries=None,  # Any country
        outcome=RuleOutcome.PROHIBITION,
        requires_pii=False,  # Applies even without PII flag
        odrl_target="HealthData",
    ),

    # General Health Data Transfer (Any Origin)
    "RULE_HEALTH_GENERAL": AttributeRule(
        rule_id="RULE_HEALTH_GEN",
        name="General Health Data Transfer",
        description="Transfer of health-related data requires review",
        priority=10,
        attribute_name="health_data",
        attribute_keywords=[
            "patient", "medical", "health", "diagnosis", "treatment",
            "hospital", "clinical", "disease", "medication", "prescription"
        ],
        origin_countries=None,  # Any origin
        receiving_countries=None,  # Any destination
        outcome=RuleOutcome.PROHIBITION,
        requires_pii=False,  # Applies even without PII flag
        odrl_target="HealthData",
        enabled=True,
    ),

    # Financial Data to High Risk Jurisdictions
    "RULE_FINANCIAL_HIGH_RISK": AttributeRule(
        rule_id="RULE_FIN_01",
        name="Financial Data to High Risk Jurisdictions",
        description="Financial data transfer to high-risk jurisdictions requires additional controls",
        priority=5,
        attribute_name="financial_data",
        attribute_keywords=[
            "bank_account", "credit_card", "financial", "payment",
            "transaction", "balance", "loan", "mortgage", "investment"
        ],
        origin_countries=None,
        receiving_countries=frozenset({"Cuba", "Iran", "North Korea", "Syria", "Venezuela"}),
        outcome=RuleOutcome.PROHIBITION,
        requires_pii=False,  # Financial data itself is sensitive
        odrl_target="FinancialData",
        enabled=True,
    ),

    # Biometric Data
    "RULE_BIOMETRIC": AttributeRule(
        rule_id="RULE_BIO_01",
        name="Biometric Data Transfer",
        description="Biometric data transfers require special handling",
        priority=3,
        attribute_name="biometric_data",
        attribute_keywords=[
            "fingerprint", "facial_recognition", "retina", "iris",
            "voice_print", "dna", "biometric"
        ],
        origin_countries=None,
        receiving_countries=None,
        outcome=RuleOutcome.PROHIBITION,
        requires_pii=False,  # Biometric is inherently PII
        odrl_target="BiometricData",
        enabled=True,
    ),
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_all_rules() -> Dict[str, Any]:
    """Get all rules organized by type"""
    return {
        "case_matching": CASE_MATCHING_RULES,
        "transfer": TRANSFER_RULES,
        "attribute": ATTRIBUTE_RULES,
    }


def get_enabled_case_matching_rules() -> Dict[str, CaseMatchingRule]:
    """Get only enabled case-matching rules"""
    return {k: v for k, v in CASE_MATCHING_RULES.items() if v.enabled}


def get_enabled_transfer_rules() -> Dict[str, TransferRule]:
    """Get only enabled transfer rules"""
    return {k: v for k, v in TRANSFER_RULES.items() if v.enabled}


def get_enabled_attribute_rules() -> Dict[str, AttributeRule]:
    """Get only enabled attribute rules"""
    return {k: v for k, v in ATTRIBUTE_RULES.items() if v.enabled}


def get_rules_by_priority() -> List[Tuple[str, Any]]:
    """Get all enabled rules sorted by priority (ascending)"""
    all_rules = []

    for rule_id, rule in get_enabled_case_matching_rules().items():
        all_rules.append((rule_id, rule, RuleType.CASE_MATCHING))

    for rule_id, rule in get_enabled_transfer_rules().items():
        all_rules.append((rule_id, rule, RuleType.TRANSFER))

    for rule_id, rule in get_enabled_attribute_rules().items():
        all_rules.append((rule_id, rule, RuleType.ATTRIBUTE))

    # Sort by priority (lower = higher priority)
    return sorted(all_rules, key=lambda x: x[1].priority)
