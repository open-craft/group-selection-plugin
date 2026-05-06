"""
Serializers for group_selection_plugin API.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers


class SelectionRequestSerializer(serializers.Serializer):
    usage_key = serializers.CharField()
    course_key = serializers.CharField()
    choice_id = serializers.CharField()


class SelectionResponseSerializer(serializers.Serializer):
    choice_id = serializers.CharField()
    content_group_id = serializers.IntegerField()
    created_at = serializers.DateTimeField(source="created")
    updated_at = serializers.DateTimeField(source="modified")
    can_change = serializers.SerializerMethodField()

    def get_can_change(self, obj: Any) -> bool:
        return self.context.get("can_change", True)


class StaffSelectionSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(source="user.id")
    username = serializers.CharField(source="user.username")
    choice_id = serializers.CharField()
    content_group_id = serializers.IntegerField()
    updated_at = serializers.DateTimeField(source="modified")


class StaffOverrideRequestSerializer(serializers.Serializer):
    usage_key = serializers.CharField()
    course_key = serializers.CharField()
    user_id = serializers.IntegerField()
    choice_id = serializers.CharField()
