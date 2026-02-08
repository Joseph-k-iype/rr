"""
Reference Data Node
====================
Thin shim: wraps ReferenceDataExecutor as a LangGraph node function.
Injects DatabaseService for FalkorDB group lookup.
"""

from agents.executors.reference_data_executor import ReferenceDataExecutor
from agents.executors.base_executor import wrap_executor_as_node
from services.database import get_db_service

_executor = ReferenceDataExecutor(db_service=get_db_service())
reference_data_node = wrap_executor_as_node(_executor)
