"""将全局 DEFAULT 分析标准更新为重点发现和具体行动。

按版本统一覆盖目标配置，缺失时创建，不比对之前的提示词内容。
其他作用域不受影响；历史附件使用快照，反向迁移不回写配置。
"""

from django.db import migrations

CONFIG_KEY = "ai_assistant_log_analysis_default_prompt"
DEFAULT_PROMPT = """
请基于本次日志检索上下文，按问题需要选择字段探索、聚合或明细取证，生成帮助用户决定“优先关注什么、为什么、下一步做什么”的 Markdown 分析报告。

先给简短结论和必要的分析范围，再展开最值得关注的发现。结合已知影响、影响范围、持续性和证据充分程度安排重点；同一问题合并呈现，普通分布只作为理解重点所需的背景。没有突出发现时如实说明，无需凑齐固定章节、风险等级或建议数量。

每项重点发现说明观察到什么、有哪些对照或证据、对当前目标有什么意义。高频、集中访问和非零结果码需要结合业务语义或可比较的基线解释；没有依据时保留待核实判断，不把现象直接写成安全风险或具体根因。

建议对应具体发现，写清要检查或处理的对象、采用什么方法，以及什么结果支持下一步行动。根因尚未确定时，优先给出能缩小问题范围的核实动作。避免只写“加强监控”“优化校验”等通用建议。

关键数字和结论使用同范围、同类别、同分母的可回查依据，核对摘要与正文的一致性。区分事实、推断和待确认事项，说明影响判断的重要数据限制；避免重复结论和大段原始日志。
""".strip()


def update_log_analysis_prompt(apps, schema_editor):
    """按全局配置定位键创建或覆盖本版本的 DEFAULT 指令。"""

    global_meta_config = apps.get_model("meta", "GlobalMetaConfig")
    global_meta_config.objects.using(schema_editor.connection.alias).update_or_create(
        config_level="global",
        instance_key="global",
        config_key=CONFIG_KEY,
        defaults={"config_value": DEFAULT_PROMPT},
    )


class Migration(migrations.Migration):
    dependencies = [("ai_assistant", "0009_merge_20260930_1424")]

    operations = [migrations.RunPython(update_log_analysis_prompt, migrations.RunPython.noop)]
