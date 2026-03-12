from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("risk", "0046_migrate_json_to_str_fields"),
    ]

    operations = [
        migrations.RemoveField(model_name="risk", name="operator"),
        migrations.RemoveField(model_name="risk", name="current_operator"),
        migrations.RemoveField(model_name="risk", name="notice_users"),
        migrations.RenameField(model_name="risk", old_name="operator_str", new_name="operator"),
        migrations.RenameField(model_name="risk", old_name="current_operator_str", new_name="current_operator"),
        migrations.RenameField(model_name="risk", old_name="notice_users_str", new_name="notice_users"),
    ]
