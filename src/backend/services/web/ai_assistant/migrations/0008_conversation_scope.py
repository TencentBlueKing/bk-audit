"""为会话及侧栏资源绑定 concrete scope，并归一化旧消息快照。"""

from django.db import migrations, models

BATCH_SIZE = 500
DEFAULT_SCOPE_TYPE = "scene"
DEFAULT_SCOPE_ID = "1"
SESSION_MESSAGE_TYPES = ("SYSTEM_SELECTION", "USER_INTENT")


def require_default_scene(apps, schema_editor):
    """确认历史数据可绑定到产品保证存在的 scene:1。"""

    Scene = apps.get_model("scene", "Scene")
    exists = Scene.objects.using(schema_editor.connection.alias).filter(scene_id=1).exists()
    if not exists:
        raise RuntimeError("AI 助手 scope 迁移要求 scene_id=1 存在")


def _primary_key_batches(queryset):
    """按主键递增产出固定大小批次，避免迁移一次载入整表。"""

    last_pk = 0
    while True:
        batch = list(queryset.filter(pk__gt=last_pk).order_by("pk").values_list("pk", flat=True)[:BATCH_SIZE])
        if not batch:
            return
        yield batch
        last_pk = batch[-1]


def _backfill_resource_scope(model, db_alias):
    """分批为单张资源表写入 scene:1。"""

    queryset = model._base_manager.using(db_alias)
    for batch in _primary_key_batches(queryset):
        queryset.filter(pk__in=batch).update(scope_type=DEFAULT_SCOPE_TYPE, scope_id=DEFAULT_SCOPE_ID)


def _has_data_to_backfill(models, db_alias):
    """只在存在需要绑定的历史资源时要求默认场景存在。"""

    Conversation, ConversationGroup, SidebarNode, Message = models
    resource_models = (Conversation, ConversationGroup, SidebarNode)
    if any(model._base_manager.using(db_alias).exists() for model in resource_models):
        return True
    return (
        Message._base_manager.using(db_alias).filter(message_type__in=(*SESSION_MESSAGE_TYPES, "LOG_SEARCH")).exists()
    )


def validate_default_scene_if_needed(apps, schema_editor):
    """仅在迁移需要绑定历史数据时校验默认场景。"""

    db_alias = schema_editor.connection.alias
    models = (
        apps.get_model("ai_assistant", "Conversation"),
        apps.get_model("ai_assistant", "ConversationGroup"),
        apps.get_model("ai_assistant", "ConversationSidebarNode"),
        apps.get_model("ai_assistant", "Message"),
    )
    if _has_data_to_backfill(models, db_alias):
        require_default_scene(apps, schema_editor)


def backfill_conversation_scope(apps, schema_editor):
    """将旧资源绑定到 scene:1，并移除消息输入中的重复会话 scope。"""

    db_alias = schema_editor.connection.alias
    Conversation = apps.get_model("ai_assistant", "Conversation")
    ConversationGroup = apps.get_model("ai_assistant", "ConversationGroup")
    SidebarNode = apps.get_model("ai_assistant", "ConversationSidebarNode")
    Message = apps.get_model("ai_assistant", "Message")
    models = (Conversation, ConversationGroup, SidebarNode, Message)

    if not _has_data_to_backfill(models, db_alias):
        return

    require_default_scene(apps, schema_editor)

    for model in (Conversation, ConversationGroup, SidebarNode):
        _backfill_resource_scope(model, db_alias)

    message_queryset = Message._base_manager.using(db_alias).filter(
        message_type__in=(*SESSION_MESSAGE_TYPES, "LOG_SEARCH")
    )
    last_pk = 0
    while True:
        rows = list(
            message_queryset.filter(pk__gt=last_pk)
            .order_by("pk")
            .values("pk", "message_type", "input_data", "context_data")[:BATCH_SIZE]
        )
        if not rows:
            return

        messages = []
        for row in rows:
            input_data = row["input_data"]
            context_data = row["context_data"]

            if row["message_type"] in SESSION_MESSAGE_TYPES:
                if isinstance(input_data, dict):
                    input_data = dict(input_data)
                    input_data.pop("scope_type", None)
                    input_data.pop("scope_id", None)
                if isinstance(context_data, dict):
                    context_data = dict(context_data)
                    context_data["scope_type"] = DEFAULT_SCOPE_TYPE
                    context_data["scope_id"] = DEFAULT_SCOPE_ID
            elif isinstance(context_data, dict):
                context_data = dict(context_data)
                context_data["session_scope_type"] = DEFAULT_SCOPE_TYPE
                context_data["session_scope_id"] = DEFAULT_SCOPE_ID

            messages.append(
                Message(
                    pk=row["pk"],
                    input_data=input_data,
                    context_data=context_data,
                )
            )

        Message._base_manager.using(db_alias).bulk_update(
            messages,
            ["input_data", "context_data"],
            batch_size=BATCH_SIZE,
        )
        last_pk = rows[-1]["pk"]


class Migration(migrations.Migration):

    dependencies = [
        ("ai_assistant", "0007_remove_natural_language_search_message_type"),
        ("scene", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(validate_default_scene_if_needed, migrations.RunPython.noop),
        migrations.AddField(
            model_name="conversation",
            name="scope_type",
            field=models.CharField(
                blank=True, choices=[("scene", "单场景"), ("system", "单系统")], max_length=32, null=True, verbose_name="范围类型"
            ),
        ),
        migrations.AddField(
            model_name="conversation",
            name="scope_id",
            field=models.CharField(blank=True, max_length=64, null=True, verbose_name="范围 ID"),
        ),
        migrations.AddField(
            model_name="conversationgroup",
            name="scope_type",
            field=models.CharField(
                blank=True, choices=[("scene", "单场景"), ("system", "单系统")], max_length=32, null=True, verbose_name="范围类型"
            ),
        ),
        migrations.AddField(
            model_name="conversationgroup",
            name="scope_id",
            field=models.CharField(blank=True, max_length=64, null=True, verbose_name="范围 ID"),
        ),
        migrations.AddField(
            model_name="conversationsidebarnode",
            name="scope_type",
            field=models.CharField(
                blank=True, choices=[("scene", "单场景"), ("system", "单系统")], max_length=32, null=True, verbose_name="范围类型"
            ),
        ),
        migrations.AddField(
            model_name="conversationsidebarnode",
            name="scope_id",
            field=models.CharField(blank=True, max_length=64, null=True, verbose_name="范围 ID"),
        ),
        migrations.RunPython(backfill_conversation_scope, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="conversation",
            name="scope_type",
            field=models.CharField(choices=[("scene", "单场景"), ("system", "单系统")], max_length=32, verbose_name="范围类型"),
        ),
        migrations.AlterField(
            model_name="conversation",
            name="scope_id",
            field=models.CharField(max_length=64, verbose_name="范围 ID"),
        ),
        migrations.AlterField(
            model_name="conversationgroup",
            name="scope_type",
            field=models.CharField(choices=[("scene", "单场景"), ("system", "单系统")], max_length=32, verbose_name="范围类型"),
        ),
        migrations.AlterField(
            model_name="conversationgroup",
            name="scope_id",
            field=models.CharField(max_length=64, verbose_name="范围 ID"),
        ),
        migrations.AlterField(
            model_name="conversationsidebarnode",
            name="scope_type",
            field=models.CharField(choices=[("scene", "单场景"), ("system", "单系统")], max_length=32, verbose_name="范围类型"),
        ),
        migrations.AlterField(
            model_name="conversationsidebarnode",
            name="scope_id",
            field=models.CharField(max_length=64, verbose_name="范围 ID"),
        ),
        migrations.RemoveIndex(
            model_name="conversation",
            name="ai_conv_owner_list_idx",
        ),
        migrations.AddIndex(
            model_name="conversation",
            index=models.Index(
                fields=["created_by", "scope_type", "scope_id", "is_deleted", "updated_at", "id"],
                name="ai_conv_scope_list_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="conversationgroup",
            index=models.Index(fields=["created_by", "scope_type", "scope_id"], name="ai_group_scope_idx"),
        ),
        migrations.RemoveIndex(
            model_name="conversationsidebarnode",
            name="ai_node_container_pos_idx",
        ),
        migrations.RemoveIndex(
            model_name="conversationsidebarnode",
            name="ai_node_pinned_idx",
        ),
        migrations.AddIndex(
            model_name="conversationsidebarnode",
            index=models.Index(
                fields=["created_by", "scope_type", "scope_id", "parent_node", "position", "id"],
                name="ai_node_scope_pos_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="conversationsidebarnode",
            index=models.Index(
                fields=["created_by", "scope_type", "scope_id", "pinned_at", "id"],
                name="ai_node_scope_pin_idx",
            ),
        ),
    ]
