"""Tests for SQL Agent components: trace, memory, schema loader, summarizer, sql_node integration."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestSQLTrace:
    def test_trace_step_running(self):
        from app.sql_agent.sql_trace import trace_step
        step = trace_step('sql_generator', '正在生成SQL...', '进行中')
        assert step['node'] == 'sql_generator'
        assert step['status'] == '进行中'
        assert 'timestamp' in step
        assert 'duration_ms' not in step

    def test_trace_step_completed(self):
        from app.sql_agent.sql_trace import trace_step
        step = trace_step('sql_generator', 'SQL生成完成', '已完成',
                           detail={'sql': 'SELECT'}, duration_ms=150)
        assert step['status'] == '已完成'
        assert step['detail']['sql'] == 'SELECT'
        assert step['duration_ms'] == 150

    def test_trace_step_failed(self):
        from app.sql_agent.sql_trace import trace_step
        step = trace_step('sql_executor', '执行失败', '失败', detail={'error': 'timeout'})
        assert step['status'] == '失败'
        assert step['detail']['error'] == '超时'

    def test_trace_messages_all_present(self):
        from app.sql_agent.sql_trace import SQL_TRACE_MESSAGES
        assert len(SQL_TRACE_MESSAGES) >= 12
        assert "sql_generation" in SQL_TRACE_MESSAGES
        assert "sql_security" in SQL_TRACE_MESSAGES
        assert "sql_execution" in SQL_TRACE_MESSAGES
        assert "sql_summarize" in SQL_TRACE_MESSAGES

class TestSQLMemory:
    def test_extract_sql_context(self):
        from app.sql_agent.sql_memory import sql_memory_helper
        slots = {"department": "技术部", "time_range": "本月", "other": "x"}
        ctx = sql_memory_helper.extract_sql_context(slots)
        assert ctx["department"] == "技术部"
        assert ctx["time_range"] == "本月"
        assert "other" not in ctx

    def test_merge_sql_context(self):
        from app.sql_agent.sql_memory import sql_memory_helper
        current = {"department": "技术部"}
        saved = {"department": "旧部门", "time_range": "上月"}
        merged = sql_memory_helper.merge_sql_context(current, saved)
        assert merged["department"] == "技术部"  # current wins
        assert merged["time_range"] == "上月"    # filled from saved

    def test_build_context_hint(self):
        from app.sql_agent.sql_memory import sql_memory_helper
        ctx = {"department": "技术部", "time_range": "最近7天"}
        hint = sql_memory_helper.build_context_hint(ctx)
        assert "技术部" in hint
        assert "最近7天" in hint

    def test_build_context_hint_empty(self):
        from app.sql_agent.sql_memory import sql_memory_helper
        hint = sql_memory_helper.build_context_hint({})
        assert hint == ''

class TestSchemaLoader:
    def test_static_fallback_has_tables(self):
        from app.sql_agent.schema_loader import schema_loader
        tables = schema_loader._static_fallback()
        assert 't_user' in tables
        assert 't_department' in tables
        assert 't_knowledge_space' in tables
        assert len(tables) == 8

    def test_build_context(self):
        from app.sql_agent.schema_loader import schema_loader
        tables = schema_loader._static_fallback()
        ctx = schema_loader.build_context(tables, ['t_user'])
        assert 't_user' in ctx
        assert 'id' in ctx
        assert 'username' in ctx
        assert 'password' not in ctx  # excluded

    def test_get_join_hints(self):
        from app.sql_agent.schema_loader import schema_loader
        hints = schema_loader.get_join_hints()
        assert 't_user.department_id' in hints
        assert 't_department.id' in hints

    @pytest.mark.asyncio
    async def test_get_schema_context_uses_fallback(self):
        from app.sql_agent.schema_loader import schema_loader
        from app.sql_agent.schema_cache import schema_cache
        schema_cache.invalidate()
        ctx = await schema_loader.get_schema_context()
        assert 't_user' in ctx
        assert '表关联提示' in ctx

class TestSQLSummarizer:
    def test_fallback_summary_zero_rows(self):
        from app.sql_agent.sql_summarizer import sql_summarizer
        summary = sql_summarizer._fallback_summary(0, [])
        assert "收到老师" in summary
        assert "没有找到" in summary

    def test_fallback_summary_with_rows(self):
        from app.sql_agent.sql_summarizer import sql_summarizer
        summary = sql_summarizer._fallback_summary(42, ['col1'])
        assert "收到老师" in summary
        assert "42" in summary
        assert "只读查询" in summary

class TestSQLNodeGraph:
    def test_graph_has_sql_node(self):
        from app.graph.intern_graph import intern_graph
        nodes = list(intern_graph.graph.nodes)
        assert 'sql_node' in nodes

    def test_router_routes_sql_to_sql_node(self):
        from app.graph.edges.routes import route_after_router
        from app.graph.state import InternState, create_initial_state
        state = create_initial_state("u1", "c1", "test")
        state["intent"] = "sql"
        result = route_after_router(state)
        assert result == "sql_node"

    def test_router_routes_chat_to_chat_node(self):
        from app.graph.edges.routes import route_after_router
        from app.graph.state import InternState, create_initial_state
        state = create_initial_state("u1", "c1", "test")
        state["intent"] = "chat"
        result = route_after_router(state)
        assert result == "chat_node"
