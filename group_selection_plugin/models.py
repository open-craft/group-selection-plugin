"""
Data models for group_selection_plugin.
"""

from django.conf import settings
from django.db import models

from model_utils.models import TimeStampedModel
from opaque_keys.edx.django.models import CourseKeyField, UsageKeyField


class LearnerSelection(TimeStampedModel):
    """
    Stores the current selection for a learner on a specific Group Selection block.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    course_key = CourseKeyField(max_length=255, db_index=True)
    usage_key = UsageKeyField(max_length=255, db_index=True)
    choice_id = models.CharField(max_length=255)
    content_group_id = models.IntegerField()
    cohort_id = models.IntegerField(null=True)

    class Meta:
        unique_together = ("user", "usage_key")
        ordering = ["-modified"]
        indexes = [
            models.Index(fields=["course_key", "usage_key"]),
        ]

    def __str__(self):
        return f"LearnerSelection(user={self.user_id}, block={self.usage_key}, choice={self.choice_id})"


class SelectionEvent(TimeStampedModel):
    """
    Audit trail for all selection and reassignment actions.
    """

    class EventType(models.TextChoices):
        SELECTED = "selected", "Learner selected"
        CHANGED = "changed", "Learner changed selection"
        STAFF_OVERRIDE = "staff_override", "Staff override"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="selection_events",
    )
    course_key = CourseKeyField(max_length=255)
    usage_key = UsageKeyField(max_length=255)
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    previous_choice_id = models.CharField(max_length=255, null=True, blank=True)
    new_choice_id = models.CharField(max_length=255)
    previous_content_group_id = models.IntegerField(null=True, blank=True)
    new_content_group_id = models.IntegerField()
    acted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="selection_actions_performed",
    )

    def __str__(self):
        return (
            f"SelectionEvent(user={self.user_id}, block={self.usage_key}, "
            f"type={self.event_type}, choice={self.new_choice_id})"
        )
