"""
Test factories for group_selection_plugin.
"""

from django.contrib.auth import get_user_model
from opaque_keys.edx.keys import CourseKey, UsageKey

User = get_user_model()

# Shared test constants.
COURSE_KEY = CourseKey.from_string("course-v1:TestX+T101+2024")
USAGE_KEY = UsageKey.from_string(
    "block-v1:TestX+T101+2024+type@group_selection+block@test_block"
)

BLOCK_CONFIG = {
    "choices": ["option_a", "option_b", "option_c"],
    "choice_group_map": {
        "option_a": 1,
        "option_b": 2,
        "option_c": 3,
    },
    "choice_partition_map": {
        "option_a": 50,
        "option_b": 50,
        "option_c": 50,
    },
    "choice_names": {
        "option_a": "Group A",
        "option_b": "Group B",
        "option_c": "Group C",
    },
    "allow_change": True,
}

BLOCK_CONFIG_LOCKED = {
    **BLOCK_CONFIG,
    "allow_change": False,
}


def create_test_user(username="testlearner", email=None):
    """Create a test user."""
    if email is None:
        email = f"{username}@example.com"
    return User.objects.create_user(username=username, email=email, password="testpass")
