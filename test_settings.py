"""
Minimal Django settings for running tests and management commands
outside of the LMS/CMS runtime.
"""

import sys
from unittest.mock import MagicMock

# Mock edx-platform modules that are only available inside the LMS/CMS process.
_MOCK_MODULES = [
    "openedx",
    "openedx.core",
    "openedx.core.djangoapps",
    "openedx.core.djangoapps.course_groups",
    "openedx.core.djangoapps.course_groups.cohorts",
    "openedx.core.djangoapps.course_groups.models",
    "common",
    "common.djangoapps",
    "common.djangoapps.student",
    "common.djangoapps.student.models",
    "common.djangoapps.student.roles",
    "xmodule",
    "xmodule.modulestore",
    "xmodule.modulestore.django",
]

for mod_name in _MOCK_MODULES:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


DEBUG = True
SECRET_KEY = "test-secret-key-not-for-production"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "test_db.sqlite3",
    }
}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "group_selection_plugin",
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "auth.User"
