from django.db.models import TextChoices
from django.utils.translation import gettext_lazy


class AIAgentCode(TextChoices):
    """AI 智能体标识；value 为默认 APIGW 网关名，新增 Agent 只需加一行。

    此模块不读取 Django settings，配置初始化阶段可安全导入。环境变量按枚举
    name 自动生效：

    - ``BKAPP_AI_{name}_API_URL``：完整 URL，优先级最高；
    - ``BKAPP_AI_{name}_APIGW_NAME``：覆盖默认网关名；
    - ``BKAPP_AI_{name}_APP_CODE``：per-agent 应用凭证，作用域与 URL 路由一致；
    - ``BKAPP_AI_{name}_SECRET_KEY``：per-agent 应用密钥。
    """

    AUDIT_REPORT = "bp-ai-audit-report", gettext_lazy("风险报告智能体")
    RISK_SEARCH = "bp-ai-aud-rsk-srch", gettext_lazy("风险检索助手")
    ALS_TITLE_SUM = "bp-ai-als-title-sum", gettext_lazy("AI 风险分析报告标题生成")
    AUDIT_ANALYSE = "bp-ai-audit-analyse", gettext_lazy("审计风险分析助手")
    USER_INTENT = "bp-ai-user-intent", gettext_lazy("用户意图识别智能体")
    AUDIT_LOG_STATISTICS = "bp-ai-log-stats", gettext_lazy("审计日志统计助手")
    AUDIT_LOG_ANALYSIS = "bp-ai-log-analyse", gettext_lazy("审计日志分析助手")
