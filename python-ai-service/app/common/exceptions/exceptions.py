class AppException(Exception):
    def __init__(self, code: int, message: str, detail: str | None = None):
        self.code = code
        self.message = message
        self.detail = detail
        super().__init__(message)


class AIServiceException(AppException):
    def __init__(self, message: str = "AI service unavailable", detail: str | None = None):
        super().__init__(503, message, detail)


class LLMException(AppException):
    def __init__(self, message: str = "LLM call failed", detail: str | None = None):
        super().__init__(502, message, detail)


class InvalidConfigException(AppException):
    """配置异常 —— API Key 无效、Provider 不可用等。

    与 LLMException 的区别：
      - LLMException: 运行时调用失败（临时性，可重试）
      - InvalidConfigException: 配置级错误（永久性，不可重试，需人工修正）

    典型触发场景:
      - .env 中 API Key 为占位符（sk-your-key-here）
      - 启动探活返回 401 Unauthorized
      - 所有 Provider 均激活失败，无可用服务商
    """
    def __init__(self, message: str = "Invalid LLM configuration", detail: str | None = None):
        super().__init__(503, message, detail)


class RAGException(AppException):
    def __init__(self, message: str = "RAG pipeline error", detail: str | None = None):
        super().__init__(500, message, detail)


class ToolException(AppException):
    def __init__(self, message: str = "Tool execution failed", detail: str | None = None):
        super().__init__(500, message, detail)


class ValidationException(AppException):
    def __init__(self, message: str = "Validation error", detail: str | None = None):
        super().__init__(400, message, detail)
