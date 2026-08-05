# -*- coding: utf-8 -*-
from rest_framework import serializers


class SubjectSerializer(serializers.Serializer):
    type = serializers.CharField()
    id = serializers.CharField()


class ResourceInstanceSerializer(serializers.Serializer):
    type = serializers.CharField()
    id = serializers.CharField()


class AuthResourceInstanceSerializer(ResourceInstanceSerializer):
    attributes = serializers.DictField(required=False)


class ApplyResourceInstanceSerializer(ResourceInstanceSerializer):
    ancestors = serializers.ListField(child=serializers.DictField(), required=False)


class ListSystemRequestSerializer(serializers.Serializer):
    page = serializers.IntegerField(required=False, min_value=1)
    page_size = serializers.IntegerField(required=False, min_value=1)


class RetrieveSystemRequestSerializer(serializers.Serializer):
    system_id = serializers.CharField()
    fields = serializers.CharField(required=False, allow_blank=True)


class DirectAuthRequestSerializer(serializers.Serializer):
    system_id = serializers.CharField()
    subject = SubjectSerializer()
    action_id = serializers.CharField()
    resource = AuthResourceInstanceSerializer(required=False, allow_null=True)


class DirectAuthByActionsRequestSerializer(serializers.Serializer):
    system_id = serializers.CharField()
    subject = SubjectSerializer()
    action_ids = serializers.ListField(child=serializers.CharField(), allow_empty=False)
    resource = AuthResourceInstanceSerializer(required=False, allow_null=True)


class DirectAuthByResourcesRequestSerializer(serializers.Serializer):
    system_id = serializers.CharField()
    subject = SubjectSerializer()
    action_id = serializers.CharField()
    resources = AuthResourceInstanceSerializer(many=True)


class ListAuthorizedResourceRequestSerializer(serializers.Serializer):
    system_id = serializers.CharField()
    subject = SubjectSerializer()
    action_id = serializers.CharField()


class PermissionApplySerializer(serializers.Serializer):
    action_id = serializers.CharField()
    resources = ApplyResourceInstanceSerializer(many=True, required=False)


class GeneratePermApplyUrlRequestSerializer(serializers.Serializer):
    system_id = serializers.CharField()
    permissions = PermissionApplySerializer(many=True)


class RoleActionSerializer(serializers.Serializer):
    id = serializers.CharField()
    resource_type_id = serializers.CharField(required=False, allow_blank=True)


class RoleSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True)
    actions = RoleActionSerializer(many=True)


class BatchCreateRoleRequestSerializer(serializers.Serializer):
    system_id = serializers.CharField()
    roles = RoleSerializer(many=True)


class DeleteRoleRequestSerializer(serializers.Serializer):
    system_id = serializers.CharField()
    role_id = serializers.CharField()


class AddAuthorizationItemSerializer(serializers.Serializer):
    role_id = serializers.CharField()
    subject = SubjectSerializer()
    expired_at = serializers.IntegerField()
    related_resource_type_id = serializers.CharField(required=False, allow_blank=True)
    resources = ResourceInstanceSerializer(many=True, required=False)


class AddAuthorizationRequestSerializer(serializers.Serializer):
    system_id = serializers.CharField()
    operator = serializers.CharField(required=False, allow_blank=True)
    authorizations = AddAuthorizationItemSerializer(many=True)


class RevokeAuthorizationItemSerializer(serializers.Serializer):
    role_id = serializers.CharField()
    subject = SubjectSerializer()
    related_resource_type_id = serializers.CharField(required=False, allow_blank=True)
    resources = ResourceInstanceSerializer(many=True, required=False)


class RevokeAuthorizationRequestSerializer(serializers.Serializer):
    system_id = serializers.CharField()
    operator = serializers.CharField(required=False, allow_blank=True)
    authorizations = RevokeAuthorizationItemSerializer(many=True)


class ListAuthorizationSubjectRequestSerializer(serializers.Serializer):
    system_id = serializers.CharField()
    operator = serializers.CharField(required=False, allow_blank=True)
    role_id = serializers.CharField()
    page = serializers.IntegerField(required=False, min_value=1)
    page_size = serializers.IntegerField(required=False, min_value=1)
    related_resource_type_id = serializers.CharField(required=False, allow_blank=True)
    resource = ResourceInstanceSerializer(required=False, allow_null=True)
