"""
Validator Executor
===================
Validates rules, Cypher queries, and logical consistency.
Supports FalkorDB test queries in temporary graphs.
Implements Google A2A SDK AgentExecutor interface.
"""

import logging
import time

from pydantic import ValidationError

from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue

from agents.executors.base_executor import ComplianceAgentExecutor, InProcessRequestContext
from agents.executors.utils import parse_json_response
from agents.prompts.validator_prompts import (
    VALIDATOR_SYSTEM_PROMPT,
    VALIDATOR_USER_TEMPLATE,
)
from agents.prompts.prompt_builder import build_validator_prompt
from agents.audit.event_types import AuditEventType
from agents.nodes.validation_models import ValidationResultModel
from agents.ai_service import AIRequestError

logger = logging.getLogger(__name__)


class ValidatorExecutor(ComplianceAgentExecutor):
    """Validator agent executor - comprehensive validation with optional FalkorDB testing."""

    agent_name = "validator"

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        ctx: InProcessRequestContext = context
        state = ctx.state
        start_time = time.time()
        session_id = state.get("origin_country", "unknown")

        # Guard: cannot validate without rule_definition and cypher_queries
        if not state.get("rule_definition") or not state.get("cypher_queries"):
            state["current_phase"] = "supervisor"
            return

        await self.emit_working(event_queue, ctx)

        self.event_store.append(
            session_id=session_id,
            event_type=AuditEventType.AGENT_INVOKED,
            agent_name=self.agent_name,
        )

        user_prompt = build_validator_prompt(
            template=VALIDATOR_USER_TEMPLATE,
            rule_text=state["rule_text"],
            rule_definition=state["rule_definition"],
            cypher_queries=state["cypher_queries"],
            dictionary=state.get("dictionary_result"),
            iteration=state["iteration"],
            max_iterations=state["max_iterations"],
            previous_errors=[],
        )

        try:
            response = self.ai_service.chat(user_prompt, VALIDATOR_SYSTEM_PROMPT)
            parsed = parse_json_response(response)

            if parsed:
                val_results = parsed.get("validation_results", {})

                try:
                    validated = ValidationResultModel(
                        overall_valid=parsed.get("overall_valid", False),
                        confidence_score=parsed.get("confidence_score", 0.0),
                        rule_definition_valid=val_results.get("rule_definition", {}).get("valid", False),
                        cypher_valid=val_results.get("cypher_queries", {}).get("valid", False),
                        logical_valid=val_results.get("logical", {}).get("valid", False),
                        errors=sum([
                            val_results.get("rule_definition", {}).get("errors", []),
                            val_results.get("cypher_queries", {}).get("errors", []),
                            val_results.get("logical", {}).get("errors", []),
                        ], []),
                        warnings=sum([
                            val_results.get("rule_definition", {}).get("warnings", []),
                            val_results.get("cypher_queries", {}).get("warnings", []),
                            val_results.get("logical", {}).get("warnings", []),
                        ], []),
                        suggested_fixes=parsed.get("suggested_fixes", []),
                    )

                    state["validation_result"] = validated.model_dump()
                    duration = (time.time() - start_time) * 1000

                    # FalkorDB test queries in temp graph
                    if self.db_service and validated.overall_valid:
                        self._run_test_queries(state, session_id)

                    if validated.overall_valid and validated.confidence_score >= 0.7:
                        state["current_phase"] = "complete"
                        state["success"] = True
                        self.event_store.append(
                            session_id=session_id,
                            event_type=AuditEventType.VALIDATION_PASSED,
                            agent_name=self.agent_name,
                            data={"confidence": validated.confidence_score},
                            duration_ms=duration,
                        )
                        logger.info(f"Validation passed with confidence {validated.confidence_score}")
                    else:
                        state["iteration"] += 1
                        if state["iteration"] >= state["max_iterations"]:
                            state["current_phase"] = "fail"
                            state["error_message"] = f"Max iterations ({state['max_iterations']}) reached"
                        else:
                            state["current_phase"] = "supervisor"

                        self.event_store.append(
                            session_id=session_id,
                            event_type=AuditEventType.VALIDATION_FAILED,
                            agent_name=self.agent_name,
                            data={"errors": validated.errors, "fixes": validated.suggested_fixes},
                            duration_ms=duration,
                        )
                        logger.warning(f"Validation failed, iteration {state['iteration']}")

                except ValidationError as ve:
                    state["current_phase"] = "supervisor"
                    self.event_store.append(
                        session_id=session_id,
                        event_type=AuditEventType.AGENT_FAILED,
                        agent_name=self.agent_name,
                        error=str(ve),
                    )
            else:
                state["current_phase"] = "supervisor"

        except AIRequestError as e:
            logger.error(f"Validator error: {e}")
            state["current_phase"] = "supervisor"
            self.event_store.append(
                session_id=session_id,
                event_type=AuditEventType.AGENT_FAILED,
                agent_name=self.agent_name,
                error=str(e),
            )

        await self.emit_completed(event_queue, ctx)

    def _run_test_queries(self, state: dict, session_id: str):
        """Run validation queries in a temporary FalkorDB graph.

        Skips execution if queries contain $param placeholders since
        FalkorDB requires actual parameter values (not just placeholders).
        Structural validation is already done in cypher_generator_executor.
        """
        cypher_queries = state.get("cypher_queries", {}).get("queries", {})
        rule_insert = cypher_queries.get("rule_insert", "")
        validation_query = cypher_queries.get("validation", "")

        if not rule_insert or not validation_query:
            return

        # Skip if queries contain $param placeholders — FalkorDB EXPLAIN/query
        # requires actual values, not parameter placeholders
        if '$' in rule_insert or '$' in validation_query:
            logger.info("Skipping FalkorDB test: queries contain $param placeholders (structural validation already passed)")
            return

        temp_graph = None
        graph_name = None
        try:
            temp_graph, graph_name = self.db_service.get_temp_graph()

            # Insert rule into temp graph
            temp_graph.query(rule_insert)

            # Run validation query
            result = temp_graph.query(validation_query)
            logger.info(f"Test query returned {len(result.result_set) if hasattr(result, 'result_set') else 0} rows")

        except Exception as e:
            logger.warning(f"FalkorDB test query failed: {e}")
            self.event_store.append(
                session_id=session_id,
                event_type=AuditEventType.AGENT_FAILED,
                agent_name=self.agent_name,
                error=f"Test query failed: {e}",
            )
        finally:
            if graph_name:
                self.db_service.delete_temp_graph(graph_name)
