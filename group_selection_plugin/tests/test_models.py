"""
Tests for group_selection_plugin models.
"""

from django.db import IntegrityError
from django.test import TestCase

from group_selection_plugin.models import LearnerSelection, SelectionEvent

from .factories import COURSE_KEY, USAGE_KEY, create_test_user


class LearnerSelectionModelTest(TestCase):
    """Tests for the LearnerSelection model."""

    def setUp(self):
        self.user = create_test_user()

    def test_create_selection(self):
        selection = LearnerSelection.objects.create(
            user=self.user,
            course_key=COURSE_KEY,
            usage_key=USAGE_KEY,
            choice_id="option_a",
            content_group_id=1,
            cohort_id=10,
        )
        self.assertEqual(selection.choice_id, "option_a")
        self.assertEqual(selection.content_group_id, 1)
        self.assertEqual(selection.cohort_id, 10)
        self.assertIsNotNone(selection.created)
        self.assertIsNotNone(selection.modified)

    def test_unique_constraint_user_usage_key(self):
        """Only one selection per user per block."""
        LearnerSelection.objects.create(
            user=self.user,
            course_key=COURSE_KEY,
            usage_key=USAGE_KEY,
            choice_id="option_a",
            content_group_id=1,
        )
        with self.assertRaises(IntegrityError):
            LearnerSelection.objects.create(
                user=self.user,
                course_key=COURSE_KEY,
                usage_key=USAGE_KEY,
                choice_id="option_b",
                content_group_id=2,
            )

    def test_different_users_same_block(self):
        """Different users can select on the same block."""
        user2 = create_test_user(username="learner2")
        LearnerSelection.objects.create(
            user=self.user,
            course_key=COURSE_KEY,
            usage_key=USAGE_KEY,
            choice_id="option_a",
            content_group_id=1,
        )
        selection2 = LearnerSelection.objects.create(
            user=user2,
            course_key=COURSE_KEY,
            usage_key=USAGE_KEY,
            choice_id="option_b",
            content_group_id=2,
        )
        self.assertEqual(selection2.choice_id, "option_b")

    def test_str_representation(self):
        selection = LearnerSelection.objects.create(
            user=self.user,
            course_key=COURSE_KEY,
            usage_key=USAGE_KEY,
            choice_id="option_a",
            content_group_id=1,
        )
        self.assertIn("option_a", str(selection))


class SelectionEventModelTest(TestCase):
    """Tests for the SelectionEvent model."""

    def setUp(self):
        self.user = create_test_user()

    def test_create_selection_event(self):
        event = SelectionEvent.objects.create(
            user=self.user,
            course_key=COURSE_KEY,
            usage_key=USAGE_KEY,
            event_type=SelectionEvent.EventType.SELECTED,
            new_choice_id="option_a",
            new_content_group_id=1,
            acted_by=self.user,
        )
        self.assertEqual(event.event_type, "selected")
        self.assertIsNone(event.previous_choice_id)
        self.assertIsNone(event.previous_content_group_id)

    def test_change_event_with_previous(self):
        event = SelectionEvent.objects.create(
            user=self.user,
            course_key=COURSE_KEY,
            usage_key=USAGE_KEY,
            event_type=SelectionEvent.EventType.CHANGED,
            previous_choice_id="option_a",
            new_choice_id="option_b",
            previous_content_group_id=1,
            new_content_group_id=2,
            acted_by=self.user,
        )
        self.assertEqual(event.previous_choice_id, "option_a")
        self.assertEqual(event.new_choice_id, "option_b")

    def test_queryability_by_event_type(self):
        SelectionEvent.objects.create(
            user=self.user,
            course_key=COURSE_KEY,
            usage_key=USAGE_KEY,
            event_type=SelectionEvent.EventType.SELECTED,
            new_choice_id="option_a",
            new_content_group_id=1,
            acted_by=self.user,
        )
        SelectionEvent.objects.create(
            user=self.user,
            course_key=COURSE_KEY,
            usage_key=USAGE_KEY,
            event_type=SelectionEvent.EventType.STAFF_OVERRIDE,
            previous_choice_id="option_a",
            new_choice_id="option_b",
            previous_content_group_id=1,
            new_content_group_id=2,
            acted_by=create_test_user(username="staffuser"),
        )
        overrides = SelectionEvent.objects.filter(
            event_type=SelectionEvent.EventType.STAFF_OVERRIDE
        )
        self.assertEqual(overrides.count(), 1)

    def test_str_representation(self):
        event = SelectionEvent.objects.create(
            user=self.user,
            course_key=COURSE_KEY,
            usage_key=USAGE_KEY,
            event_type=SelectionEvent.EventType.SELECTED,
            new_choice_id="option_a",
            new_content_group_id=1,
            acted_by=self.user,
        )
        self.assertIn("selected", str(event))
        self.assertIn("option_a", str(event))
