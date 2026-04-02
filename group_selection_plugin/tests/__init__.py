"""
Test package for group_selection_plugin.

Mocks edx-platform modules that are only available inside the LMS/CMS runtime.
"""

import sys
from unittest.mock import MagicMock

# Create mock modules for edx-platform dependencies so services.py can be imported.
# These are replaced by per-test patches in test_services.py and test_api.py.

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
