"""
Rule Analyzer Executor
=======================
Chain of Thought reasoning to extract rule structure from text.
Implements Google A2A SDK AgentExecutor interface.
"""

import logging
import time

from pydantic import ValidationError

from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueue

from agents.executors.base_executor import ComplianceAgentExecutor, InProcessRequestContext
from agents.executors.utils import parse_json_response
from agents.prompts.analyzer_prompts import (
    RULE_ANALYZER_SYSTEM_PROMPT,
    RULE_ANALYZER_USER_TEMPLATE,
)
from agents.prompts.prompt_builder import build_analyzer_prompt, build_country_groups_context
from agents.audit.event_types import AuditEventType
from agents.nodes.validation_models import RuleDefinitionModel
from agents.ai_service import AIRequestError

logger = logging.getLogger(__name__)


class RuleAnalyzerExecutor(ComplianceAgentExecutor):
    """Rule analyzer agent executor - extracts rule structure via CoT."""

    agent_name = "rule_analyzer"

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        ctx: InProcessRequestContext = context
        state = ctx.state
        start_time = time.time()
        session_id = state.get("origin_country", "unknown")

        await self.emit_working(event_queue, ctx)

        self.event_store.append(
            session_id=session_id,
            event_type=AuditEventType.AGENT_INVOKED,
            agent_name=self.agent_name,
        )

        system_prompt = RULE_ANALYZER_SYSTEM_PROMPT.format(
            country_groups=build_country_groups_context()
        )

        user_prompt = build_analyzer_prompt(
            template=RULE_ANALYZER_USER_TEMPLATE,
            rule_text=state["rule_text"],
            origin_country=state["origin_country"],
            receiving_countries=state["receiving_countries"],
            scenario_type=state["scenario_type"],
            data_categories=state["data_categories"],
            feedback="",
        )

        try:
            response = self.ai_service.chat(user_prompt, system_prompt)
            parsed = parse_json_response(response)

            if parsed:
                state["analysis_result"] = parsed.get("chain_of_thought", {})

                rule_def = parsed.get("rule_definition", {})
                try:
                    validated = RuleDefinitionModel(**rule_def)
                    state["rule_definition"] = validated.model_dump()
                    state["current_phase"] = (
                        "data_dictionary" if state["data_categories"] else "cypher_generator"
                    )

                    duration = (time.time() - start_time) * 1000
                    self.event_store.append(
                        session_id=session_id,
                        event_type=AuditEventType.RULE_ANALYZED,
                        agent_name=self.agent_name,
                        data={"rule_id": rule_def.get("rule_id")},
                        duration_ms=duration,
                    )
                    logger.info(f"Rule analyzed: {rule_def.get('rule_id')}")

                except ValidationError as ve:
                    errors = [str(e) for e in ve.errors()]
                    state["current_phase"] = "supervisor"
                    self.event_store.append(
                        session_id=session_id,
                        event_type=AuditEventType.AGENT_FAILED,
                        agent_name=self.agent_name,
                        error=f"Validation errors: {errors}",
                    )
                    logger.warning(f"Rule validation failed: {errors}")
            else:
                state["current_phase"] = "supervisor"
                self.event_store.append(
                    session_id=session_id,
                    event_type=AuditEventType.AGENT_FAILED,
                    agent_name=self.agent_name,
                    error="Failed to parse response",
                )

        except AIRequestError as e:
            logger.error(f"Rule analyzer error: {e}")
            state["current_phase"] = "supervisor"
            self.event_store.append(
                session_id=session_id,
                event_type=AuditEventType.AGENT_FAILED,
                agent_name=self.agent_name,
                error=str(e),
            )

        await self.emit_completed(event_queue, ctx)
