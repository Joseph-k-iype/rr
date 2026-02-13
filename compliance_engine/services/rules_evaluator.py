"""
Rules Evaluation Service
========================
Core engine for evaluating rules via FalkorDB graph queries.
The RulesGraph is the single source of truth.

Evaluates case-matching rules (precedent-based) against the graph.
Supports legal entity matching, case-insensitive country matching,
prohibition logic (any prohibition → overall PROHIBITION), and rule expiration.
"""

import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import date

from services.database import get_db_service
from services.cache import get_cache_service
from services.attribute_detector import (
    get_attribute_detector,
    AttributeDetectionConfig,
)
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


# ── FalkorDB-compatible Cypher queries ──────────────────────────────────────

# Case-matching rules: origin/receiving matching + assessment duties
# Uses case-insensitive CONTAINS matching for country names
# Checks rule expiration via valid_until property
CASE_MATCHING_RULES_QUERY = """
MATCH (r:Rule)
WHERE r.rule_type = 'case_matching' AND r.enabled = true
  AND (r.valid_until IS NULL OR r.valid_until >= $today)
OPTIONAL MATCH (r)-[:TRIGGERED_BY_ORIGIN]->(og:CountryGroup)<-[:BELONGS_TO]-(oc:Country)
  WHERE toLower(oc.name) CONTAINS toLower($origin)
OPTIONAL MATCH (r)-[:TRIGGERED_BY_ORIGIN]->(odc:Country)
  WHERE toLower(odc.name) CONTAINS toLower($origin)
WITH r, og, odc
WHERE r.origin_match_type = 'any' OR og IS NOT NULL OR odc IS NOT NULL
OPTIONAL MATCH (r)-[:TRIGGERED_BY_RECEIVING]->(rg:CountryGroup)<-[:BELONGS_TO]-(rc:Country)
  WHERE toLower(rc.name) CONTAINS toLower($receiving)
OPTIONAL MATCH (r)-[:TRIGGERED_BY_RECEIVING]->(rdc:Country)
  WHERE toLower(rdc.name) CONTAINS toLower($receiving)
WITH r, rg, rdc
WHERE r.receiving_match_type = 'any' OR rg IS NOT NULL OR rdc IS NOT NULL
OPTIONAL MATCH (r)-[:EXCLUDES_RECEIVING]->(eg:CountryGroup)<-[:BELONGS_TO]-(ec:Country)
  WHERE toLower(ec.name) CONTAINS toLower($receiving)
WITH DISTINCT r, eg
WHERE r.receiving_match_type <> 'not_in' OR eg IS NULL
WITH DISTINCT r
WHERE (r.requires_personal_data = false OR $has_personal_data = true)
  AND (r.has_pii_required = false OR $pii = true)
OPTIONAL MATCH (r)-[:HAS_PERMISSION]->(p:Permission)-[:CAN_HAVE_DUTY]->(d:Duty)
OPTIONAL MATCH (r)-[:HAS_PROHIBITION]->(pb:Prohibition)
RETURN DISTINCT
    r.rule_id AS rule_id, r.name AS name, r.description AS description,
    r.priority AS priority, r.priority_order AS priority_order,
    r.odrl_type AS odrl_type, r.outcome AS outcome,
    r.has_pii_required AS requires_pii,
    r.requires_personal_data AS requires_personal_data,
    r.origin_match_type AS origin_match_type,
    r.receiving_match_type AS receiving_match_type,
    r.required_actions AS required_actions,
    collect(DISTINCT d.module) AS required_assessments,
    collect(DISTINCT pb.name) AS prohibition_names
ORDER BY r.priority_order
"""


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
    origin_legal_entity: Optional[str] = None
    receiving_legal_entity: Optional[str] = None


class RulesEvaluator:
    """
    Graph-based rules evaluation engine.
    All rule matching is done via Cypher queries against the RulesGraph.
    """

    def __init__(self, rules_graph=None):
        self.db = get_db_service()
        self.cache = get_cache_service()
        self.attribute_detector = get_attribute_detector()
        self._rules_graph = rules_graph or self.db.get_rules_graph()

    def _graph_query(self, query: str, params: dict = None) -> list:
        """Execute a Cypher query against the rules graph."""
        try:
            result = self._rules_graph.query(query, params)
            if not hasattr(result, 'result_set') or not result.result_set:
                return []
            headers = result.header
            rows = []
            for row in result.result_set:
                row_dict = {}
                for i, header in enumerate(headers):
                    col_name = header[1] if isinstance(header, (list, tuple)) else header
                    row_dict[col_name] = row[i]
                rows.append(row_dict)
            return rows
        except Exception as e:
            logger.error(f"Graph query failed: {e}")
            return []

    # ─── Main evaluation entry ──────────────────────────────────────────

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
        origin_legal_entity: Optional[str] = None,
        receiving_legal_entity: Optional[str] = None,
    ) -> RulesEvaluationResponse:
        """Evaluate all applicable rules for a data transfer via graph queries."""
        start_time = time.time()

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
            origin_legal_entity=origin_legal_entity,
            receiving_legal_entity=receiving_legal_entity,
        )

        # Detect attributes for informational enrichment
        context.detected_attributes = self._detect_attributes(context)

        triggered_rules: List[TriggeredRule] = []
        consolidated_duties: List[str] = []

        # ── PHASE 1: Case-matching rules (graph query) ─────────────────
        case_rules = self._evaluate_case_matching_rules(context)

        if not case_rules:
            context_info = self._build_context_info(context)
            return RulesEvaluationResponse(
                transfer_status=TransferStatus.REQUIRES_REVIEW,
                origin_country=origin_country,
                receiving_country=receiving_country,
                pii=pii,
                triggered_rules=triggered_rules,
                detected_attributes=self._format_detected(context),
                message=f"REQUIRES REVIEW [{context_info}]: No applicable rules found. Please raise a governance ticket.",
                evaluation_time_ms=(time.time() - start_time) * 1000,
            )

        # ── Check for prohibition rules ──────────────────────────────
        has_prohibition = False
        prohibition_reasons = []
        for rule_row in case_rules:
            outcome = rule_row.get('outcome', 'permission')
            prohibition_names = rule_row.get('prohibition_names', [])
            if outcome == 'prohibition' or (prohibition_names and any(p for p in prohibition_names)):
                has_prohibition = True
                prohibition_reasons.append(
                    f"Rule '{rule_row.get('name', '')}' is a prohibition: {rule_row.get('description', '')}"
                )

        # ── PHASE 2: Search for precedent cases ───────────────────────
        required_assessments = self._get_required_assessments_from_graph(case_rules)
        precedent_result = self._search_precedent_cases(context, required_assessments)

        for rule_row in case_rules:
            triggered_rules.append(self._build_triggered_rule_from_row(rule_row, "case_matching"))
            for module in (rule_row.get('required_assessments') or []):
                if module:
                    consolidated_duties.append(module)

        # ── PHASE 3: Determine final status ───────────────────────────
        # If ANY triggered rule is a prohibition → overall PROHIBITION
        if has_prohibition:
            context_info = self._build_context_info(context)
            return RulesEvaluationResponse(
                transfer_status=TransferStatus.PROHIBITED,
                origin_country=origin_country,
                receiving_country=receiving_country,
                pii=pii,
                triggered_rules=triggered_rules,
                precedent_validation=precedent_result,
                detected_attributes=self._format_detected(context),
                consolidated_duties=list(set(consolidated_duties)),
                prohibition_reasons=prohibition_reasons,
                evidence_summary=precedent_result.evidence_summary if precedent_result else None,
                message=f"Transfer PROHIBITED [{context_info}]: One or more rules prohibit this transfer.",
                evaluation_time_ms=(time.time() - start_time) * 1000,
            )

        assessment_compliance = AssessmentCompliance(
            pia_required=required_assessments.get('pia', False),
            tia_required=required_assessments.get('tia', False),
            hrpr_required=required_assessments.get('hrpr', False),
        )

        if precedent_result.has_valid_precedent:
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
                detected_attributes=self._format_detected(context),
                consolidated_duties=list(set(consolidated_duties)),
                evidence_summary=precedent_result.evidence_summary,
                message=f"Transfer ALLOWED [{context_info}]: Precedent found with completed assessments.",
                evaluation_time_ms=(time.time() - start_time) * 1000,
            )

        # No valid precedent
        missing = []
        if required_assessments.get('pia') and not precedent_result.compliant_matches:
            missing.append('PIA'); assessment_compliance.pia_compliant = False
        if required_assessments.get('tia') and not precedent_result.compliant_matches:
            missing.append('TIA'); assessment_compliance.tia_compliant = False
        if required_assessments.get('hrpr') and not precedent_result.compliant_matches:
            missing.append('HRPR'); assessment_compliance.hrpr_compliant = False
        assessment_compliance.missing_assessments = missing

        context_info = self._build_context_info(context)
        status_msg = (
            f"Transfer PROHIBITED [{context_info}]: No precedent cases found. Please raise a governance ticket."
            if precedent_result.total_matches == 0
            else f"Transfer PROHIBITED [{context_info}]: Precedent cases found but missing required assessments: {', '.join(missing)}"
        )
        return RulesEvaluationResponse(
            transfer_status=TransferStatus.PROHIBITED,
            origin_country=origin_country,
            receiving_country=receiving_country,
            pii=pii,
            triggered_rules=triggered_rules,
            precedent_validation=precedent_result,
            assessment_compliance=assessment_compliance,
            detected_attributes=self._format_detected(context),
            consolidated_duties=list(set(consolidated_duties)),
            prohibition_reasons=(
                ["No precedent cases found matching criteria"]
                if precedent_result.total_matches == 0
                else [f"No precedent cases with completed {', '.join(missing)} assessments"]
            ),
            evidence_summary=precedent_result.evidence_summary,
            message=status_msg,
            evaluation_time_ms=(time.time() - start_time) * 1000,
        )

    # ─── Graph-based rule evaluation ────────────────────────────────────

    def _evaluate_case_matching_rules(self, context: EvaluationContext) -> list:
        """Query the RulesGraph for applicable case-matching rules."""
        today_str = date.today().isoformat()
        return self._graph_query(CASE_MATCHING_RULES_QUERY, {
            "origin": context.origin_country,
            "receiving": context.receiving_country,
            "pii": context.pii,
            "has_personal_data": bool(context.personal_data_names),
            "today": today_str,
        })

    # ─── Helpers ────────────────────────────────────────────────────────

    def _detect_attributes(self, context: EvaluationContext) -> list:
        combined_metadata = {
            **context.metadata,
            'personal_data_names': context.personal_data_names,
            'purposes': context.purposes,
        }
        if not combined_metadata:
            return []
        results = self.attribute_detector.detect(combined_metadata)
        return [r for r in results if r.detected]

    def _format_detected(self, context: EvaluationContext) -> List[DetectedAttribute]:
        return [
            DetectedAttribute(
                attribute_name=d.attribute_name,
                detection_method=d.detection_method,
                matched_terms=d.matched_terms,
                confidence=d.confidence,
            )
            for d in context.detected_attributes
        ]

    def _build_context_info(self, context: EvaluationContext) -> str:
        parts = [f"{context.origin_country} → {context.receiving_country}"]
        if context.pii:
            parts.append("PII=Yes")
        if context.origin_legal_entity:
            parts.append(f"Origin LE: {context.origin_legal_entity}")
        if context.receiving_legal_entity:
            parts.append(f"Receiving LE: {context.receiving_legal_entity}")
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

    def _get_required_assessments_from_graph(self, case_rules: list) -> Dict[str, bool]:
        required = {'pia': False, 'tia': False, 'hrpr': False}
        for row in case_rules:
            for module in (row.get('required_assessments') or []):
                key = str(module).lower()
                if key in required:
                    required[key] = True
        return required

    def _build_triggered_rule_from_row(self, row: dict, rule_type: str) -> TriggeredRule:
        """Build a TriggeredRule from a graph query result row."""
        outcome_str = row.get('outcome', 'permission')
        outcome = RuleOutcomeType.PROHIBITION if outcome_str == 'prohibition' else RuleOutcomeType.PERMISSION

        prohibitions = []
        permissions = []
        duties = []
        req_actions = row.get('required_actions') or []

        if isinstance(req_actions, str):
            req_actions = [req_actions] if req_actions else []

        for action in req_actions:
            duties.append(DutyInfo(
                duty_id=f"DUTY_{str(action).replace(' ', '_')}",
                name=str(action),
                module="action",
                value="required",
            ))

        # For case-matching rules, build duties from assessments
        if rule_type == 'case_matching':
            for module in (row.get('required_assessments') or []):
                if module:
                    duties.append(DutyInfo(
                        duty_id=f"DUTY_{module}",
                        name=f"Complete {module} Module",
                        module=str(module),
                        value="Completed",
                        description=f"Complete the {module} assessment before transfer",
                    ))

        if outcome_str == 'prohibition':
            # Prohibitions have NO duties
            prohibitions.append(ProhibitionInfo(
                prohibition_id=f"PROHIB_{row.get('rule_id')}",
                name=row.get('name', ''),
                description=row.get('description', ''),
            ))
        else:
            permissions.append(PermissionInfo(
                permission_id=f"PERM_{row.get('rule_id')}",
                name=row.get('name', ''),
                description=row.get('description', ''),
                duties=duties,
            ))

        return TriggeredRule(
            rule_id=str(row.get('rule_id', '')),
            rule_name=str(row.get('name', '')),
            rule_type=rule_type,
            priority=str(row.get('priority', 'medium')),
            origin_match_type=str(row.get('origin_match_type', 'any')),
            receiving_match_type=str(row.get('receiving_match_type', 'any')),
            odrl_type=str(row.get('odrl_type', 'Permission')),
            has_pii_required=bool(row.get('requires_pii', False)),
            description=str(row.get('description', '')),
            outcome=outcome,
            permissions=permissions,
            prohibitions=prohibitions,
            required_actions=req_actions,
            required_assessments=[str(m) for m in (row.get('required_assessments') or []) if m],
        )

    # ─── Precedent case search (already graph-based on DataTransferGraph) ───

    def _search_precedent_cases(
        self,
        context: EvaluationContext,
        required_assessments: Dict[str, bool],
    ) -> PrecedentValidation:
        match_parts = ["MATCH (c:Case)"]
        where_conditions = ["c.case_status IN ['Completed', 'Complete', 'Active', 'Published']"]
        params = {}
        applied_filters = []

        if context.origin_country:
            match_parts.append("MATCH (c)-[:ORIGINATES_FROM]->(origin:Country {name: $origin_country})")
            params["origin_country"] = context.origin_country
            applied_filters.append(f"origin={context.origin_country}")

        if context.receiving_country:
            match_parts.append("MATCH (c)-[:TRANSFERS_TO]->(receiving:Jurisdiction {name: $receiving_country})")
            params["receiving_country"] = context.receiving_country
            applied_filters.append(f"receiving={context.receiving_country}")

        if context.purposes:
            match_parts.append("MATCH (c)-[:HAS_PURPOSE]->(p:Purpose)")
            where_conditions.append("p.name IN $purposes")
            params["purposes"] = context.purposes
            applied_filters.append(f"purposes={context.purposes}")

        if context.process_l1:
            match_parts.append("MATCH (c)-[:HAS_PROCESS_L1]->(pl1:ProcessL1)")
            where_conditions.append("pl1.name IN $process_l1")
            params["process_l1"] = context.process_l1

        if context.process_l2:
            match_parts.append("MATCH (c)-[:HAS_PROCESS_L2]->(pl2:ProcessL2)")
            where_conditions.append("pl2.name IN $process_l2")
            params["process_l2"] = context.process_l2

        if context.process_l3:
            match_parts.append("MATCH (c)-[:HAS_PROCESS_L3]->(pl3:ProcessL3)")
            where_conditions.append("pl3.name IN $process_l3")
            params["process_l3"] = context.process_l3

        base_query = "\n".join(match_parts)
        if where_conditions:
            base_query += "\nWHERE " + " AND ".join(where_conditions)

        # Count total matches
        count_query = base_query + "\nRETURN count(c) as total"
        try:
            total_result = self.db.execute_data_query(count_query, params=params or None)
            total_matches = total_result[0].get('total', 0) if total_result else 0
        except Exception as e:
            logger.warning(f"Error counting precedent cases: {e}")
            total_matches = 0

        # Build compliant query with assessment filters
        assessment_conditions = []
        if required_assessments.get('pia'):
            assessment_conditions.append("c.pia_status = 'Completed'")
        if required_assessments.get('tia'):
            assessment_conditions.append("c.tia_status = 'Completed'")
        if required_assessments.get('hrpr'):
            assessment_conditions.append("c.hrpr_status = 'Completed'")

        if assessment_conditions:
            all_conditions = where_conditions + assessment_conditions
            compliant_query = "\n".join(match_parts)
            compliant_query += "\nWHERE " + " AND ".join(all_conditions)
        else:
            compliant_query = base_query

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

        # Build case matches
        matching_cases = []
        for row in compliant_result:
            case_data = row.get('c', {})
            if not case_data:
                continue
            case_purposes = [p for p in (row.get('purposes', []) or []) if p]
            case_l1 = [p for p in (row.get('process_l1', []) or []) if p]
            case_l2 = [p for p in (row.get('process_l2', []) or []) if p]
            case_l3 = [p for p in (row.get('process_l3', []) or []) if p]
            personal_data = [p for p in (row.get('personal_data_names', []) or []) if p]
            data_cats = [p for p in (row.get('data_categories', []) or []) if p]

            field_matches = self._compute_field_matches(
                context, case_purposes, case_l1, case_l2, case_l3, personal_data,
            )
            match_score = self._compute_match_score(field_matches)
            relevance = self._build_relevance_explanation(
                context, case_data, case_purposes, case_l1, match_score,
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

        matching_cases.sort(key=lambda c: c.match_score, reverse=True)
        compliant_count = len(matching_cases)
        evidence_summary = self._build_evidence_summary(
            context, matching_cases, total_matches, required_assessments,
        )
        filters_info = f" (filters: {', '.join(applied_filters)})" if applied_filters else ""
        msg = (
            f"Found {compliant_count} compliant case(s) out of {total_matches} total matches{filters_info}"
            if total_matches > 0
            else f"No matching cases found{filters_info}"
        )

        return PrecedentValidation(
            total_matches=total_matches,
            compliant_matches=compliant_count,
            has_valid_precedent=compliant_count > 0,
            matching_cases=matching_cases,
            evidence_summary=evidence_summary,
            message=msg,
        )

    # ─── Field matching helpers ─────────────────────────────────────────

    def _compute_field_matches(
        self, context, case_purposes, case_l1, case_l2, case_l3, case_pd,
    ) -> List[FieldMatch]:
        field_matches = [
            FieldMatch(field_name="origin_country", query_values=[context.origin_country],
                       case_values=[context.origin_country], match_type="exact", match_percentage=100.0),
            FieldMatch(field_name="receiving_country", query_values=[context.receiving_country],
                       case_values=[context.receiving_country], match_type="exact", match_percentage=100.0),
        ]
        for field_name, query_vals, case_vals in [
            ("purposes", context.purposes, case_purposes),
            ("process_l1", context.process_l1, case_l1),
            ("process_l2", context.process_l2, case_l2),
            ("process_l3", context.process_l3, case_l3),
            ("personal_data_names", context.personal_data_names, case_pd),
        ]:
            if query_vals:
                overlap = set(query_vals) & set(case_vals)
                pct = (len(overlap) / len(query_vals) * 100) if query_vals else 0
                mt = "exact" if pct == 100 else ("partial" if pct > 0 else "none")
                field_matches.append(FieldMatch(
                    field_name=field_name, query_values=query_vals,
                    case_values=case_vals, match_type=mt, match_percentage=round(pct, 1),
                ))
        return field_matches

    def _compute_match_score(self, field_matches: List[FieldMatch]) -> float:
        if not field_matches:
            return 1.0
        weights = {
            "origin_country": 0.25, "receiving_country": 0.25,
            "purposes": 0.15, "process_l1": 0.10,
            "process_l2": 0.08, "process_l3": 0.07,
            "personal_data_names": 0.10,
        }
        total_w = sum(weights.get(fm.field_name, 0.05) for fm in field_matches)
        weighted = sum(weights.get(fm.field_name, 0.05) * (fm.match_percentage / 100.0) for fm in field_matches)
        return round(weighted / total_w, 3) if total_w > 0 else 1.0

    def _build_relevance_explanation(self, context, case_data, case_purposes, case_l1, score) -> str:
        case_ref = case_data.get('case_ref_id', case_data.get('case_id', 'Unknown'))
        parts = [f"Case {case_ref} is a precedent for {context.origin_country} to {context.receiving_country} transfers"]
        assessments = [a for a in ['PIA', 'TIA', 'HRPR'] if case_data.get(f'{a.lower()}_status') == 'Completed']
        if assessments:
            parts.append(f"with completed {', '.join(assessments)} assessments")
        if context.purposes and case_purposes:
            overlap = set(context.purposes) & set(case_purposes)
            if overlap:
                parts.append(f"covering purposes: {', '.join(overlap)}")
        if score >= 0.9:
            parts.append("(strong match)")
        elif score >= 0.7:
            parts.append("(good match)")
        elif score >= 0.5:
            parts.append("(partial match)")
        return ". ".join(parts) + "."

    def _build_evidence_summary(self, context, matching_cases, total_matches, required_assessments) -> EvidenceSummary:
        if not matching_cases:
            return EvidenceSummary(
                total_cases_searched=total_matches, compliant_cases_found=0,
                confidence_level="low",
                evidence_narrative=f"No compliant precedent cases found for {context.origin_country} to {context.receiving_country} transfers.",
            )
        all_purposes = set()
        all_cats = set()
        best_score = 0.0
        best_id = None
        for c in matching_cases:
            all_purposes.update(c.purposes)
            all_cats.update(c.data_categories)
            if c.match_score > best_score:
                best_score = c.match_score
                best_id = c.case_ref_id or c.case_id
        assessment_coverage = {}
        for key in ['pia', 'tia', 'hrpr']:
            if required_assessments.get(key):
                n = sum(1 for c in matching_cases if getattr(c, f'{key}_status', None) == 'Completed')
                assessment_coverage[key.upper()] = f"{n}/{len(matching_cases)} cases completed"
        confidence = "high" if best_score >= 0.9 and len(matching_cases) >= 2 else ("medium" if best_score >= 0.7 else "low")
        parts = [f"Found {len(matching_cases)} compliant precedent case(s) out of {total_matches} total for {context.origin_country} to {context.receiving_country}."]
        if best_id:
            parts.append(f"Strongest precedent: case {best_id} with {best_score:.0%} match.")
        if all_purposes:
            parts.append(f"Covered purposes: {', '.join(sorted(all_purposes)[:5])}.")
        if assessment_coverage:
            parts.append("Assessment: " + "; ".join(f"{k}: {v}" for k, v in assessment_coverage.items()) + ".")
        return EvidenceSummary(
            total_cases_searched=total_matches, compliant_cases_found=len(matching_cases),
            strongest_match_score=best_score, strongest_match_case_id=best_id,
            common_purposes=sorted(all_purposes)[:10], common_data_categories=sorted(all_cats)[:10],
            assessment_coverage=assessment_coverage, confidence_level=confidence,
            evidence_narrative=" ".join(parts),
        )


# Singleton
_evaluator: Optional[RulesEvaluator] = None


def get_rules_evaluator() -> RulesEvaluator:
    global _evaluator
    if _evaluator is None:
        _evaluator = RulesEvaluator()
    return _evaluator
