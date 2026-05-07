"""
Tests for group_selection_plugin service layer.

All edx-platform imports are mocked since they're not available outside the LMS runtime.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import TestCase

from group_selection_plugin.exceptions import (
    CohortCreationFailedException,
    InvalidChoiceException,
    NotEnrolledException,
    NotStaffException,
    SelectionLockedException,
)
from group_selection_plugin.models import LearnerSelection, SelectionEvent
from group_selection_plugin.services import (  # noqa: F401 — forces module import for @patch
    ensure_cohorts_for_block,
    staff_override_selection,
    submit_selection,
)

from .factories import (
    BLOCK_CONFIG,
    BLOCK_CONFIG_LOCKED,
    COURSE_KEY,
    USAGE_KEY,
    create_test_user,
)


# Base path for mocking edx-platform imports used in services.py
SERVICES_MODULE = "group_selection_plugin.services"


class EnsureCohortsForBlockTest(TestCase):
    """Tests for ensure_cohorts_for_block."""

    @patch(f"{SERVICES_MODULE}.set_course_cohorted")
    @patch(f"{SERVICES_MODULE}.CourseUserGroupPartitionGroup")
    @patch(f"{SERVICES_MODULE}.CourseUserGroup")
    def test_ensure_cohorts_creates_cohorts(
        self, mock_cug: MagicMock, mock_cugpg: MagicMock, mock_set_cohorted: MagicMock,
    ) -> None:
        """Creates cohorts for all mapped content groups and links them."""
        # No existing links.
        mock_cugpg.objects.filter.return_value.select_related.return_value.first.return_value = None

        # Mock cohort creation.
        mock_cohort = MagicMock()
        mock_cohort.id = 100
        mock_cohort.name = "Group A"
        mock_cug.objects.create.return_value = mock_cohort
        mock_cug.COHORT = "cohort"

        result = ensure_cohorts_for_block(COURSE_KEY, BLOCK_CONFIG)

        # Should create cohorts for all 3 choices.
        self.assertEqual(mock_cug.objects.create.call_count, 3)
        self.assertEqual(mock_cugpg.objects.create.call_count, 3)
        self.assertEqual(len(result), 3)
        for mapping in result:
            self.assertTrue(mapping["created"])

    @patch(f"{SERVICES_MODULE}.set_course_cohorted")
    @patch(f"{SERVICES_MODULE}.CourseUserGroupPartitionGroup")
    @patch(f"{SERVICES_MODULE}.CourseUserGroup")
    def test_ensure_cohorts_enables_course_cohorts(
        self, mock_cug: MagicMock, mock_cugpg: MagicMock, mock_set_cohorted: MagicMock,
    ) -> None:
        """Enables cohort settings for the course."""
        mock_cugpg.objects.filter.return_value.select_related.return_value.first.return_value = None
        mock_cohort = MagicMock(id=1, name="Test")
        mock_cug.objects.create.return_value = mock_cohort
        mock_cug.COHORT = "cohort"

        ensure_cohorts_for_block(COURSE_KEY, BLOCK_CONFIG)

        mock_set_cohorted.assert_called_once_with(COURSE_KEY, True)

    @patch(f"{SERVICES_MODULE}.set_course_cohorted")
    @patch(f"{SERVICES_MODULE}.CourseUserGroupPartitionGroup")
    @patch(f"{SERVICES_MODULE}.CourseUserGroup")
    def test_ensure_cohorts_skips_existing(
        self, mock_cug: MagicMock, mock_cugpg: MagicMock, mock_set_cohorted: MagicMock,
    ) -> None:
        """Does not duplicate cohorts that already exist and are linked."""
        existing_link = MagicMock()
        existing_link.course_user_group.id = 50
        existing_link.course_user_group.name = "Existing Group"
        mock_cugpg.objects.filter.return_value.select_related.return_value.first.return_value = existing_link

        result = ensure_cohorts_for_block(COURSE_KEY, BLOCK_CONFIG)

        # Should NOT create any new cohorts.
        mock_cug.objects.create.assert_not_called()
        self.assertEqual(len(result), 3)
        for mapping in result:
            self.assertFalse(mapping["created"])
            self.assertEqual(mapping["cohort_id"], 50)

    @patch(f"{SERVICES_MODULE}.set_course_cohorted")
    @patch(f"{SERVICES_MODULE}.CourseUserGroupPartitionGroup")
    @patch(f"{SERVICES_MODULE}.CourseUserGroup")
    def test_ensure_cohorts_names_from_content_group(
        self, mock_cug: MagicMock, mock_cugpg: MagicMock, mock_set_cohorted: MagicMock,
    ) -> None:
        """Created cohort names match the content group names from block config."""
        mock_cugpg.objects.filter.return_value.select_related.return_value.first.return_value = None
        mock_cohort = MagicMock(id=1)
        mock_cug.objects.create.return_value = mock_cohort
        mock_cug.COHORT = "cohort"

        ensure_cohorts_for_block(COURSE_KEY, BLOCK_CONFIG)

        # Verify names passed to create match choice_names.
        create_calls = mock_cug.objects.create.call_args_list
        created_names = [call.kwargs["name"] for call in create_calls]
        self.assertIn("Group A", created_names)
        self.assertIn("Group B", created_names)
        self.assertIn("Group C", created_names)


class SubmitSelectionTest(TestCase):
    """Tests for submit_selection."""

    def setUp(self) -> None:
        self.user = create_test_user()

    @patch(f"{SERVICES_MODULE}.add_user_to_cohort")
    @patch(f"{SERVICES_MODULE}.CourseUserGroupPartitionGroup")
    @patch(f"{SERVICES_MODULE}.CourseEnrollment")
    def test_submit_selection_happy_path(
        self, mock_enrollment: MagicMock, mock_cugpg: MagicMock, mock_add_cohort: MagicMock,
    ) -> None:
        """New selection creates LearnerSelection + SelectionEvent + assigns cohort."""
        mock_enrollment.is_enrolled.return_value = True

        mock_link = MagicMock()
        mock_link.course_user_group.id = 10
        mock_link.course_user_group.name = "Group A"
        mock_cugpg.objects.filter.return_value.select_related.return_value.first.return_value = mock_link

        selection = submit_selection(
            self.user, USAGE_KEY, COURSE_KEY, "option_a", BLOCK_CONFIG,
        )

        self.assertEqual(selection.choice_id, "option_a")
        self.assertEqual(selection.content_group_id, 1)
        self.assertEqual(selection.cohort_id, 10)
        mock_add_cohort.assert_called_once()

        # Check event was logged.
        event = SelectionEvent.objects.get(user=self.user, usage_key=USAGE_KEY)
        self.assertEqual(event.event_type, SelectionEvent.EventType.SELECTED)
        self.assertEqual(event.new_choice_id, "option_a")
        self.assertIsNone(event.previous_choice_id)

    @patch(f"{SERVICES_MODULE}.add_user_to_cohort")
    @patch(f"{SERVICES_MODULE}.CourseUserGroupPartitionGroup")
    @patch(f"{SERVICES_MODULE}.CourseEnrollment")
    def test_submit_selection_locked(
        self, mock_enrollment: MagicMock, mock_cugpg: MagicMock, mock_add_cohort: MagicMock,
    ) -> None:
        """When allow_change=False and selection exists, raises exception."""
        mock_enrollment.is_enrolled.return_value = True

        # Create existing selection.
        LearnerSelection.objects.create(
            user=self.user,
            course_key=COURSE_KEY,
            usage_key=USAGE_KEY,
            choice_id="option_a",
            content_group_id=1,
            cohort_id=10,
        )

        with self.assertRaises(SelectionLockedException):
            submit_selection(
                self.user, USAGE_KEY, COURSE_KEY, "option_b", BLOCK_CONFIG_LOCKED,
            )

    @patch(f"{SERVICES_MODULE}.add_user_to_cohort")
    @patch(f"{SERVICES_MODULE}.CourseUserGroupPartitionGroup")
    @patch(f"{SERVICES_MODULE}.CourseEnrollment")
    def test_submit_selection_change_allowed(
        self, mock_enrollment: MagicMock, mock_cugpg: MagicMock, mock_add_cohort: MagicMock,
    ) -> None:
        """When allow_change=True and selection exists, updates and reassigns cohort."""
        mock_enrollment.is_enrolled.return_value = True

        LearnerSelection.objects.create(
            user=self.user,
            course_key=COURSE_KEY,
            usage_key=USAGE_KEY,
            choice_id="option_a",
            content_group_id=1,
            cohort_id=10,
        )

        mock_link = MagicMock()
        mock_link.course_user_group.id = 20
        mock_link.course_user_group.name = "Group B"
        mock_cugpg.objects.filter.return_value.select_related.return_value.first.return_value = mock_link

        selection = submit_selection(
            self.user, USAGE_KEY, COURSE_KEY, "option_b", BLOCK_CONFIG,
        )

        self.assertEqual(selection.choice_id, "option_b")
        self.assertEqual(selection.content_group_id, 2)
        self.assertEqual(selection.cohort_id, 20)

        event = SelectionEvent.objects.filter(
            user=self.user, event_type=SelectionEvent.EventType.CHANGED,
        ).first()
        self.assertIsNotNone(event)
        self.assertEqual(event.previous_choice_id, "option_a")
        self.assertEqual(event.new_choice_id, "option_b")

    @patch(f"{SERVICES_MODULE}.CourseEnrollment")
    def test_submit_selection_invalid_choice(self, mock_enrollment: MagicMock) -> None:
        """Invalid choice_id raises validation error."""
        mock_enrollment.is_enrolled.return_value = True

        with self.assertRaises(InvalidChoiceException):
            submit_selection(
                self.user, USAGE_KEY, COURSE_KEY, "nonexistent", BLOCK_CONFIG,
            )

    @patch(f"{SERVICES_MODULE}.add_user_to_cohort")
    @patch(f"{SERVICES_MODULE}.set_course_cohorted")
    @patch(f"{SERVICES_MODULE}.CourseUserGroup")
    @patch(f"{SERVICES_MODULE}.CourseUserGroupPartitionGroup")
    @patch(f"{SERVICES_MODULE}.CourseEnrollment")
    def test_submit_selection_missing_cohort_raises_error(
        self,
        mock_enrollment: MagicMock,
        mock_cugpg: MagicMock,
        mock_cug: MagicMock,
        mock_set_cohorted: MagicMock,
        mock_add_cohort: MagicMock,
    ) -> None:
        """If cohort is missing, raises CohortCreationFailedException (staff should configure cohorts)."""
        mock_enrollment.is_enrolled.return_value = True

        # _find_cohort returns None — cohort was never set up.
        mock_cugpg.objects.filter.return_value.select_related.return_value.first.return_value = None

        with self.assertRaises(CohortCreationFailedException):
            submit_selection(
                self.user, USAGE_KEY, COURSE_KEY, "option_a", BLOCK_CONFIG,
            )

    @patch(f"{SERVICES_MODULE}.CourseEnrollment")
    def test_submit_selection_not_enrolled(self, mock_enrollment: MagicMock) -> None:
        """Unenrolled user raises permission error."""
        mock_enrollment.is_enrolled.return_value = False

        with self.assertRaises(NotEnrolledException):
            submit_selection(
                self.user, USAGE_KEY, COURSE_KEY, "option_a", BLOCK_CONFIG,
            )


class StaffOverrideTest(TestCase):
    """Tests for staff_override_selection."""

    def setUp(self) -> None:
        self.staff_user = create_test_user(username="staffuser")
        self.target_user = create_test_user(username="targetuser")

    @patch(f"{SERVICES_MODULE}.add_user_to_cohort")
    @patch(f"{SERVICES_MODULE}.CourseUserGroupPartitionGroup")
    @patch(f"{SERVICES_MODULE}.CourseInstructorRole")
    @patch(f"{SERVICES_MODULE}.CourseStaffRole")
    def test_staff_override(
        self,
        mock_staff_role: MagicMock,
        mock_instructor_role: MagicMock,
        mock_cugpg: MagicMock,
        mock_add_cohort: MagicMock,
    ) -> None:
        """Staff can override regardless of allow_change setting."""
        mock_staff_role.return_value.has_user.return_value = True
        mock_instructor_role.return_value.has_user.return_value = False

        mock_link = MagicMock()
        mock_link.course_user_group.id = 10
        mock_link.course_user_group.name = "Group B"
        mock_cugpg.objects.filter.return_value.select_related.return_value.first.return_value = mock_link

        selection = staff_override_selection(
            self.staff_user, self.target_user, USAGE_KEY, COURSE_KEY,
            "option_b", BLOCK_CONFIG_LOCKED,
        )

        self.assertEqual(selection.choice_id, "option_b")
        self.assertEqual(selection.user, self.target_user)

        event = SelectionEvent.objects.get(user=self.target_user)
        self.assertEqual(event.event_type, SelectionEvent.EventType.STAFF_OVERRIDE)
        self.assertEqual(event.acted_by, self.staff_user)

    @patch(f"{SERVICES_MODULE}.CourseInstructorRole")
    @patch(f"{SERVICES_MODULE}.CourseStaffRole")
    def test_staff_override_non_staff(
        self, mock_staff_role: MagicMock, mock_instructor_role: MagicMock,
    ) -> None:
        """Non-staff user cannot use override."""
        mock_staff_role.return_value.has_user.return_value = False
        mock_instructor_role.return_value.has_user.return_value = False

        with self.assertRaises(NotStaffException):
            staff_override_selection(
                self.staff_user, self.target_user, USAGE_KEY, COURSE_KEY,
                "option_b", BLOCK_CONFIG,
            )
