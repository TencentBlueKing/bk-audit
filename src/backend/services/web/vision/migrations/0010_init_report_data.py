from django.db import migrations


def init_report_data(apps, schema_editor):
    ReportGroup = apps.get_model("vision", "ReportGroup")
    VisionPanel = apps.get_model("vision", "VisionPanel")

    default_group = ReportGroup.objects.create(name="默认分组", priority_index=0)

    VisionPanel.objects.filter(scenario="default", is_deleted=False,).update(
        group=default_group,
        is_enabled=True,
    )


def reverse_init_report_data(apps, schema_editor):
    ReportGroup = apps.get_model("vision", "ReportGroup")
    VisionPanel = apps.get_model("vision", "VisionPanel")

    VisionPanel.objects.filter(scenario="default").update(group=None, is_enabled=False)
    ReportGroup.objects.filter(name="默认分组").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("vision", "0009_add_report_group_and_panel_fields"),
    ]

    operations = [
        migrations.RunPython(init_report_data, reverse_init_report_data),
    ]
