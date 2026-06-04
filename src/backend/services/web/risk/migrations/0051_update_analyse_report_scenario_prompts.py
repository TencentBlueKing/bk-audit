# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from django.db import migrations, models

BUILTIN_SCENARIOS = [
    {
        "scenario_key": "person_investigation",
        "name": "责任人行为调查分析报告",
        "description": "行为链分析、风险关联分析、意图判断、关联人员挖掘、建议下一步调查、风险影响评估",
        "report_type": "system",
        "is_builtin": True,
        "system_prompt": (
            "你是一个专业的审计安全分析师。请根据当前报告已绑定的风险数据，对责任人进行深度行为调查分析。\n"
            "报告需包含以下章节：\n"
            "一、行为链分析 - 对责任人相关风险单进行时序分析，发现行为轨迹\n"
            "二、风险关联分析 - 识别多个风险单之间的关联关系\n"
            "三、意图判断 - 基于行为模式分析主观故意可能性\n"
            "四、关联人员挖掘 - 识别可能存在配合行为的其他人员\n"
            "五、建议下一步调查 - 提出具体可操作的调查方向\n"
            "六、风险影响评估 - 评估潜在影响范围和严重程度"
        ),
        "priority": 100,
    },
    {
        "scenario_key": "comprehensive",
        "name": "风险综合分析报告",
        "description": "根因归纳、风险聚类、异常识别、趋势解读、关联分析、治理建议",
        "report_type": "system",
        "is_builtin": True,
        "system_prompt": (
            "你是一个专业的审计安全分析师。请根据当前报告已绑定的风险数据，进行综合分析。\n"
            "报告需包含以下章节：\n"
            "一、总览概述 - 数据范围、风险数量、关键指标\n"
            "二、根因归纳 - 归纳主要的风险根因\n"
            "三、风险聚类 - 按相似性对风险进行分组聚类\n"
            "四、异常识别 - 识别显著异常的风险模式\n"
            "五、趋势解读 - 分析风险变化趋势\n"
            "六、关联分析 - 发现风险之间的关联\n"
            "七、治理建议 - 提出具体可操作的治理建议"
        ),
        "priority": 90,
    },
    {
        "scenario_key": "trend_summary",
        "name": "风险态势总结报告",
        "description": "自然语言总结、重点事件提炼、风险预判",
        "report_type": "system",
        "is_builtin": True,
        "system_prompt": (
            "你是一个专业的审计安全分析师。请根据当前报告已绑定的风险数据，生成态势总结报告。\n"
            "报告需包含以下章节：\n"
            "一、态势概览 - 用自然语言概述当前风险态势\n"
            "二、重点事件 - 提炼值得关注的重点风险事件\n"
            "三、风险趋势 - 分析风险数量和类型的变化趋势\n"
            "四、风险预判 - 预测未来可能出现的风险"
        ),
        "priority": 80,
    },
    {
        "scenario_key": "strategy_analysis",
        "name": "策略分析报告",
        "description": "策略的风险总览、策略意图分析、策略覆盖度评估、策略级根因归类",
        "report_type": "system",
        "is_builtin": True,
        "system_prompt": (
            "你是一个专业的审计安全分析师。请根据当前报告已绑定的风险数据，生成策略分析报告。\n"
            "报告需包含以下章节：\n"
            "一、策略概览 - 各策略对应的风险数量和分布\n"
            "二、策略意图分析 - 分析各策略的检测意图和效果\n"
            "三、策略覆盖度 - 评估策略覆盖是否充分\n"
            "四、策略级根因归类 - 按策略维度归类风险根因"
        ),
        "priority": 70,
    },
    {
        "scenario_key": "scenario_analysis",
        "name": "场景分析报告",
        "description": "多点场景的风险总览、跨策略关联分析、场景覆盖度评估、场景级根因归类",
        "report_type": "system",
        "is_builtin": True,
        "system_prompt": (
            "你是一个专业的审计安全分析师。请根据当前报告已绑定的风险数据，生成场景分析报告。\n"
            "报告需包含以下章节：\n"
            "一、场景概览 - 各场景对应的风险数量和分布\n"
            "二、跨策略关联分析 - 分析不同策略在同一场景下的关联\n"
            "三、场景覆盖度 - 评估场景覆盖是否充分\n"
            "四、场景级根因归类 - 按场景维度归类风险根因"
        ),
        "priority": 60,
    },
    {
        "scenario_key": "tag_analysis",
        "name": "标签分析报告",
        "description": "标签维度的风险聚合分析、标签间关联发现、处理状态分布",
        "report_type": "system",
        "is_builtin": True,
        "system_prompt": (
            "你是一个专业的审计安全分析师。请根据当前报告已绑定的风险数据，生成标签分析报告。\n"
            "报告需包含以下章节：\n"
            "一、标签概览 - 各标签对应的风险数量和分布\n"
            "二、标签间关联 - 发现不同标签之间的关联关系\n"
            "三、处理状态分布 - 按标签维度统计风险处理状态\n"
            "四、标签治理建议 - 提出标签维度的治理建议"
        ),
        "priority": 50,
    },
]


def update_builtin_scenario_prompts(apps, schema_editor):
    """更新内置 AI 分析报告场景 prompt。"""
    AnalyseReportScenario = apps.get_model("risk", "AnalyseReportScenario")
    for scenario_data in BUILTIN_SCENARIOS:
        defaults = {**scenario_data, "updated_by": "system"}
        defaults.setdefault("created_by", "system")
        AnalyseReportScenario.objects.update_or_create(
            scenario_key=scenario_data["scenario_key"],
            defaults=defaults,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("risk", "0050_analysereport_extra_info"),
    ]

    operations = [
        migrations.AlterField(
            model_name="analysereport",
            name="prompt_params",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="用于后端筛选并绑定报告风险的参数",
                verbose_name="Prompt参数",
            ),
        ),
        migrations.AlterField(
            model_name="analysereportscenario",
            name="system_prompt",
            field=models.TextField(help_text="发送给Agent的系统提示词模板", verbose_name="Agent System Prompt"),
        ),
        migrations.RunPython(update_builtin_scenario_prompts, migrations.RunPython.noop),
    ]
