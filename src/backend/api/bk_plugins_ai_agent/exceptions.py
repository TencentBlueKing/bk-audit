from blueapps.core.exceptions import BlueException
from django.utils.translation import gettext_lazy

from api.constants import AIAgentCode


class AgentRateLimited(BlueException):
    """Agent 全局配额暂不可用，可由 HTTP 或异步任务边界分别处理。"""

    ERROR_CODE = "429"
    STATUS_CODE = 429
    MESSAGE = gettext_lazy("AI 服务请求过于频繁，请稍后重试")

    def __init__(self, agent_code: AIAgentCode, retry_after: float | None = None):
        """记录限流维度和可选重试时间，不携带请求正文。"""

        self.agent_code = AIAgentCode(agent_code)
        self.retry_after = retry_after
        data = {"agent_code": self.agent_code.value}
        if retry_after is not None:
            data["retry_after"] = retry_after
        super().__init__(data=data)
