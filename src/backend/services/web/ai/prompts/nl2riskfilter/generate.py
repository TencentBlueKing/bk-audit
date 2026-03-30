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

from services.web.risk.constants import EventFilterOperator  # noqa: E402
from services.web.risk.serializers import (  # noqa: E402
    EventFieldFilterItemSerializer,
    ListRiskRequestSerializer,
)

# 内部使用字段，不需要 AI 生成
EXCLUDE_FIELDS = ["use_bkbase"]

# 字段说明的人工覆盖（仅当 Serializer 的 help_text 不够精确时使用；优先修改序列化器 help_text）
FIELD_LABEL_OVERRIDES = {}

# 字段类型的人工覆盖（Serializer 推导类型不准确时使用）
FIELD_TYPE_OVERRIDES = {}


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
    elif isinstance(field, serializers.ListField):
        info["type"] = "array"
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
        elif info.get("help_text"):
            # help_text 存在时优先使用，比英文 label 更适合 AI 理解
            label = info["help_text"]
        else:
            label = info["label"]

        lines.append(f"| {name} | {field_type} | {label} |")

    return "\n".join(lines)


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

以下为跨字段的全局规则，单字段的转换说明已包含在字段定义中。

**"我"+ 动词优先级**：当"我"后跟具体动词时，按动词语义映射，不走默认 `operator`：①"待我处理""我处理过的""转单给我" → `current_operator`（"处理"动词 → 当前处理人）②"我关注的""我订阅的" → `notice_users`（"关注/订阅"动词 → 通知人）③"我的风险""我负责的" → `operator`（无具体动词或"负责"→ 责任人，兜底规则）

> **"操作人"歧义消解**：当查询中出现"操作人"且关联了策略时，优先理解为**事件字段**（需调 MCP 工具获取字段名后放入 `event_filters`），而非顶层 `operator`（责任人）。只有明确说"负责人""责任人"或"xxx 的风险/xxx 负责的"时才映射到 `operator`。

**策略精确匹配**：当用户查询包含足够区分度的关键词时（如"游戏**内**赠送违规"），应精确匹配名称最接近的那一个策略，不要宽泛召回名称相似但关键词不完全匹配的策略。当用户查询较模糊（如仅说"赠送违规"）且多个策略名都包含该关键词时，可以返回所有匹配的策略 ID

**事件字段补充**：调用工具时传 `strategy_ids` 和 `keyword` 缩小范围。工具返回空时，仍输出其他可识别的筛选条件

**否定条件**：顶层字段不支持否定操作符。遇到"不是 xxx 负责的"时，只提取其他可识别的条件，忽略无法表达的否定部分。event_filters 支持 `!=`/`NOT IN`/`NOT CONTAINS` 操作符，可正常使用

**event_content 与 event_filters 区分**：常见表述"事件内容/详情/描述 + 含/包含/有/提到 + 关键词"→ `event_content`。当查询未指定策略时，"事件描述/事件内容/事件详情/事件中有"一律映射到 `event_content`

**口语化趋势映射**：用户说"趋势""走势""变化情况""最近情况" → 最近 7 天（`start_time` + `end_time`）

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
输出：`{{"has_report": true, "risk_level": "MIDDLE"}}`

### 示例 10：事件字段排序（event_data sort + event_filters 必须同时存在）

输入：`可用策略：id=50 数据导出审计 | 数据导出审计的风险，按操作耗时从高到低`
→ 调用工具获得 `[{{"field_name": "op_duration", "display_name": "操作耗时"}}]`
输出：`{{"strategy_id": "50", "sort": ["-event_data.op_duration"], "event_filters": [{{"field": "op_duration", "display_name": "操作耗时", "operator": ">=", "value": "0"}}]}}`

> ⚠️ 使用 `event_data.xxx` 排序时，**必须**同时在 `event_filters` 中包含该字段的筛选条件，否则后端校验失败。即使用户没有指定筛选值，也需要添加一个宽松条件（如 `>= 0`）来满足校验要求。

### 示例 11：事件字段否定条件（!= 操作符）

输入：`可用策略：id=80 服务器登录审计 | 服务器登录审计中访问来源不是内网的风险`
→ 调用工具获得 `[{{"field_name": "access_source", "display_name": "访问来源"}}]`
输出：`{{"strategy_id": "80", "event_filters": [{{"field": "access_source", "display_name": "访问来源", "operator": "!=", "value": "内网"}}]}}`

> 当用户使用"不是""非""排除""不包含"等否定词描述事件字段条件时，使用 `!=`/`NOT IN`/`NOT CONTAINS` 操作符。注意：否定操作符**仅适用于 event_filters**，顶层字段（如 operator、status）不支持否定。'''

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
