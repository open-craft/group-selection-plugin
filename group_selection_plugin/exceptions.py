"""
Custom exceptions for group_selection_plugin.
"""


class SelectionLockedException(Exception):
    """Raised when a learner tries to change a selection that is locked."""


class CohortCreationFailedException(Exception):
    """Raised when the plugin cannot find or create a cohort for a content group."""


class InvalidChoiceException(Exception):
    """Raised when the submitted choice_id is not in the block configuration."""


class NotEnrolledException(Exception):
    """Raised when a learner is not enrolled in the course."""


class NotStaffException(Exception):
    """Raised when a non-staff user attempts a staff-only action."""
