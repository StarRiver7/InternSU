"""SQL Agent API -- deprecated.

v4: Schema / Tables / SQL execution all handled by Java direct MySQL.
Python side only keeps sql_node (LangGraph internal), no SQL HTTP endpoints.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/ai/sql", tags=["SQL Agent"])