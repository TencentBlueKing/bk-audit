from django.db import migrations

SCENARIO_CONTENT = {
    "person_investigation": {
        "name": "责任人行为调查报告",
        "description": "面向风险责任人的行为调查，关注行为链、风险关联、意图线索、关联人员和后续调查建议。",
        "system_prompt": (
            "你是一个专业的审计安全分析师。请根据当前报告已绑定的风险数据，对责任人进行深度行为调查分析。\n\n"
            "最终报告建议以 Markdown 输出，标题为：# 责任人行为调查分析报告。\n\n"
            "建议包含以下章节：\n"
            "一、行为链分析：梳理风险责任人的时间分布、频次、关键节点和可验证样例。\n"
            "二、风险关联分析：识别风险单之间在时间、策略、业务对象、金额、状态等维度的关联。\n"
            "三、意图判断：基于证据给出低强度意图线索；证据不足时写待核实，不做强定性。\n"
            "四、关联人员挖掘：重点分析风险责任人与事件明细字段中的疑似人员、目标账号、业务人员之间的关系。\n"
            "五、重点证据清单：列出最关键的证据点，包含数量、时间、人员、金额、risk_id 或业务对象等数据锚点。\n"
            "六、建议下一步调查：每条建议对应前文证据点，说明查什么、为什么查、预期验证什么。\n"
            "七、风险影响评估：评估影响范围、持续性、处置优先级和数据缺口。\n\n"
            "请优先保留已统计出的 TopN、频次、金额区间、业务对象分布和关键样例；"
            "没有证据支撑的判断应降级为“待核实/需补充证据”。"
        ),
    },
    "trend_summary": {
        "name": "风险态势总结报告",
        "description": "面向整体风险态势的自然语言总结，关注当前状态、重点事件、趋势和预判。",
        "system_prompt": (
            "你是一个专业的审计安全分析师。请根据当前报告已绑定的风险数据，生成风险态势总结报告。\n\n"
            "最终报告建议以 Markdown 输出，标题为：# 风险态势总结报告。\n\n"
            "建议包含以下章节：\n"
            "一、态势概览：概述当前风险数量、等级、状态、主要类型和整体态势。\n"
            "二、重点事件：提炼值得关注的风险事件和关键证据。\n"
            "三、风险趋势：基于现有数据说明趋势；样本不足时明确数据局限。\n"
            "四、风险预判：给出短期关注点、可能影响和后续处置建议。\n\n"
            "请以已获取证据为主组织内容。"
        ),
    },
}


def update_analyse_report_scenario_content(apps, schema_editor):
    AnalyseReportScenario = apps.get_model("risk", "AnalyseReportScenario")
    for scenario_key, scenario_content in SCENARIO_CONTENT.items():
        AnalyseReportScenario.objects.filter(scenario_key=scenario_key).update(
            **scenario_content,
            updated_by="system",
        )


class Migration(migrations.Migration):

    dependencies = [
        ("risk", "0052_analysereport_title_generating_and_more"),
    ]

    operations = [
        migrations.RunPython(update_analyse_report_scenario_content, migrations.RunPython.noop),
    ]
