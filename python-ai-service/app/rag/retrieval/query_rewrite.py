"""查询重写 — 基于 LLM 的查询优化以提升检索效果。

将模糊的用户查询转换为搜索优化形式。
通过现有的 LLM 网关使用 DeepSeek LLM。

示例:
  "请假制度" → "公司员工请假制度 年假 调休 病假 规则"
  "报销" → "费用报销流程 差旅报销 审批规则 发票要求"
"""

from app.llm.gateway import llm_gateway
from app.core.logger import get_logger

logger = get_logger(__name__)

REWRITE_PROMPT = """You are a search query optimizer. Your task is to rewrite a user's search query to improve retrieval quality.

Rules:
1. Expand abbreviations and vague terms into specific keywords
2. Add synonyms and related terms
3. Keep the original intent
4. Return ONLY the rewritten query, no explanations
5. Keep it under 200 characters
6. Use Chinese when the query is in Chinese

User query: {query}

Rewritten query:"""


class QueryRewriter:
    """基于 LLM 的查询重写器，用于提升检索召回率。"""

    def __init__(self, model: str = "deepseek-chat"):
        self._model = model

    async def rewrite(self, query: str) -> str:
        """重写用户查询以优化检索。

        如果 LLM 失败或查询已经具体，则返回原始查询。
        """
        if not query or len(query.strip()) < 3:
            return query

        # Skip rewrite for already-specific queries (>30 chars likely specific)
        if len(query) > 50:
            return query

        try:
            prompt = REWRITE_PROMPT.format(query=query)
            rewritten = await llm_gateway.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self._model,
                max_tokens=100,
                temperature=0.3,
            )
            rewritten = rewritten.strip().strip('"').strip("'")
            if rewritten and len(rewritten) >= len(query):
                logger.debug(f"[QueryRewrite] '{query}' → '{rewritten}'")
                return rewritten
        except Exception as e:
            logger.warning(f"[QueryRewrite] LLM 重写失败: {e}")

        return query

    async def rewrite_with_keywords(self, query: str) -> dict:
        """重写查询并提取独立关键词。

        返回 {"rewritten": str, "keywords": [str]}
        """
        rewritten = await self.rewrite(query)

        # Simple keyword extraction
        import re
        keywords = list(set(
            kw.strip() for kw in re.split(r"[，,、\s]+", rewritten)
            if len(kw.strip()) >= 2
        ))

        return {"rewritten": rewritten, "keywords": keywords}


query_rewriter = QueryRewriter()
