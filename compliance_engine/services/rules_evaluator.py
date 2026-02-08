"""
Rules Evaluation Service
========================
Core engine for evaluating both sets of rules:
- SET 1: Case-matching rules (precedent-based)
- SET 2: Generic rules (transfer and attribute-based)
"""

import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

from rules.dictionaries.country_groups import (
    COUNTRY_GROUPS,
    is_country_in_group,
    get_country_group,
)
from rules.dictionaries.rules_definitions import (
    RuleType,
    RuleOutcome,
    CaseMatchingRule,
    TransferRule,
    AttributeRule,
    get_enabled_case_matching_rules,
    get_enabled_transfer_rules,
    get_enabled_attribute_rules,
)
from rules.templates.cypher_templates import (
    build_origin_filter,
    build_receiving_filter,
    build_purpose_filter,
    build_process_filter,
    build_pii_filter,
    build_assessment_filter,
)
from services.database import get_db_service
from services.cache import get_cache_service, cached
from services.attribute_detector import get_attribute_detector
from models.schemas import (
    TransferStatus,
    RuleOutcomeType,
    TriggeredRule,
    PermissionInfo,
    ProhibitionInfo,
    DutyInfo,
    CaseMatch,
    FieldMatch,
    PrecedentValidation,
    EvidenceSummary,
    AssessmentCompliance,
    DetectedAttribute,
    RulesEvaluationResponse,
)

logger = logging.getLogger(__name__)


@dataclass
class EvaluationContext:
    """Context for rule evaluation"""
    origin_country: str
    receiving_country: str
    pii: bool = False
    purposes: List[str] = field(default_factory=list)
    process_l1: List[str] = field(default_factory=list)
    process_l2: List[str] = field(default_factory=list)
    process_l3: List[str] = field(default_factory=list)
    personal_data_names: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    detected_attributes: List[DetectedAttribute] = field(default_factory=list)


class RulesEvaluator:
    """
    Main rules evaluation engine.

    Processes rules in priority order:
    1. Transfer prohibitions (highest priority country-specific rules)
    2. Attribute-based rules (e.g., health data restrictions)
    3. Case-matching rules (precedent validation)
    """

    def __init__(self, extra_transfer_rules=None, extra_attribute_rules=None):
        self.db = get_db_service()
        self.cache = get_cache_service()
        self.attribute_detector = get_attribute_detector()
        self._extra_transfer_rules = extra_transfer_rules or {}
        self._extra_attribute_rules = extra_attribute_rules or {}

    def evaluate(
        self,
        origin_country: str,
        receiving_country: str,
        pii: bool = False,
        purposes: Optional[List[str]] = None,
        process_l1: Optional[List[str]] = None,
        process_l2: Optional[List[str]] = None,
        process_l3: Optional[List[str]] = None,
        personal_data_names: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RulesEvaluationResponse:
        """
        Evaluate all applicable rules for a data transfer.

        All rules are evaluated and collected - multiple rules can trigger.
        Returns RulesEvaluationResponse with transfer status and details.
        """
        start_time = time.time()

        # Build evaluation context
        context = EvaluationContext(
            origin_country=origin_country,
            receiving_country=receiving_country,
            pii=pii,
            purposes=purposes or [],
            process_l1=process_l1 or [],
            process_l2=process_l2 or [],
            process_l3=process_l3 or [],
            personal_data_names=personal_data_names or [],
            metadata=metadata or {},
        )

        # Detect attributes from metadata
        context.detected_attributes = self._detect_attributes(context)

        # Initialize result containers
        triggered_rules: List[TriggeredRule] = []
        prohibition_reasons: List[str] = []
        consolidated_duties: List[str] = []
        required_actions: List[str] = []
        is_prohibited = False

        # =================================================================
        # PHASE 1: Check Transfer Rules (SET 2A - Highest Priority)
        # =================================================================
        transfer_result = self._evaluate_transfer_rules(context)
        if transfer_result:
            triggered_rules.extend(transfer_result.rules)
            prohibition_reasons.extend(transfer_result.prohibition_reasons)
            required_actions.extend(transfer_result.required_actions)
            if transfer_result.is_prohibited:
                is_prohibited = True

        # =================================================================
        # PHASE 2: Check Attribute Rules (SET 2B) - Always check these
        # =================================================================
        attribute_result = self._evaluate_attribute_rules(context)
        if attribute_result:
            triggered_rules.extend(attribute_result.rules)
            prohibition_reasons.extend(attribute_result.prohibition_reasons)
            required_actions.extend(attribute_result.required_actions)
            if attribute_result.is_prohibited:
                is_prohibited = True

        # =================================================================
        # If any prohibition found, return PROHIBITED with all triggered rules
        # =================================================================
        if is_prohibited:
            context_info = self._build_context_info(context)
            return RulesEvaluationResponse(
                transfer_status=TransferStatus.PROHIBITED,
                origin_country=origin_country,
                receiving_country=receiving_country,
                pii=pii,
                triggered_rules=triggered_rules,
                detected_attributes=[
                    DetectedAttribute(
                        attribute_name=d.attribute_name,
                        detection_method=d.detection_method,
                        matched_terms=d.matched_terms,
                        confidence=d.confidence
                    )
                    for d in context.detected_attributes
                ],
                prohibition_reasons=prohibition_reasons,
                required_actions=list(set(required_actions)),
                message=f"Transfer PROHIBITED [{context_info}]: {'; '.join(prohibition_reasons)}",
                evaluation_time_ms=(time.time() - start_time) * 1000
            )

        # =================================================================
        # PHASE 3: Find Applicable Case-Matching Rules (SET 1)
        # =================================================================
        applicable_rules = self._find_applicable_case_matching_rules(context)

        if not applicable_rules:
            # No rules apply - require review
            context_info = self._build_context_info(context)
            return RulesEvaluationResponse(
                transfer_status=TransferStatus.REQUIRES_REVIEW,
                origin_country=origin_country,
                receiving_country=receiving_country,
                pii=pii,
                triggered_rules=triggered_rules,
                detected_attributes=[
                    DetectedAttribute(
                        attribute_name=d.attribute_name,
                        detection_method=d.detection_method,
                        matched_terms=d.matched_terms,
                        confidence=d.confidence
                    )
                    for d in context.detected_attributes
                ],
                message=f"REQUIRES REVIEW [{context_info}]: No applicable rules found. Please raise a governance ticket.",
                evaluation_time_ms=(time.time() - start_time) * 1000
            )

        # =================================================================
        # PHASE 4: Search for Precedent Cases
        # =================================================================
        # Get required assessments from applicable rules
        required_assessments = self._get_required_assessments(applicable_rules)

        # Search for matching cases
        precedent_result = self._search_precedent_cases(context, required_assessments)

        # Build triggered rules from case-matching rules
        for rule in applicable_rules:
            triggered_rules.append(self._build_triggered_rule(rule))
            consolidated_duties.extend(rule.required_assessments.to_list())

        # =================================================================
        # PHASE 5: Determine Final Status
        # =================================================================
        assessment_compliance = AssessmentCompliance(
            pia_required=required_assessments.get('pia', False),
            tia_required=required_assessments.get('tia', False),
            hrpr_required=required_assessments.get('hrpr', False),
        )

        if precedent_result.has_valid_precedent:
            # Found compliant precedent case(s)
            assessment_compliance.pia_compliant = True
            assessment_compliance.tia_compliant = True
            assessment_compliance.hrpr_compliant = True
            assessment_compliance.all_compliant = True

            context_info = self._build_context_info(context)
            return RulesEvaluationResponse(
                transfer_status=TransferStatus.ALLOWED,
                origin_country=origin_country,
                receiving_country=receiving_country,
                pii=pii,
                triggered_rules=triggered_rules,
                precedent_validation=precedent_result,
                assessment_compliance=assessment_compliance,
                detected_attributes=[
                    DetectedAttribute(
                        attribute_name=d.attribute_name,
                        detection_method=d.detection_method,
                        matched_terms=d.matched_terms,
                        confidence=d.confidence
                    )
                    for d in context.detected_attributes
                ],
                consolidated_duties=list(set(consolidated_duties)),
                required_actions=list(set(required_actions)),
                evidence_summary=precedent_result.evidence_summary,
                message=f"Transfer ALLOWED [{context_info}]: Precedent found with completed assessments.",
                evaluation_time_ms=(time.time() - start_time) * 1000
            )

        # No valid precedent found
        missing = []
        if required_assessments.get('pia') and not precedent_result.compliant_matches:
            missing.append('PIA')
            assessment_compliance.pia_compliant = False
        if required_assessments.get('tia') and not precedent_result.compliant_matches:
            missing.append('TIA')
            assessment_compliance.tia_compliant = False
        if required_assessments.get('hrpr') and not precedent_result.compliant_matches:
            missing.append('HRPR')
            assessment_compliance.hrpr_compliant = False

        assessment_compliance.missing_assessments = missing

        context_info = self._build_context_info(context)

        if precedent_result.total_matches == 0:
            # No cases found at all
            return RulesEvaluationResponse(
                transfer_status=TransferStatus.PROHIBITED,
                origin_country=origin_country,
                receiving_country=receiving_country,
                pii=pii,
                triggered_rules=triggered_rules,
                precedent_validation=precedent_result,
                assessment_compliance=assessment_compliance,
                detected_attributes=[
                    DetectedAttribute(
                        attribute_name=d.attribute_name,
                        detection_method=d.detection_method,
                        matched_terms=d.matched_terms,
                        confidence=d.confidence
                    )
                    for d in context.detected_attributes
                ],
                consolidated_duties=list(set(consolidated_duties)),
                prohibition_reasons=["No precedent cases found matching criteria"],
                evidence_summary=precedent_result.evidence_summary,
                message=f"Transfer PROHIBITED [{context_info}]: No precedent cases found. Please raise a governance ticket.",
                evaluation_time_ms=(time.time() - start_time) * 1000
            )

        # Cases found but none compliant
        return RulesEvaluationResponse(
            transfer_status=TransferStatus.PROHIBITED,
            origin_country=origin_country,
            receiving_country=receiving_country,
            pii=pii,
            triggered_rules=triggered_rules,
            precedent_validation=precedent_result,
            assessment_compliance=assessment_compliance,
            detected_attributes=[
                DetectedAttribute(
                    attribute_name=d.attribute_name,
                    detection_method=d.detection_method,
                    matched_terms=d.matched_terms,
                    confidence=d.confidence
                )
                for d in context.detected_attributes
            ],
            consolidated_duties=list(set(consolidated_duties)),
            prohibition_reasons=[f"No precedent cases with completed {', '.join(missing)} assessments"],
            evidence_summary=precedent_result.evidence_summary,
            message=f"Transfer PROHIBITED [{context_info}]: Precedent cases found but missing required assessments: {', '.join(missing)}",
            evaluation_time_ms=(time.time() - start_time) * 1000
        )

    def _detect_attributes(self, context: EvaluationContext) -> List:
        """Detect attributes from context metadata"""
        results = []

        # Combine all metadata for detection
        combined_metadata = {
            **context.metadata,
            'personal_data_names': context.personal_data_names,
            'purposes': context.purposes,
        }

        if combined_metadata:
            detection_results = self.attribute_detector.detect(combined_metadata)
            for result in detection_results:
                if result.detected:
                    results.append(result)

        return results

    def _build_context_info(self, context: EvaluationContext) -> str:
        """Build a human-readable summary of the evaluation context"""
        parts = [f"{context.origin_country} → {context.receiving_country}"]

        if context.pii:
            parts.append("PII=Yes")
        if context.purposes:
            parts.append(f"Purposes: {', '.join(context.purposes)}")
        if context.process_l1:
            parts.append(f"L1: {', '.join(context.process_l1)}")
        if context.process_l2:
            parts.append(f"L2: {', '.join(context.process_l2)}")
        if context.process_l3:
            parts.append(f"L3: {', '.join(context.process_l3)}")
        if context.detected_attributes:
            attrs = [d.attribute_name for d in context.detected_attributes]
            parts.append(f"Detected: {', '.join(attrs)}")

        return " | ".join(parts)

    def _evaluate_transfer_rules(self, context: EvaluationContext) -> Optional['RuleEvaluationResult']:
        """Evaluate transfer rules (SET 2A)"""
        result = RuleEvaluationResult()
        transfer_rules = get_enabled_transfer_rules()
        if self._extra_transfer_rules:
            transfer_rules = {**transfer_rules, **self._extra_transfer_rules}

        for rule_id, rule in transfer_rules.items():
            if self._transfer_rule_matches(rule, context):
                triggered = self._build_triggered_rule_from_transfer(rule)
                result.rules.append(triggered)

                if rule.outcome == RuleOutcome.PROHIBITION:
                    result.is_prohibited = True
                    result.prohibition_reasons.append(rule.description)
                    result.required_actions.extend(rule.required_actions)

        return result if result.rules else None

    def _transfer_rule_matches(self, rule: TransferRule, context: EvaluationContext) -> bool:
        """Check if a transfer rule matches the context"""
        # Check PII requirement (skip if rule applies to any data)
        if rule.requires_pii and not rule.requires_any_data and not context.pii:
            return False

        origin_normalized = context.origin_country.strip()
        receiving_normalized = context.receiving_country.strip()

        # Check transfer pairs first - if defined, MUST match one pair
        if rule.transfer_pairs:
            pair_matched = False
            for origin, receiving in rule.transfer_pairs:
                if origin == origin_normalized and receiving == receiving_normalized:
                    pair_matched = True
                    break

            if not pair_matched and rule.bidirectional:
                for origin, receiving in rule.transfer_pairs:
                    if receiving == origin_normalized and origin == receiving_normalized:
                        pair_matched = True
                        break

            # If transfer_pairs defined but no match, rule doesn't apply
            if not pair_matched:
                return False

            # If pair matched, rule applies
            return True

        # No transfer_pairs defined - check country groups
        origin_matches = True
        receiving_matches = True

        # Check origin group/countries if specified
        if rule.origin_group:
            origin_group_countries = get_country_group(rule.origin_group)
            origin_matches = origin_normalized in origin_group_countries

        # Check receiving group/countries if specified
        if rule.receiving_group:
            receiving_group_countries = get_country_group(rule.receiving_group)
            receiving_matches = receiving_normalized in receiving_group_countries
        elif rule.receiving_countries:
            receiving_matches = receiving_normalized in rule.receiving_countries

        # Must have at least one constraint defined
        has_constraints = bool(rule.origin_group or rule.receiving_group or rule.receiving_countries)

        return has_constraints and origin_matches and receiving_matches

    def _evaluate_attribute_rules(self, context: EvaluationContext) -> Optional['RuleEvaluationResult']:
        """Evaluate attribute rules (SET 2B)"""
        result = RuleEvaluationResult()
        attribute_rules = get_enabled_attribute_rules()
        if self._extra_attribute_rules:
            attribute_rules = {**attribute_rules, **self._extra_attribute_rules}

        # Get detected attribute names
        detected_names = {d.attribute_name for d in context.detected_attributes}

        for rule_id, rule in attribute_rules.items():
            # Check if this attribute was detected
            if rule.attribute_name not in detected_names:
                continue

            # Check country restrictions
            if not self._attribute_rule_country_matches(rule, context):
                continue

            # Check PII requirement
            if rule.requires_pii and not context.pii:
                continue

            triggered = self._build_triggered_rule_from_attribute(rule)
            result.rules.append(triggered)

            if rule.outcome == RuleOutcome.PROHIBITION:
                result.is_prohibited = True
                result.prohibition_reasons.append(
                    f"{rule.description} (detected: {rule.attribute_name})"
                )

        return result if result.rules else None

    def _attribute_rule_country_matches(self, rule: AttributeRule, context: EvaluationContext) -> bool:
        """Check if an attribute rule's country restrictions match"""
        # Check origin
        if rule.origin_countries:
            if context.origin_country not in rule.origin_countries:
                return False
        elif rule.origin_group:
            if not is_country_in_group(context.origin_country, rule.origin_group):
                return False

        # Check receiving (if specified)
        if rule.receiving_countries:
            if context.receiving_country not in rule.receiving_countries:
                return False
        elif rule.receiving_group:
            if not is_country_in_group(context.receiving_country, rule.receiving_group):
                return False

        return True

    def _find_applicable_case_matching_rules(
        self,
        context: EvaluationContext
    ) -> List[CaseMatchingRule]:
        """Find all applicable case-matching rules (SET 1)"""
        applicable = []
        rules = get_enabled_case_matching_rules()

        for rule_id, rule in rules.items():
            if self._case_matching_rule_applies(rule, context):
                applicable.append(rule)

        # Sort by priority (lower = higher priority)
        applicable.sort(key=lambda r: r.priority)
        return applicable

    def _case_matching_rule_applies(self, rule: CaseMatchingRule, context: EvaluationContext) -> bool:
        """Check if a case-matching rule applies to the context"""
        # Check personal data requirement
        if rule.requires_personal_data and not context.personal_data_names:
            return False

        # Check PII requirement
        if rule.requires_pii and not context.pii:
            return False

        # Check origin country/group
        origin_matches = False
        if rule.origin_countries:
            origin_matches = context.origin_country in rule.origin_countries
        elif rule.origin_group:
            origin_group_countries = get_country_group(rule.origin_group)
            origin_matches = context.origin_country in origin_group_countries
        else:
            origin_matches = True  # Any origin

        if not origin_matches:
            return False

        # Check receiving country/group
        receiving_matches = False
        if rule.receiving_not_in:
            # Special handling for "not in" rules
            excluded_countries = set()
            for group_ref in rule.receiving_not_in:
                if group_ref in COUNTRY_GROUPS:
                    excluded_countries.update(get_country_group(group_ref))
                else:
                    excluded_countries.add(group_ref)
            receiving_matches = context.receiving_country not in excluded_countries
        elif rule.receiving_countries:
            receiving_matches = context.receiving_country in rule.receiving_countries
        elif rule.receiving_group:
            receiving_group_countries = get_country_group(rule.receiving_group)
            receiving_matches = context.receiving_country in receiving_group_countries
        else:
            receiving_matches = True  # Any receiving

        return receiving_matches

    def _get_required_assessments(self, rules: List[CaseMatchingRule]) -> Dict[str, bool]:
        """Get combined required assessments from applicable rules"""
        required = {'pia': False, 'tia': False, 'hrpr': False}

        for rule in rules:
            if rule.required_assessments.pia_required:
                required['pia'] = True
            if rule.required_assessments.tia_required:
                required['tia'] = True
            if rule.required_assessments.hrpr_required:
                required['hrpr'] = True

        return required

    def _search_precedent_cases(
        self,
        context: EvaluationContext,
        required_assessments: Dict[str, bool]
    ) -> PrecedentValidation:
        """Search for precedent cases matching the context"""
        # Build the search query using parameterized queries to prevent injection
        match_parts = ["MATCH (c:Case)"]
        where_conditions = ["c.case_status IN ['Completed', 'Complete', 'Active', 'Published']"]
        params = {}

        # Track which filters are applied for reporting
        applied_filters = []

        # Add origin filter
        if context.origin_country:
            match_parts.append(
                "MATCH (c)-[:ORIGINATES_FROM]->(origin:Country {name: $origin_country})"
            )
            params["origin_country"] = context.origin_country
            applied_filters.append(f"origin={context.origin_country}")

        # Add receiving filter
        if context.receiving_country:
            match_parts.append(
                "MATCH (c)-[:TRANSFERS_TO]->(receiving:Jurisdiction {name: $receiving_country})"
            )
            params["receiving_country"] = context.receiving_country
            applied_filters.append(f"receiving={context.receiving_country}")

        # Add purpose filter
        if context.purposes:
            match_parts.append(
                "MATCH (c)-[:HAS_PURPOSE]->(p:Purpose)"
            )
            where_conditions.append("p.name IN $purposes")
            params["purposes"] = context.purposes
            applied_filters.append(f"purposes={context.purposes}")

        # Add process L1 filter
        if context.process_l1:
            match_parts.append(
                "MATCH (c)-[:HAS_PROCESS_L1]->(pl1:ProcessL1)"
            )
            where_conditions.append("pl1.name IN $process_l1")
            params["process_l1"] = context.process_l1
            applied_filters.append(f"process_l1={context.process_l1}")

        # Add process L2 filter
        if context.process_l2:
            match_parts.append(
                "MATCH (c)-[:HAS_PROCESS_L2]->(pl2:ProcessL2)"
            )
            where_conditions.append("pl2.name IN $process_l2")
            params["process_l2"] = context.process_l2
            applied_filters.append(f"process_l2={context.process_l2}")

        # Add process L3 filter
        if context.process_l3:
            match_parts.append(
                "MATCH (c)-[:HAS_PROCESS_L3]->(pl3:ProcessL3)"
            )
            where_conditions.append("pl3.name IN $process_l3")
            params["process_l3"] = context.process_l3
            applied_filters.append(f"process_l3={context.process_l3}")

        # Build base query
        base_query = "\n".join(match_parts)
        if where_conditions:
            base_query += "\nWHERE " + " AND ".join(where_conditions)

        # First, get total matches
        count_query = base_query + "\nRETURN count(c) as total"
        try:
            total_result = self.db.execute_data_query(count_query, params=params or None)
            total_matches = total_result[0].get('total', 0) if total_result else 0
        except Exception as e:
            logger.warning(f"Error counting precedent cases: {e}")
            total_matches = 0

        # Add assessment requirements for compliant query
        assessment_conditions = []
        if required_assessments.get('pia'):
            assessment_conditions.append("c.pia_status = 'Completed'")
        if required_assessments.get('tia'):
            assessment_conditions.append("c.tia_status = 'Completed'")
        if required_assessments.get('hrpr'):
            assessment_conditions.append("c.hrpr_status = 'Completed'")

        # Build compliant query with full case details
        if assessment_conditions:
            all_conditions = where_conditions + assessment_conditions
            compliant_query = "\n".join(match_parts)
            compliant_query += "\nWHERE " + " AND ".join(all_conditions)
        else:
            compliant_query = base_query

        # Add OPTIONAL MATCHes to get related data for evidence
        compliant_query += """
OPTIONAL MATCH (c)-[:HAS_PURPOSE]->(purpose:Purpose)
OPTIONAL MATCH (c)-[:HAS_PROCESS_L1]->(proc_l1:ProcessL1)
OPTIONAL MATCH (c)-[:HAS_PROCESS_L2]->(proc_l2:ProcessL2)
OPTIONAL MATCH (c)-[:HAS_PROCESS_L3]->(proc_l3:ProcessL3)
OPTIONAL MATCH (c)-[:HAS_PERSONAL_DATA]->(pdn:PersonalData)
OPTIONAL MATCH (c)-[:HAS_PERSONAL_DATA_CATEGORY]->(dc:PersonalDataCategory)
WITH c,
     collect(DISTINCT purpose.name) as purposes,
     collect(DISTINCT proc_l1.name) as process_l1,
     collect(DISTINCT proc_l2.name) as process_l2,
     collect(DISTINCT proc_l3.name) as process_l3,
     collect(DISTINCT pdn.name) as personal_data_names,
     collect(DISTINCT dc.name) as data_categories
RETURN c, purposes, process_l1, process_l2, process_l3, personal_data_names, data_categories
LIMIT 10"""

        try:
            compliant_result = self.db.execute_data_query(compliant_query, params=params or None)
        except Exception as e:
            logger.warning(f"Error searching compliant cases: {e}")
            compliant_result = []

        # Build case matches with full evidence and field-level matching
        matching_cases = []
        for row in compliant_result:
            case_data = row.get('c', {})
            if case_data:
                case_purposes = [p for p in (row.get('purposes', []) or []) if p]
                case_l1 = [p for p in (row.get('process_l1', []) or []) if p]
                case_l2 = [p for p in (row.get('process_l2', []) or []) if p]
                case_l3 = [p for p in (row.get('process_l3', []) or []) if p]
                personal_data = [p for p in (row.get('personal_data_names', []) or []) if p]
                data_cats = [p for p in (row.get('data_categories', []) or []) if p]

                # Compute field-level match analysis
                field_matches = self._compute_field_matches(
                    context, case_purposes, case_l1, case_l2, case_l3, personal_data
                )

                # Compute match score from field matches
                match_score = self._compute_match_score(field_matches)

                # Build relevance explanation
                relevance = self._build_relevance_explanation(
                    context, case_data, case_purposes, case_l1, match_score
                )

                matching_cases.append(CaseMatch(
                    case_id=str(case_data.get('case_id', '')),
                    case_ref_id=str(case_data.get('case_ref_id', '')),
                    case_status=str(case_data.get('case_status', '')),
                    origin_country=context.origin_country,
                    receiving_country=context.receiving_country,
                    pia_status=case_data.get('pia_status'),
                    tia_status=case_data.get('tia_status'),
                    hrpr_status=case_data.get('hrpr_status'),
                    is_compliant=True,
                    purposes=case_purposes,
                    process_l1=case_l1,
                    process_l2=case_l2,
                    process_l3=case_l3,
                    personal_data_names=personal_data,
                    data_categories=data_cats,
                    created_date=case_data.get('created_date'),
                    last_updated=case_data.get('last_updated'),
                    match_score=match_score,
                    field_matches=field_matches,
                    relevance_explanation=relevance,
                ))

        # Sort by match score descending
        matching_cases.sort(key=lambda c: c.match_score, reverse=True)

        compliant_count = len(matching_cases)
        has_valid = compliant_count > 0

        # Build evidence summary
        evidence_summary = self._build_evidence_summary(
            context, matching_cases, total_matches, required_assessments
        )

        # Build message with applied filters info
        filters_info = f" (filters: {', '.join(applied_filters)})" if applied_filters else ""
        if total_matches > 0:
            msg = f"Found {compliant_count} compliant case(s) out of {total_matches} total matches{filters_info}"
        else:
            msg = f"No matching cases found{filters_info}"

        return PrecedentValidation(
            total_matches=total_matches,
            compliant_matches=compliant_count,
            has_valid_precedent=has_valid,
            matching_cases=matching_cases,
            evidence_summary=evidence_summary,
            message=msg
        )

    def _compute_field_matches(
        self,
        context: EvaluationContext,
        case_purposes: List[str],
        case_l1: List[str],
        case_l2: List[str],
        case_l3: List[str],
        case_personal_data: List[str],
    ) -> List[FieldMatch]:
        """Compute field-by-field match analysis between query and case"""
        field_matches = []

        # Country match (always exact since we filter)
        field_matches.append(FieldMatch(
            field_name="origin_country",
            query_values=[context.origin_country],
            case_values=[context.origin_country],
            match_type="exact",
            match_percentage=100.0,
        ))
        field_matches.append(FieldMatch(
            field_name="receiving_country",
            query_values=[context.receiving_country],
            case_values=[context.receiving_country],
            match_type="exact",
            match_percentage=100.0,
        ))

        # Purposes match
        if context.purposes:
            overlap = set(context.purposes) & set(case_purposes)
            pct = (len(overlap) / len(context.purposes) * 100) if context.purposes else 0
            match_type = "exact" if pct == 100 else ("partial" if pct > 0 else "none")
            field_matches.append(FieldMatch(
                field_name="purposes",
                query_values=context.purposes,
                case_values=case_purposes,
                match_type=match_type,
                match_percentage=round(pct, 1),
            ))

        # Process L1 match
        if context.process_l1:
            overlap = set(context.process_l1) & set(case_l1)
            pct = (len(overlap) / len(context.process_l1) * 100) if context.process_l1 else 0
            match_type = "exact" if pct == 100 else ("partial" if pct > 0 else "none")
            field_matches.append(FieldMatch(
                field_name="process_l1",
                query_values=context.process_l1,
                case_values=case_l1,
                match_type=match_type,
                match_percentage=round(pct, 1),
            ))

        # Process L2 match
        if context.process_l2:
            overlap = set(context.process_l2) & set(case_l2)
            pct = (len(overlap) / len(context.process_l2) * 100) if context.process_l2 else 0
            match_type = "exact" if pct == 100 else ("partial" if pct > 0 else "none")
            field_matches.append(FieldMatch(
                field_name="process_l2",
                query_values=context.process_l2,
                case_values=case_l2,
                match_type=match_type,
                match_percentage=round(pct, 1),
            ))

        # Process L3 match
        if context.process_l3:
            overlap = set(context.process_l3) & set(case_l3)
            pct = (len(overlap) / len(context.process_l3) * 100) if context.process_l3 else 0
            match_type = "exact" if pct == 100 else ("partial" if pct > 0 else "none")
            field_matches.append(FieldMatch(
                field_name="process_l3",
                query_values=context.process_l3,
                case_values=case_l3,
                match_type=match_type,
                match_percentage=round(pct, 1),
            ))

        # Personal data match
        if context.personal_data_names:
            overlap = set(context.personal_data_names) & set(case_personal_data)
            pct = (len(overlap) / len(context.personal_data_names) * 100) if context.personal_data_names else 0
            match_type = "exact" if pct == 100 else ("partial" if pct > 0 else "none")
            field_matches.append(FieldMatch(
                field_name="personal_data_names",
                query_values=context.personal_data_names,
                case_values=case_personal_data,
                match_type=match_type,
                match_percentage=round(pct, 1),
            ))

        return field_matches

    def _compute_match_score(self, field_matches: List[FieldMatch]) -> float:
        """Compute an overall match score from field-level matches"""
        if not field_matches:
            return 1.0

        # Weights for each field type
        weights = {
            "origin_country": 0.25,
            "receiving_country": 0.25,
            "purposes": 0.15,
            "process_l1": 0.10,
            "process_l2": 0.08,
            "process_l3": 0.07,
            "personal_data_names": 0.10,
        }

        total_weight = 0.0
        weighted_score = 0.0

        for fm in field_matches:
            weight = weights.get(fm.field_name, 0.05)
            total_weight += weight
            weighted_score += weight * (fm.match_percentage / 100.0)

        return round(weighted_score / total_weight, 3) if total_weight > 0 else 1.0

    def _build_relevance_explanation(
        self,
        context: EvaluationContext,
        case_data: Dict,
        case_purposes: List[str],
        case_l1: List[str],
        match_score: float,
    ) -> str:
        """Build a human-readable explanation of why this case is relevant"""
        parts = []
        case_ref = case_data.get('case_ref_id', case_data.get('case_id', 'Unknown'))

        parts.append(
            f"Case {case_ref} is a precedent for {context.origin_country} to "
            f"{context.receiving_country} transfers"
        )

        # Assessment status
        assessments = []
        if case_data.get('pia_status') == 'Completed':
            assessments.append('PIA')
        if case_data.get('tia_status') == 'Completed':
            assessments.append('TIA')
        if case_data.get('hrpr_status') == 'Completed':
            assessments.append('HRPR')

        if assessments:
            parts.append(f"with completed {', '.join(assessments)} assessments")

        # Purpose overlap
        if context.purposes and case_purposes:
            overlap = set(context.purposes) & set(case_purposes)
            if overlap:
                parts.append(f"covering purposes: {', '.join(overlap)}")

        # Process overlap
        if context.process_l1 and case_l1:
            overlap = set(context.process_l1) & set(case_l1)
            if overlap:
                parts.append(f"with matching processes: {', '.join(overlap)}")

        # Match confidence
        if match_score >= 0.9:
            parts.append("(strong match)")
        elif match_score >= 0.7:
            parts.append("(good match)")
        elif match_score >= 0.5:
            parts.append("(partial match)")

        return ". ".join(parts) + "."

    def _build_evidence_summary(
        self,
        context: EvaluationContext,
        matching_cases: List[CaseMatch],
        total_matches: int,
        required_assessments: Dict[str, bool],
    ) -> EvidenceSummary:
        """Build a consolidated evidence summary from all matching cases"""
        if not matching_cases:
            return EvidenceSummary(
                total_cases_searched=total_matches,
                compliant_cases_found=0,
                confidence_level="low",
                evidence_narrative=(
                    f"No compliant precedent cases found for "
                    f"{context.origin_country} to {context.receiving_country} transfers."
                ),
            )

        # Aggregate data from matching cases
        all_purposes = set()
        all_data_categories = set()
        best_score = 0.0
        best_case_id = None

        for case in matching_cases:
            all_purposes.update(case.purposes)
            all_data_categories.update(case.data_categories)
            if case.match_score > best_score:
                best_score = case.match_score
                best_case_id = case.case_ref_id or case.case_id

        # Assessment coverage
        assessment_coverage = {}
        if required_assessments.get('pia'):
            pia_complete = sum(1 for c in matching_cases if c.pia_status == 'Completed')
            assessment_coverage['PIA'] = f"{pia_complete}/{len(matching_cases)} cases completed"
        if required_assessments.get('tia'):
            tia_complete = sum(1 for c in matching_cases if c.tia_status == 'Completed')
            assessment_coverage['TIA'] = f"{tia_complete}/{len(matching_cases)} cases completed"
        if required_assessments.get('hrpr'):
            hrpr_complete = sum(1 for c in matching_cases if c.hrpr_status == 'Completed')
            assessment_coverage['HRPR'] = f"{hrpr_complete}/{len(matching_cases)} cases completed"

        # Determine confidence level
        if best_score >= 0.9 and len(matching_cases) >= 2:
            confidence = "high"
        elif best_score >= 0.7 or len(matching_cases) >= 1:
            confidence = "medium"
        else:
            confidence = "low"

        # Build narrative
        narrative_parts = [
            f"Found {len(matching_cases)} compliant precedent case(s) "
            f"out of {total_matches} total matching cases for "
            f"{context.origin_country} to {context.receiving_country} transfers."
        ]

        if best_case_id:
            narrative_parts.append(
                f"Strongest precedent: case {best_case_id} "
                f"with {best_score:.0%} match score."
            )

        if all_purposes:
            narrative_parts.append(
                f"Covered purposes include: {', '.join(sorted(all_purposes)[:5])}."
            )

        if assessment_coverage:
            coverage_str = "; ".join(
                f"{k}: {v}" for k, v in assessment_coverage.items()
            )
            narrative_parts.append(f"Assessment coverage: {coverage_str}.")

        return EvidenceSummary(
            total_cases_searched=total_matches,
            compliant_cases_found=len(matching_cases),
            strongest_match_score=best_score,
            strongest_match_case_id=best_case_id,
            common_purposes=sorted(all_purposes)[:10],
            common_data_categories=sorted(all_data_categories)[:10],
            assessment_coverage=assessment_coverage,
            confidence_level=confidence,
            evidence_narrative=" ".join(narrative_parts),
        )

    def _build_triggered_rule(self, rule: CaseMatchingRule) -> TriggeredRule:
        """Build TriggeredRule from CaseMatchingRule"""
        # Determine match types
        origin_match_type = "group" if rule.origin_group else ("specific" if rule.origin_countries else "any")
        receiving_match_type = "group" if rule.receiving_group else ("specific" if rule.receiving_countries else "any")

        duties = []
        for assessment in rule.required_assessments.to_list():
            duties.append(DutyInfo(
                duty_id=f"DUTY_{assessment}",
                name=f"Complete {assessment} Module",
                module=assessment,
                value="Completed",
                description=f"Complete the {assessment} assessment before transfer"
            ))

        return TriggeredRule(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            rule_type="case_matching",
            priority=rule.priority,
            origin_match_type=origin_match_type,
            receiving_match_type=receiving_match_type,
            odrl_type=rule.odrl_type,
            has_pii_required=rule.requires_pii,
            description=rule.description,
            outcome=RuleOutcomeType.PERMISSION,
            permissions=[PermissionInfo(
                permission_id=f"PERM_{rule.rule_id}",
                name=f"Transfer Permission ({rule.name})",
                duties=duties
            )],
            prohibitions=[],
            required_assessments=rule.required_assessments.to_list(),
        )

    def _build_triggered_rule_from_transfer(self, rule: TransferRule) -> TriggeredRule:
        """Build TriggeredRule from TransferRule"""
        # Determine match types
        origin_match_type = "group" if rule.origin_group else "specific"
        receiving_match_type = "group" if rule.receiving_group else "specific"

        outcome = (
            RuleOutcomeType.PROHIBITION
            if rule.outcome == RuleOutcome.PROHIBITION
            else RuleOutcomeType.PERMISSION
        )

        prohibitions = []
        permissions = []
        duties = []

        for action in rule.required_actions:
            duties.append(DutyInfo(
                duty_id=f"DUTY_{action.replace(' ', '_')}",
                name=action,
                module="action",
                value="required",
            ))

        if rule.outcome == RuleOutcome.PROHIBITION:
            prohibitions.append(ProhibitionInfo(
                prohibition_id=f"PROHIB_{rule.rule_id}",
                name=rule.name,
                description=rule.description,
                duties=duties,
            ))
        else:
            permissions.append(PermissionInfo(
                permission_id=f"PERM_{rule.rule_id}",
                name=rule.name,
                description=rule.description,
                duties=duties,
            ))

        return TriggeredRule(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            rule_type="transfer",
            priority=rule.priority,
            origin_match_type=origin_match_type,
            receiving_match_type=receiving_match_type,
            odrl_type=rule.odrl_type,
            has_pii_required=rule.requires_pii,
            description=rule.description,
            outcome=outcome,
            permissions=permissions,
            prohibitions=prohibitions,
            required_actions=rule.required_actions,
        )

    def _build_triggered_rule_from_attribute(self, rule: AttributeRule) -> TriggeredRule:
        """Build TriggeredRule from AttributeRule"""
        # Determine match types
        origin_match_type = "group" if rule.origin_group else ("specific" if rule.origin_countries else "any")
        receiving_match_type = "group" if rule.receiving_group else ("specific" if rule.receiving_countries else "any")

        outcome = (
            RuleOutcomeType.PROHIBITION
            if rule.outcome == RuleOutcome.PROHIBITION
            else RuleOutcomeType.PERMISSION
        )

        prohibitions = []
        if rule.outcome == RuleOutcome.PROHIBITION:
            prohibitions.append(ProhibitionInfo(
                prohibition_id=f"PROHIB_{rule.rule_id}",
                name=rule.name,
                description=rule.description,
            ))

        return TriggeredRule(
            rule_id=rule.rule_id,
            rule_name=rule.name,
            rule_type="attribute",
            priority=rule.priority,
            origin_match_type=origin_match_type,
            receiving_match_type=receiving_match_type,
            odrl_type=rule.odrl_type,
            has_pii_required=rule.requires_pii,
            description=rule.description,
            outcome=outcome,
            prohibitions=prohibitions,
        )


@dataclass
class RuleEvaluationResult:
    """Internal result container for rule evaluation"""
    rules: List[TriggeredRule] = field(default_factory=list)
    is_prohibited: bool = False
    prohibition_reasons: List[str] = field(default_factory=list)
    required_actions: List[str] = field(default_factory=list)


# Singleton evaluator
_evaluator: Optional[RulesEvaluator] = None


def get_rules_evaluator() -> RulesEvaluator:
    """Get the rules evaluator instance"""
    global _evaluator
    if _evaluator is None:
        _evaluator = RulesEvaluator()
    return _evaluator
