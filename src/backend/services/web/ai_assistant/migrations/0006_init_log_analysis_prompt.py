"""初始化第一版审计日志默认分析标准。"""

from django.db import migrations

CONFIG_KEY = "ai_assistant_log_analysis_default_prompt"
DEFAULT_PROMPT = """
请基于当前日志检索条件，使用审计日志检索、字段探索和聚合工具完成分析，并生成 Markdown 报告。

报告应包含：
1. 分析范围：说明系统、时间范围、检索条件、命中规模和数据限制。
2. 整体概览：概括主要操作、用户、结果和资源分布。
3. 时间与行为特征：分析趋势、峰值、集中时段和关键行为组合。
4. 风险与异常发现：列出候选异常及工具返回的证据，并明确区分事实、推断和建议。
5. 重点发现与可执行建议：按优先级给出结论和后续动作。
6. 分析限制：说明未覆盖、无法确认或数据质量不足的部分。

不得伪造工具未返回的数据，不得把推测写成确定事实，不要大段堆砌原始日志。
""".strip()


def init_log_analysis_prompt(apps, schema_editor):
    """仅在配置不存在时写入首版，不覆盖运营已预置的内容。"""

    global_meta_config = apps.get_model("meta", "GlobalMetaConfig")
    global_meta_config.objects.get_or_create(
        config_level="global",
        instance_key="global",
        config_key=CONFIG_KEY,
        defaults={"config_value": DEFAULT_PROMPT},
    )


class Migration(migrations.Migration):
    dependencies = [
        ("ai_assistant", "0005_user_column_preference"),
        ("meta", "0025_alter_enummappingcollectionrelation_related_type"),
    ]

    # 无法区分迁移创建和运营预置的同 key 记录，回滚不得删除现存配置。
    operations = [migrations.RunPython(init_log_analysis_prompt, migrations.RunPython.noop)]
