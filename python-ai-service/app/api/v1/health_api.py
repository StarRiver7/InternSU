"""健康检查 API。

【API 端点】
  GET /ai/health      - 服务健康状态检查
  GET /ai/health/llm  - LLM 连接健康检查

【设计用途】
  - /health: 用于 Kubernetes/Docker 健康探针，快速判断服务是否正常运行
  - /health/llm: 用于检查 LLM 网关连接状态，验证模型服务可用性

【响应格式】
  /health:
    {
      "status": "healthy",      # healthy/unhealthy
      "service": "...",         # 服务名称
      "timestamp": "..."        # ISO 8601 时间戳
    }
  
  /health/llm:
    {
      "llm": "ok/error",        # LLM 状态
      "model": "...",           # 模型名称（成功时）
      "response": "..."         # 响应预览（成功时）
      "detail": "..."           # 错误详情（失败时）
    }
"""

from fastapi import APIRouter
from datetime import datetime

router = APIRouter(prefix="/ai", tags=["Health"])


@router.get("/health")
async def health():
    """服务健康状态检查。

    【用途】
      Kubernetes/Docker 健康探针端点，用于判断服务是否正常运行。
    
    【响应】
      status: healthy（服务正常）
      service: 服务标识
      timestamp: 当前时间

    Returns:
        健康状态字典
    """
    return {
        "status": "healthy",
        "service": "ai-agent-python-service",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/health/llm")
async def health_llm():
    """LLM 连接健康检查。

    【用途】
      验证 LLM 网关是否能正常连接到后端模型服务。
      通过发送简短测试消息（"hi"）验证连接和响应能力。

    【响应】
      成功: {"llm": "ok", "model": "<模型名>", "response": "<响应预览>"}
      失败: {"llm": "error", "detail": "<错误信息>"}

    Returns:
        LLM 健康状态字典
    """
    try:
        from app.llm.gateway import llm_gateway
        resp = await llm_gateway.chat([{"role": "user", "content": "hi"}], max_tokens=10)
        return {"llm": "ok", "model": str(resp.model), "response": resp.content[:50]}
    except Exception as e:
        return {"llm": "error", "detail": str(e)}
