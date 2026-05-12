# -*- coding: utf-8 -*-

from django.contrib import admin

from services.web.scene.models import (
    ResourceBinding,
    ResourceBindingScene,
    ResourceBindingSystem,
    Scene,
    SceneDataTable,
    SceneSystem,
)


@admin.register(Scene)
class SceneAdmin(admin.ModelAdmin):
    list_display = [
        "scene_id",
        "name",
        "status",
        "iam_manager_group_id",
        "iam_viewer_group_id",
        "is_deleted",
        "updated_at",
    ]
    list_filter = ["status", "is_deleted"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_by", "created_at", "updated_by", "updated_at"]

    def get_queryset(self, request):
        """后台需要能看到软删除场景，便于手动恢复。"""
        return Scene._objects.all()

    def delete_model(self, request, obj):
        """后台删除也必须走软删除，避免绕过 Scene.delete() 造成级联硬删。"""
        obj.delete()

    def delete_queryset(self, request, queryset):
        """后台批量删除使用软删除语义。"""
        for obj in queryset:
            obj.delete()


@admin.register(SceneSystem)
class SceneSystemAdmin(admin.ModelAdmin):
    list_display = ["id", "scene", "system_id", "is_all_systems", "updated_at"]
    list_filter = ["is_all_systems"]
    search_fields = ["scene__name", "system_id"]
    readonly_fields = ["created_by", "created_at", "updated_by", "updated_at"]


@admin.register(SceneDataTable)
class SceneDataTableAdmin(admin.ModelAdmin):
    list_display = ["id", "scene", "table_id", "updated_at"]
    list_filter = ["scene"]
    search_fields = ["scene__name", "table_id"]
    readonly_fields = ["created_by", "created_at", "updated_by", "updated_at"]


@admin.register(ResourceBinding)
class ResourceBindingAdmin(admin.ModelAdmin):
    list_display = ["id", "resource_type", "resource_id", "binding_type", "visibility_type", "updated_at"]
    list_filter = ["resource_type", "binding_type", "visibility_type"]
    search_fields = ["resource_id"]
    readonly_fields = ["created_by", "created_at", "updated_by", "updated_at"]


@admin.register(ResourceBindingScene)
class ResourceBindingSceneAdmin(admin.ModelAdmin):
    list_display = ["id", "binding", "scene", "updated_at"]
    list_filter = ["scene", "binding__resource_type", "binding__binding_type"]
    search_fields = ["scene__name", "binding__resource_id"]
    readonly_fields = ["created_by", "created_at", "updated_by", "updated_at"]


@admin.register(ResourceBindingSystem)
class ResourceBindingSystemAdmin(admin.ModelAdmin):
    list_display = ["id", "binding", "system_id", "updated_at"]
    list_filter = ["binding__resource_type", "binding__binding_type"]
    search_fields = ["system_id", "binding__resource_id"]
    readonly_fields = ["created_by", "created_at", "updated_by", "updated_at"]
