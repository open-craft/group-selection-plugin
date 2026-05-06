"""
Tests for group_selection_plugin API views.

All edx-platform imports are mocked since they're not available outside the LMS runtime.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import TestCase

from rest_framework import status as http_status
from rest_framework.test import APIRequestFactory, force_authenticate

from group_selection_plugin.api.v1.views import (
    SelectionDetailView,
    SelectionSubmitView,
    StaffOverrideView,
)
from group_selection_plugin.models import LearnerSelection

from .factories import (
    BLOCK_CONFIG,
    BLOCK_CONFIG_LOCKED,
    COURSE_KEY,
    USAGE_KEY,
    create_test_user,
)


VIEWS_MODULE = "group_selection_plugin.api.v1.views"
PERMISSIONS_MODULE = "group_selection_plugin.api.v1.permissions"


class SelectionSubmitViewTest(TestCase):
    """Tests for POST /api/group-selection/v1/select/"""

    def setUp(self) -> None:
        self.factory = APIRequestFactory()
        self.user = create_test_user()
        self.view = SelectionSubmitView.as_view()

    def _post(self, data: dict, user=None):
        request = self.factory.post(
            "/api/group-selection/v1/select/",
            data=data,
            format="json",
        )
        force_authenticate(request, user=user or self.user)
        return request

    @patch(f"{VIEWS_MODULE}._get_block_config")
    @patch(f"{VIEWS_MODULE}.services.submit_selection")
    @patch(f"{PERMISSIONS_MODULE}.CourseEnrollment")
    def test_submit_success(
        self, mock_enrollment: MagicMock, mock_submit: MagicMock, mock_get_config: MagicMock,
    ) -> None:
        """Successful selection returns 200 with selection data."""
        mock_enrollment.is_enrolled.return_value = True
        mock_get_config.return_value = BLOCK_CONFIG

        mock_selection = MagicMock()
        mock_selection.choice_id = "option_a"
        mock_selection.content_group_id = 1
        mock_selection.created = "2024-01-01T00:00:00Z"
        mock_selection.modified = "2024-01-01T00:00:00Z"
        mock_submit.return_value = mock_selection

        request = self._post({
            "usage_key": str(USAGE_KEY),
            "course_key": str(COURSE_KEY),
            "choice_id": "option_a",
        })

        response = self.view(request)

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data["choice_id"], "option_a")
        self.assertEqual(response.data["content_group_id"], 1)
        self.assertIn("can_change", response.data)

    @patch(f"{VIEWS_MODULE}._get_block_config")
    @patch(f"{VIEWS_MODULE}.services.submit_selection")
    @patch(f"{PERMISSIONS_MODULE}.CourseEnrollment")
    def test_submit_locked_returns_403(
        self, mock_enrollment: MagicMock, mock_submit: MagicMock, mock_get_config: MagicMock,
    ) -> None:
        """Locked selection returns 403."""
        mock_enrollment.is_enrolled.return_value = True
        mock_get_config.return_value = BLOCK_CONFIG_LOCKED

        from group_selection_plugin.exceptions import SelectionLockedException
        mock_submit.side_effect = SelectionLockedException("locked")

        request = self._post({
            "usage_key": str(USAGE_KEY),
            "course_key": str(COURSE_KEY),
            "choice_id": "option_b",
        })

        response = self.view(request)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    @patch(f"{VIEWS_MODULE}._get_block_config")
    @patch(f"{VIEWS_MODULE}.services.submit_selection")
    @patch(f"{PERMISSIONS_MODULE}.CourseEnrollment")
    def test_submit_invalid_choice_returns_400(
        self, mock_enrollment: MagicMock, mock_submit: MagicMock, mock_get_config: MagicMock,
    ) -> None:
        """Invalid choice returns 400."""
        mock_enrollment.is_enrolled.return_value = True
        mock_get_config.return_value = BLOCK_CONFIG

        from group_selection_plugin.exceptions import InvalidChoiceException
        mock_submit.side_effect = InvalidChoiceException("bad choice")

        request = self._post({
            "usage_key": str(USAGE_KEY),
            "course_key": str(COURSE_KEY),
            "choice_id": "nonexistent",
        })

        response = self.view(request)
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    @patch(f"{VIEWS_MODULE}._get_block_config")
    @patch(f"{VIEWS_MODULE}.services.submit_selection")
    @patch(f"{PERMISSIONS_MODULE}.CourseEnrollment")
    def test_submit_not_enrolled_returns_403(
        self, mock_enrollment: MagicMock, mock_submit: MagicMock, mock_get_config: MagicMock,
    ) -> None:
        """Not enrolled returns 403 (from service layer)."""
        mock_enrollment.is_enrolled.return_value = True  # permission passes
        mock_get_config.return_value = BLOCK_CONFIG

        from group_selection_plugin.exceptions import NotEnrolledException
        mock_submit.side_effect = NotEnrolledException("not enrolled")

        request = self._post({
            "usage_key": str(USAGE_KEY),
            "course_key": str(COURSE_KEY),
            "choice_id": "option_a",
        })

        response = self.view(request)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    @patch(f"{VIEWS_MODULE}._get_block_config")
    @patch(f"{VIEWS_MODULE}.services.submit_selection")
    @patch(f"{PERMISSIONS_MODULE}.CourseEnrollment")
    def test_submit_cohort_failure_returns_500(
        self, mock_enrollment: MagicMock, mock_submit: MagicMock, mock_get_config: MagicMock,
    ) -> None:
        """Cohort creation failure returns 500."""
        mock_enrollment.is_enrolled.return_value = True
        mock_get_config.return_value = BLOCK_CONFIG

        from group_selection_plugin.exceptions import CohortCreationFailedException
        mock_submit.side_effect = CohortCreationFailedException("no cohort")

        request = self._post({
            "usage_key": str(USAGE_KEY),
            "course_key": str(COURSE_KEY),
            "choice_id": "option_a",
        })

        response = self.view(request)
        self.assertEqual(response.status_code, http_status.HTTP_500_INTERNAL_SERVER_ERROR)

    def test_submit_unauthenticated_returns_403(self) -> None:
        """Unauthenticated request returns 403."""
        request = self.factory.post(
            "/api/group-selection/v1/select/",
            data={
                "usage_key": str(USAGE_KEY),
                "course_key": str(COURSE_KEY),
                "choice_id": "option_a",
            },
            format="json",
        )
        # Don't authenticate.
        response = self.view(request)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)


class SelectionDetailViewTest(TestCase):
    """Tests for GET /api/group-selection/v1/selection/{usage_key}/"""

    def setUp(self) -> None:
        self.factory = APIRequestFactory()
        self.user = create_test_user()
        self.view = SelectionDetailView.as_view()

    @patch(f"{VIEWS_MODULE}._get_block_config")
    @patch(f"{VIEWS_MODULE}.CourseStaffRole")
    @patch(f"{VIEWS_MODULE}.CourseInstructorRole")
    def test_learner_gets_own_selection(
        self,
        mock_instructor: MagicMock,
        mock_staff: MagicMock,
        mock_get_config: MagicMock,
    ) -> None:
        """Learner gets their own selection."""
        mock_staff.return_value.has_user.return_value = False
        mock_instructor.return_value.has_user.return_value = False
        mock_get_config.return_value = BLOCK_CONFIG

        LearnerSelection.objects.create(
            user=self.user,
            course_key=COURSE_KEY,
            usage_key=USAGE_KEY,
            choice_id="option_a",
            content_group_id=1,
            cohort_id=10,
        )

        request = self.factory.get(f"/api/group-selection/v1/selection/{USAGE_KEY}/")
        force_authenticate(request, user=self.user)

        response = self.view(request, usage_key_str=str(USAGE_KEY))

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data["choice_id"], "option_a")
        self.assertIn("can_change", response.data)

    @patch(f"{VIEWS_MODULE}.CourseStaffRole")
    @patch(f"{VIEWS_MODULE}.CourseInstructorRole")
    def test_learner_no_selection_returns_404(
        self, mock_instructor: MagicMock, mock_staff: MagicMock,
    ) -> None:
        """Learner with no selection gets 404."""
        mock_staff.return_value.has_user.return_value = False
        mock_instructor.return_value.has_user.return_value = False

        request = self.factory.get(f"/api/group-selection/v1/selection/{USAGE_KEY}/")
        force_authenticate(request, user=self.user)

        response = self.view(request, usage_key_str=str(USAGE_KEY))

        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    @patch(f"{VIEWS_MODULE}.CourseStaffRole")
    @patch(f"{VIEWS_MODULE}.CourseInstructorRole")
    def test_staff_gets_all_selections(
        self, mock_instructor: MagicMock, mock_staff: MagicMock,
    ) -> None:
        """Staff gets paginated list of all selections."""
        mock_staff.return_value.has_user.return_value = True
        mock_instructor.return_value.has_user.return_value = False

        # Create multiple selections.
        for i in range(3):
            user = create_test_user(username=f"learner{i}")
            LearnerSelection.objects.create(
                user=user,
                course_key=COURSE_KEY,
                usage_key=USAGE_KEY,
                choice_id=f"option_{chr(97 + i)}",
                content_group_id=i + 1,
                cohort_id=10 + i,
            )

        request = self.factory.get(f"/api/group-selection/v1/selection/{USAGE_KEY}/")
        force_authenticate(request, user=self.user)

        response = self.view(request, usage_key_str=str(USAGE_KEY))

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(len(response.data["results"]), 3)
        self.assertIn("user_id", response.data["results"][0])
        self.assertIn("username", response.data["results"][0])


class StaffOverrideViewTest(TestCase):
    """Tests for POST /api/group-selection/v1/staff/override/"""

    def setUp(self) -> None:
        self.factory = APIRequestFactory()
        self.staff_user = create_test_user(username="staffuser")
        self.target_user = create_test_user(username="targetuser")
        self.view = StaffOverrideView.as_view()

    @patch(f"{VIEWS_MODULE}._get_block_config")
    @patch(f"{VIEWS_MODULE}.services.staff_override_selection")
    @patch(f"{PERMISSIONS_MODULE}.CourseStaffRole")
    @patch(f"{PERMISSIONS_MODULE}.CourseInstructorRole")
    def test_staff_override_success(
        self,
        mock_instructor: MagicMock,
        mock_staff: MagicMock,
        mock_override: MagicMock,
        mock_get_config: MagicMock,
    ) -> None:
        """Staff override returns 200."""
        mock_staff.return_value.has_user.return_value = True
        mock_instructor.return_value.has_user.return_value = False
        mock_get_config.return_value = BLOCK_CONFIG

        mock_selection = MagicMock()
        mock_selection.choice_id = "option_b"
        mock_selection.content_group_id = 2
        mock_selection.created = "2024-01-01T00:00:00Z"
        mock_selection.modified = "2024-01-01T00:00:00Z"
        mock_override.return_value = mock_selection

        request = self.factory.post(
            "/api/group-selection/v1/staff/override/",
            data={
                "usage_key": str(USAGE_KEY),
                "course_key": str(COURSE_KEY),
                "user_id": self.target_user.id,
                "choice_id": "option_b",
            },
            format="json",
        )
        force_authenticate(request, user=self.staff_user)

        response = self.view(request)

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data["choice_id"], "option_b")

    @patch(f"{PERMISSIONS_MODULE}.CourseStaffRole")
    @patch(f"{PERMISSIONS_MODULE}.CourseInstructorRole")
    def test_non_staff_returns_403(
        self, mock_instructor: MagicMock, mock_staff: MagicMock,
    ) -> None:
        """Non-staff user gets 403."""
        mock_staff.return_value.has_user.return_value = False
        mock_instructor.return_value.has_user.return_value = False

        request = self.factory.post(
            "/api/group-selection/v1/staff/override/",
            data={
                "usage_key": str(USAGE_KEY),
                "course_key": str(COURSE_KEY),
                "user_id": self.target_user.id,
                "choice_id": "option_b",
            },
            format="json",
        )
        force_authenticate(request, user=self.staff_user)

        response = self.view(request)
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    @patch(f"{VIEWS_MODULE}._get_block_config")
    @patch(f"{VIEWS_MODULE}.services.staff_override_selection")
    @patch(f"{PERMISSIONS_MODULE}.CourseStaffRole")
    @patch(f"{PERMISSIONS_MODULE}.CourseInstructorRole")
    def test_override_invalid_user_returns_404(
        self,
        mock_instructor: MagicMock,
        mock_staff: MagicMock,
        mock_override: MagicMock,
        mock_get_config: MagicMock,
    ) -> None:
        """Override for nonexistent user returns 404."""
        mock_staff.return_value.has_user.return_value = True
        mock_instructor.return_value.has_user.return_value = False
        mock_get_config.return_value = BLOCK_CONFIG

        request = self.factory.post(
            "/api/group-selection/v1/staff/override/",
            data={
                "usage_key": str(USAGE_KEY),
                "course_key": str(COURSE_KEY),
                "user_id": 99999,
                "choice_id": "option_b",
            },
            format="json",
        )
        force_authenticate(request, user=self.staff_user)

        response = self.view(request)
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)
