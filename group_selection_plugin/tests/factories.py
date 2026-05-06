"""
Test factories for group_selection_plugin.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from opaque_keys.edx.keys import CourseKey, UsageKey

UserModel = get_user_model()

# Shared test constants.
COURSE_KEY = CourseKey.from_string("course-v1:TestX+T101+2024")
USAGE_KEY = UsageKey.from_string(
    "block-v1:TestX+T101+2024+type@group_selection+block@test_block"
)

BLOCK_CONFIG: dict = {
    "choices": ["option_a", "option_b", "option_c"],
    "choice_group_partition_map": {
        "option_a": {"group_id": 1, "partition_id": 50},
        "option_b": {"group_id": 2, "partition_id": 50},
        "option_c": {"group_id": 3, "partition_id": 50},
    },
    "choice_names": {
        "option_a": "Group A",
        "option_b": "Group B",
        "option_c": "Group C",
    },
    "allow_change": True,
}

BLOCK_CONFIG_LOCKED: dict = {
    **BLOCK_CONFIG,
    "allow_change": False,
}


def create_test_user(username: str = "testlearner", email: str | None = None) -> User:
    """Create a test user."""
    if email is None:
        email = f"{username}@example.com"
    return UserModel.objects.create_user(username=username, email=email, password="testpass")
