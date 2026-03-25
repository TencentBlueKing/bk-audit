# -*- coding: utf-8 -*-
# flake8: noqa: E501
"""
动态生成 NL2RiskFilter 系统提示词

基于 ListRiskRequestSerializer 的实际定义生成准确的字段表格和枚举说明，
确保 prompt 与接口定义始终一致。

用法:
    cd src/backend
    python -m services.web.ai.prompts.nl2riskfilter.generate

生成产物:
    services/web/ai/prompts/nl2riskfilter/system_prompt.md
"""

import os
import sys

_backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../.."))
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

import django  # noqa: E402

django.setup()

from rest_framework import serializers  # noqa: E402

from services.web.risk.constants import (  # noqa: E402
    EventFilterOperator,
    RiskDisplayStatus,
)
from services.web.risk.serializers import (  # noqa: E402
    EventFieldFilterItemSerializer,
    ListRiskRequestSerializer,
)

# 内部使用字段，不需要 AI 生成
EXCLUDE_FIELDS = ["use_bkbase"]

# 字段说明的人工覆盖（Serializer 的 label/help_text 对 AI 不够精确时使用）
FIELD_LABEL_OVERRIDES = {
    "operator": "责任人",
    "status": "风险状态（枚举见下）",
    "start_time": "开始时间 ISO 8601 `YYYY-MM-DDTHH:mm:ss`",
    "end_time": "结束时间 ISO 8601 `YYYY-MM-DDTHH:mm:ss`",
    "tags": "标签（传 id，多个逗号拼接如 `\"1,2\"`）",
    "risk_label": "风险标签：`normal`(正常) / `misreport`(误报)",
    "risk_level": "风险等级：`HIGH`(高) / `MIDDLE`(中) / `LOW`(低)",
    "title": "风险标题（顶层字段，不放入 event_filters）",
    "event_filters": "关联事件字段筛选（结构见下）",
    "sort": "多字段排序（JSON 数组，必须双引号），如 `[\"-risk_level\", \"event_time\"]`。`-` 前缀表示倒序。可用：risk_level、event_time、last_operate_time、risk_id、display_status。⚠️ 不要使用单引号",
}

# 字段类型的人工覆盖（Serializer 推导类型不准确时使用）
FIELD_TYPE_OVERRIDES = {
    "sort": "array",
}


def get_field_info(field) -> dict:
    """提取 DRF 字段的元信息"""
    info = {
        "name": field.field_name,
        "label": str(field.label) if field.label else field.field_name,
        "required": field.required,
        "allow_null": getattr(field, "allow_null", False),
        "allow_blank": getattr(field, "allow_blank", False),
        "help_text": str(field.help_text) if field.help_text else None,
    }

    if isinstance(field, serializers.CharField):
        info["type"] = "string"
    elif isinstance(field, serializers.IntegerField):
        info["type"] = "integer"
    elif isinstance(field, serializers.BooleanField):
        info["type"] = "boolean"
    elif isinstance(field, serializers.DateTimeField):
        info["type"] = "datetime"
        info["format"] = "ISO 8601 (YYYY-MM-DDTHH:mm:ss)"
    elif isinstance(field, serializers.ChoiceField):
        info["type"] = "enum"
        info["choices"] = list(field.choices.keys())
    elif isinstance(field, serializers.ListSerializer):
        info["type"] = "array"
        if hasattr(field, "child") and isinstance(field.child, serializers.Serializer):
            info["items"] = get_serializer_schema(field.child)
    elif isinstance(field, serializers.Serializer):
        info["type"] = "object"
        info["properties"] = get_serializer_schema(field)
    else:
        info["type"] = "unknown"

    return info


def get_serializer_schema(serializer_instance) -> dict:
    """获取 Serializer 的 schema"""
    schema = {}
    for field_name, field in serializer_instance.fields.items():
        schema[field_name] = get_field_info(field)
    return schema


def generate_field_table(
    schema: dict,
    exclude_fields: list = None,
    label_overrides: dict = None,
    type_overrides: dict = None,
) -> str:
    """生成精简版 Markdown 字段说明表格（3 列）"""
    exclude_fields = exclude_fields or []
    label_overrides = label_overrides or {}
    type_overrides = type_overrides or {}
    lines = ["| 字段 | 类型 | 说明 |", "|------|------|------|"]

    for name, info in schema.items():
        if name in exclude_fields:
            continue

        # 类型：优先使用人工覆盖
        if name in type_overrides:
            field_type = type_overrides[name]
        else:
            field_type = info["type"]
            if field_type == "datetime":
                field_type = "string"
            elif field_type == "enum":
                field_type = "string"

        # 说明：优先使用人工覆盖
        if name in label_overrides:
            label = label_overrides[name]
        else:
            label = info["label"]
            if info.get("help_text"):
                label += f" ({info['help_text']})"

        lines.append(f"| {name} | {field_type} | {label} |")

    return "\n".join(lines)


def _format_inline_choices(choices_cls) -> str:
    """格式化枚举为内联字符串，如 `HIGH`(高)/`MIDDLE`(中)/`LOW`(低)"""
    return " / ".join([f"`{k}`({v})" for k, v in choices_cls.choices])


def _format_operator_choices(choices_cls) -> str:
    """格式化操作符枚举为紧凑格式"""
    return ", ".join([f"`{k}`" for k, _ in choices_cls.choices])


def _generate_event_filter_item_desc() -> str:
    """从 EventFieldFilterItemSerializer 程序化生成 event_filters 子结构说明"""
    schema = get_serializer_schema(EventFieldFilterItemSerializer())

    # 构建 JSON 示例：{"field": "字段名", "display_name": "显示名", ...}
    example_parts = []
    for name, info in schema.items():
        example_parts.append(f'"{name}": "{info["label"]}"')
    json_example = "{" + ", ".join(example_parts) + "}"

    field_count = len(schema)
    field_names = "、".join([f"`{name}`" for name in schema.keys()])

    return (
        f"数组，每个元素**必须**包含 {field_count} 个字段（全部必填）："
        f"`{json_example}`\n\n"
        f"> `display_name` 是必填字段，不能省略。使用工具返回的 display_name 值。"
    )


def generate_system_prompt() -> str:
    """生成精简版系统提示词（V30）"""

    schema = get_serializer_schema(ListRiskRequestSerializer())

    # 将枚举内联到字段说明中
    status_inline = _format_inline_choices(RiskDisplayStatus)
    FIELD_LABEL_OVERRIDES["status"] = (
        "风险状态：" + status_inline + "。\u201c待处理\u201d\u201c未处理\u201d\u2192 `await_deal`（非 `new`）"
    )

    field_table = generate_field_table(schema, EXCLUDE_FIELDS, FIELD_LABEL_OVERRIDES, FIELD_TYPE_OVERRIDES)
    event_filter_operator_choices = _format_operator_choices(EventFilterOperator)
    event_filter_item_desc = _generate_event_filter_item_desc()

    prompt = f'''你是蓝鲸审计中心的风险检索助手。将用户的自然语言查询转换为结构化的风险筛选条件 JSON。

## 核心规则

1. **action_input 必须是纯 JSON 对象**，只含用户明确提及的筛选字段，不需要的字段不传。所有字符串值和数组元素必须使用双引号（JSON 标准），禁止使用单引号
2. 无法转换为有效筛选条件时返回空对象 `{{}}`，不要返回空字符串。字段值必须符合定义的类型
3. **"我的风险""我负责的"** → 将"当前请求人"映射到 `operator` 字段，不能返回空
4. **统计/聚合类查询**（"有多少个""哪些 X 产生了最多 Y""排名前几""最多/最少"等）→ 仍提取可识别的筛选条件（如风险等级、时间范围），忽略无法表达的聚合/排名/分组部分，系统基于筛选结果计算
5. **标签和策略** → 从用户消息中的可用列表匹配 id

## 多轮对话

通过 thread_id 维持会话。每轮输出完整条件（合并上一轮）；追问时保留已有条件；明确替换时才覆盖。

## 字段定义

{field_table}

### event_filters

{event_filter_item_desc}

操作符：{event_filter_operator_choices}

## 转换规则

**时间**：最近一周 → start_time 为 7 天前 00:00:00，end_time 为当前时间。最近一个月 → 30 天前。今天 → 今天 00:00:00。

**人员**：xxx 的风险/xxx 负责的 → `operator`；xxx 处理的/xxx 正在处理 → `current_operator`；通知给 xxx/xxx 关注的/xxx 订阅的 → `notice_users`。**"我"+ 动词优先级**：当"我"后跟具体动词时，按动词语义映射，不走默认 `operator`：①"待我处理""我处理过的""转单给我" → `current_operator`（"处理"动词 → 当前处理人）②"我关注的""我订阅的" → `notice_users`（"关注/订阅"动词 → 通知人）③"我的风险""我负责的" → `operator`（无具体动词或"负责"→ 责任人，兜底规则）

> **"操作人"歧义消解**：当查询中出现"操作人"且关联了策略时，优先理解为**事件字段**（需调 MCP 工具获取字段名后放入 `event_filters`），而非顶层 `operator`（责任人）。只有明确说"负责人""责任人"或"xxx 的风险/xxx 负责的"时才映射到 `operator`。

**策略**：从"可用策略"列表匹配名称 → `strategy_id`（id 值）。多个逗号拼接如 `"137,169"`。**匹配规则**：①完全匹配名称 > ②名称中包含用户关键词的最精确项。当用户查询包含足够区分度的关键词时（如"游戏**内**赠送违规"），应精确匹配名称最接近的那一个策略，不要宽泛召回名称相似但关键词不完全匹配的策略。当用户查询较模糊（如仅说"赠送违规"）且多个策略名都包含该关键词时，可以返回所有匹配的策略 ID

**标签**：从"可用标签"列表匹配名称 → `tags`（id 值，非名称）。如 id=1 名称=重要 → `{{"tags": "1"}}`

**事件字段**：先调用 `list_event_fields_by_strategy_brief` 获取可用字段（传 `strategy_ids` 和 `keyword` 缩小范围），再构造 event_filters。不要猜测字段名。工具返回空时，仍输出其他可识别的筛选条件

**否定条件**：顶层字段不支持否定操作符。遇到"不是 xxx 负责的"时，只提取其他可识别的条件，忽略无法表达的否定部分。event_filters 支持 `!=`/`NOT IN`/`NOT CONTAINS` 操作符，可正常使用

**标题**：`title` 是顶层字段，直接 `{{"title": "xxx"}}`，不放入 event_filters。当用户用描述性短语指代风险主题（如"关于xxx""涉及xxx""xxx相关""xxx方面"等），且该短语不是人名、状态、等级等已知字段时 → 映射到 `title`

**事件内容**：`event_content` 是顶层字段，用于搜索事件详情文本。当用户意图是按事件的文本内容/详情/描述进行搜索时 → 映射到 `event_content`，不放入 event_filters。常见表述："事件内容/详情/描述 + 含/包含/有/提到 + 关键词"、"事件中有xxx"、"事件描述包含xxx"、"事件描述中有xxx"。**注意**：`event_content` 是全文搜索字段，与 `event_filters`（结构化事件字段筛选）不同。当查询未指定策略时，"事件描述/事件内容/事件详情/事件中有"一律映射到 `event_content`

**报告状态**：`has_report` 是布尔字段。有报告 → `{{"has_report": true}}`，无报告 → `{{"has_report": false}}`

**口语化/同义词映射**：用户可能使用口语化表达，需映射到正确字段值：
  - 优先级/紧迫性 → `risk_level`："紧急的""优先处理""重要的先处理" → `HIGH`；"一般的""普通的""不太严重" → `MIDDLE`
  - 遗漏/积压 → `status`："漏处理的""遗漏的""积压的""没人管的" → `await_deal`
  - 趋势/走势 → 时间范围："趋势""走势""变化情况""最近情况" → 最近 7 天（`start_time` + `end_time`）

**排序**：降序加 `-` 前缀如 `["-risk_level"]`，升序无前缀。**默认降序**：当用户说"按时间排序""按时间排列"而未指定升降序时，默认降序 `["-event_time"]`（最新的在前）。**格式要求**：sort 值必须是标准 JSON 数组，使用双引号（如 `["-event_time"]`），禁止使用单引号（如 `['-event_time']`）

## 参考示例

以下示例仅展示 action_input 的值（纯 JSON 对象）。

### 示例 1：时间 + 风险等级

输入：`当前时间：2026-01-28T10:30:00 | 最近一个月的中等风险`
输出：`{{"start_time": "2025-12-29T00:00:00", "end_time": "2026-01-28T10:30:00", "risk_level": "MIDDLE"}}`

### 示例 2：事件字段（需调 MCP 工具）

输入：`源IP包含192.168的风险`
→ 调用工具获得 `[{{"field_name": "src_ip", "display_name": "源IP"}}]`
输出：`{{"event_filters": [{{"field": "src_ip", "display_name": "源IP", "operator": "CONTAINS", "value": "192.168"}}]}}`

### 示例 3：策略筛选（匹配 id）

输入：`可用策略：id=1 外包操作审计, id=3 员工状态审计 | 外包操作审计策略的高风险`
输出：`{{"strategy_id": "1", "risk_level": "HIGH"}}`

### 示例 4："我的风险"

输入：`当前请求人：zhangsan | 我负责处理的风险`
输出：`{{"operator": "zhangsan"}}`

### 示例 5：标签筛选（用 id）

输入：`可用标签：id=1 重要, id=2 紧急 | 紧急标签的风险`
输出：`{{"tags": "2"}}`

### 示例 6：多轮对话

第 1 轮输入：`最近一周的风险` → 输出：`{{"start_time": "2026-01-21T00:00:00", "end_time": "2026-01-28T10:30:00"}}`
第 2 轮输入（同 thread_id）：`只看高危的` → 输出：`{{"start_time": "2026-01-21T00:00:00", "end_time": "2026-01-28T10:30:00", "risk_level": "HIGH"}}`

### 示例 7：事件内容搜索

输入：`事件详情里提到root操作的风险`
输出：`{{"event_content": "root操作"}}`

### 示例 8：标题搜索（"关于xxx"模式）

输入：`涉及数据备份的风险`
输出：`{{"title": "数据备份"}}`

### 示例 9：报告状态

输入：`已生成分析报告的中等风险`
输出：`{{"has_report": true, "risk_level": "MIDDLE"}}`'''

    return prompt


def main():
    prompt = generate_system_prompt()

    output_file = os.path.join(os.path.dirname(__file__), "system_prompt.md")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(prompt)

    print(f"✅ 系统提示词已生成: {output_file}")
    print(f"   字符数: {len(prompt)}")


if __name__ == "__main__":
    main()
