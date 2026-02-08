"""
Cypher Generator Node
======================
Thin shim: wraps CypherGeneratorExecutor as a LangGraph node function.
Injects DatabaseService for FalkorDB syntax validation.
"""

from agents.executors.cypher_generator_executor import CypherGeneratorExecutor
from agents.executors.base_executor import wrap_executor_as_node
from services.database import get_db_service

_executor = CypherGeneratorExecutor(db_service=get_db_service())
cypher_generator_node = wrap_executor_as_node(_executor)
