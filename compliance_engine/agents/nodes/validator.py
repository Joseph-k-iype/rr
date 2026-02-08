"""
Validator Node
===============
Thin shim: wraps ValidatorExecutor as a LangGraph node function.
Injects DatabaseService for FalkorDB test queries.
"""

from agents.executors.validator_executor import ValidatorExecutor
from agents.executors.base_executor import wrap_executor_as_node
from services.database import get_db_service

_executor = ValidatorExecutor(db_service=get_db_service())
validator_node = wrap_executor_as_node(_executor)
