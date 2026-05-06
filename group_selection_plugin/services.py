"""
Core business logic for group_selection_plugin.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.db.models.query import QuerySet
from opaque_keys.edx.keys import CourseKey, UsageKey

from openedx.core.djangoapps.course_groups.cohorts import (
    add_user_to_cohort,
    set_course_cohorted,
)
from openedx.core.djangoapps.course_groups.models import (
    CourseUserGroup,
    CourseUserGroupPartitionGroup,
)
from common.djangoapps.student.models import CourseEnrollment
from common.djangoapps.student.roles import CourseStaffRole, CourseInstructorRole
from xmodule.modulestore.django import modulestore
from xmodule.partitions.partitions_service import get_all_partitions_for_course

from .exceptions import (
    CohortCreationFailedException,
    InvalidChoiceException,
    NotEnrolledException,
    NotStaffException,
    SelectionLockedException,
)
from .models import LearnerSelection, SelectionEvent

log = logging.getLogger(__name__)


def ensure_cohorts_for_block(
    course_key: CourseKey,
    block_config: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Ensure cohort infrastructure is ready for a Group Selection block.

    Called when XBlock configuration is saved in Studio. For each mapped
    content group, creates a cohort and links it if one doesn't already exist.

    Returns:
        List of dicts with cohort mapping info for each choice.
    """
    set_course_cohorted(course_key, True)
    log.info("Ensured cohorts enabled for course %s", course_key)

    cohort_mappings = []

    for choice_id in block_config["choices"]:
        mapping = block_config["choice_group_partition_map"][choice_id]
        group_id = mapping["group_id"]
        partition_id = mapping["partition_id"]

        existing_link = CourseUserGroupPartitionGroup.objects.filter(
            partition_id=partition_id,
            group_id=group_id,
            course_user_group__course_id=course_key,
        ).select_related("course_user_group").first()

        if existing_link:
            cohort_mappings.append({
                "choice_id": choice_id,
                "cohort_id": existing_link.course_user_group.id,
                "cohort_name": existing_link.course_user_group.name,
                "content_group_id": group_id,
                "partition_id": partition_id,
                "created": False,
            })
            continue

        group_name = block_config.get("choice_names", {}).get(choice_id, f"Group {choice_id}")

        cohort = CourseUserGroup.objects.create(
            name=group_name,
            course_id=course_key,
            group_type=CourseUserGroup.COHORT,
        )
        CourseUserGroupPartitionGroup.objects.create(
            course_user_group=cohort,
            partition_id=partition_id,
            group_id=group_id,
        )
        log.info(
            "Created cohort '%s' (id=%d) for course %s, partition_id=%d, group_id=%d",
            group_name, cohort.id, course_key, partition_id, group_id,
        )

        cohort_mappings.append({
            "choice_id": choice_id,
            "cohort_id": cohort.id,
            "cohort_name": group_name,
            "content_group_id": group_id,
            "partition_id": partition_id,
            "created": True,
        })

    return cohort_mappings


def _find_cohort_for_content_group(
    course_key: CourseKey,
    partition_id: int,
    group_id: int,
) -> Optional[CourseUserGroup]:
    """
    Find the cohort linked to a specific content group.

    Returns:
        CourseUserGroup instance or None.
    """
    link = CourseUserGroupPartitionGroup.objects.filter(
        partition_id=partition_id,
        group_id=group_id,
        course_user_group__course_id=course_key,
    ).select_related("course_user_group").first()

    if link:
        return link.course_user_group
    return None


def _resolve_cohort_for_choice(
    course_key: CourseKey,
    choice_id: str,
    block_config: dict[str, Any],
) -> tuple[int, int, CourseUserGroup]:
    """
    Validate a choice and find its linked cohort, auto-creating if needed.

    Returns:
        Tuple of (group_id, partition_id, cohort).
    """
    if choice_id not in block_config["choices"]:
        raise InvalidChoiceException(
            f"Choice '{choice_id}' is not valid"
        )

    mapping = block_config["choice_group_partition_map"][choice_id]
    group_id = mapping["group_id"]
    partition_id = mapping["partition_id"]

    cohort = _find_cohort_for_content_group(course_key, partition_id, group_id)
    if cohort is None:
        # Fallback: auto-create cohorts and retry.
        log.info(
            "Cohort not found for group_id=%d, partition_id=%d in course %s. "
            "Running ensure_cohorts_for_block as fallback.",
            group_id, partition_id, course_key,
        )
        ensure_cohorts_for_block(course_key, block_config)
        cohort = _find_cohort_for_content_group(course_key, partition_id, group_id)
        if cohort is None:
            raise CohortCreationFailedException(
                f"Could not find or create cohort for content group "
                f"(partition_id={partition_id}, group_id={group_id}) in course {course_key}"
            )

    return group_id, partition_id, cohort


def _assign_to_cohort(user: AbstractUser, cohort: CourseUserGroup, course_key: CourseKey) -> None:
    """Assign a user to a cohort, treating 'already a member' as success."""
    try:
        add_user_to_cohort(cohort, user)
        log.info(
            "Assigned user %d to cohort '%s' (id=%d) in course %s",
            user.id, cohort.name, cohort.id, course_key,
        )
    except ValueError:
        log.info(
            "User %d already in cohort '%s' (id=%d) in course %s",
            user.id, cohort.name, cohort.id, course_key,
        )


def _save_selection_and_log_event(
    user: AbstractUser,
    course_key: CourseKey,
    usage_key: UsageKey,
    choice_id: str,
    group_id: int,
    cohort: CourseUserGroup,
    event_type: str,
    acted_by: AbstractUser,
) -> LearnerSelection:
    """
    Create or update LearnerSelection and log a SelectionEvent.

    Returns:
        The created or updated LearnerSelection.
    """
    try:
        existing = LearnerSelection.objects.get(user=user, usage_key=usage_key)
    except LearnerSelection.DoesNotExist:
        existing = None

    if existing:
        previous_choice_id = existing.choice_id
        previous_content_group_id = existing.content_group_id
        existing.choice_id = choice_id
        existing.content_group_id = group_id
        existing.cohort_id = cohort.id
        existing.save()
        selection = existing
    else:
        previous_choice_id = None
        previous_content_group_id = None
        selection = LearnerSelection.objects.create(
            user=user,
            course_key=course_key,
            usage_key=usage_key,
            choice_id=choice_id,
            content_group_id=group_id,
            cohort_id=cohort.id,
        )

    SelectionEvent.objects.create(
        user=user,
        course_key=course_key,
        usage_key=usage_key,
        event_type=event_type,
        previous_choice_id=previous_choice_id,
        new_choice_id=choice_id,
        previous_content_group_id=previous_content_group_id,
        new_content_group_id=group_id,
        acted_by=acted_by,
    )

    return selection


@transaction.atomic
def submit_selection(
    user: AbstractUser,
    usage_key: UsageKey,
    course_key: CourseKey,
    choice_id: str,
    block_config: dict[str, Any],
) -> LearnerSelection:
    """
    Submit or update a learner's group selection.

    Returns:
        The created or updated LearnerSelection.
    """
    if not CourseEnrollment.is_enrolled(user, course_key):
        raise NotEnrolledException(
            f"User {user.id} is not enrolled in course {course_key}"
        )

    has_existing = LearnerSelection.objects.filter(
        user=user, usage_key=usage_key,
    ).exists()
    if has_existing and not block_config.get("allow_change", False):
        raise SelectionLockedException(
            f"User {user.id} already has a selection for block {usage_key} and changes are not allowed"
        )

    group_id, _, cohort = _resolve_cohort_for_choice(
        course_key, choice_id, block_config,
    )

    _assign_to_cohort(user, cohort, course_key)

    event_type = (
        SelectionEvent.EventType.CHANGED if has_existing
        else SelectionEvent.EventType.SELECTED
    )
    return _save_selection_and_log_event(
        user, course_key, usage_key, choice_id, group_id, cohort, event_type, acted_by=user,
    )


@transaction.atomic
def staff_override_selection(
    staff_user: AbstractUser,
    target_user: AbstractUser,
    usage_key: UsageKey,
    course_key: CourseKey,
    choice_id: str,
    block_config: dict[str, Any],
) -> LearnerSelection:
    """
    Staff override of a learner's group selection.

    Ignores allow_change policy. Event type is STAFF_OVERRIDE.
    """
    if not (CourseStaffRole(course_key).has_user(staff_user) or
            CourseInstructorRole(course_key).has_user(staff_user)):
        raise NotStaffException(
            f"User {staff_user.id} does not have staff/instructor role on course {course_key}"
        )

    group_id, _, cohort = _resolve_cohort_for_choice(
        course_key, choice_id, block_config,
    )

    _assign_to_cohort(target_user, cohort, course_key)

    return _save_selection_and_log_event(
        target_user, course_key, usage_key, choice_id, group_id, cohort,
        SelectionEvent.EventType.STAFF_OVERRIDE, acted_by=staff_user,
    )


def get_learner_selection(user: AbstractUser, usage_key: UsageKey) -> Optional[LearnerSelection]:
    """
    Get the current selection for a learner on a block.

    Returns:
        LearnerSelection or None.
    """
    return LearnerSelection.objects.filter(user=user, usage_key=usage_key).first()


def get_block_selections(usage_key: UsageKey, course_key: CourseKey) -> QuerySet[LearnerSelection]:
    """
    Get all selections for a block (staff-only use).

    Returns:
        QuerySet of LearnerSelection objects.
    """
    return LearnerSelection.objects.filter(
        usage_key=usage_key,
        course_key=course_key,
    ).select_related("user")


def get_course_content_groups(course_key_str: str) -> list[dict[str, Any]]:
    """
    Fetch content groups defined in the course's Group Configurations.

    Args:
        course_key_str: Course key as a string (e.g. 'course-v1:Org+Course+Run').

    Returns:
        List of dicts with 'partition_id', 'group_id', and 'name' keys.
    """
    course_key = CourseKey.from_string(course_key_str)
    course = modulestore().get_course(course_key)

    content_groups = []
    for partition in get_all_partitions_for_course(course):
        if partition.scheme and partition.scheme.name == "cohort":
            for group in partition.groups:
                content_groups.append({
                    "partition_id": partition.id,
                    "group_id": group.id,
                    "name": group.name,
                })

    return content_groups
