"""
API views for group_selection_plugin.
"""

from __future__ import annotations

import logging
from typing import Any

from django.contrib.auth import get_user_model
from django.http import HttpRequest
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from opaque_keys.edx.keys import CourseKey, UsageKey
from xmodule.modulestore.django import modulestore

from common.djangoapps.student.models import CourseEnrollment
from common.djangoapps.student.roles import CourseStaffRole, CourseInstructorRole

from group_selection_plugin import services
from group_selection_plugin.exceptions import (
    CohortCreationFailedException,
    InvalidChoiceException,
    NotEnrolledException,
    NotStaffException,
    SelectionLockedException,
)

from .permissions import IsCourseStaffOrInstructor, IsEnrolledInCourse
from .serializers import (
    SelectionRequestSerializer,
    SelectionResponseSerializer,
    StaffOverrideRequestSerializer,
    StaffSelectionSerializer,
)

log = logging.getLogger(__name__)
User = get_user_model()


def _get_block_config(usage_key: UsageKey) -> dict[str, Any]:
    """
    Load the XBlock and extract its configuration as a dict.
    """
    block = modulestore().get_item(usage_key)
    return {
        "choices": block.choices,
        "choice_group_partition_map": block.choice_group_partition_map,
        "choice_names": getattr(block, "choice_names", {}),
        "allow_change": block.allow_change,
    }


class SelectionSubmitView(APIView):
    """
    POST /api/group-selection/v1/select/

    Submit or update a learner's group selection.
    """

    permission_classes = [IsAuthenticated, IsEnrolledInCourse]

    def post(self, request: HttpRequest) -> Response:
        serializer = SelectionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        usage_key = UsageKey.from_string(serializer.validated_data["usage_key"])
        course_key = CourseKey.from_string(serializer.validated_data["course_key"])
        choice_id = serializer.validated_data["choice_id"]

        try:
            block_config = _get_block_config(usage_key)
        except Exception:
            log.error("Failed to load block config for %s", usage_key, exc_info=True)
            return Response(
                {"error": "Could not load block configuration."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            selection = services.submit_selection(
                user=request.user,
                usage_key=usage_key,
                course_key=course_key,
                choice_id=choice_id,
                block_config=block_config,
            )
        except NotEnrolledException:
            return Response(
                {"error": "You are not enrolled in this course."},
                status=status.HTTP_403_FORBIDDEN,
            )
        except SelectionLockedException:
            return Response(
                {"error": "Your selection is locked and cannot be changed."},
                status=status.HTTP_403_FORBIDDEN,
            )
        except InvalidChoiceException:
            return Response(
                {"error": "Invalid choice."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except CohortCreationFailedException:
            log.error(
                "Cohort creation failed for user %d, block %s, choice %s",
                request.user.id, usage_key, choice_id,
                exc_info=True,
            )
            return Response(
                {"error": "No cohort mapped for the selected group."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        response_serializer = SelectionResponseSerializer(
            selection,
            context={"can_change": block_config.get("allow_change", True)},
        )
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class SelectionPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class SelectionDetailView(APIView):
    """
    GET /api/group-selection/v1/selection/{usage_key}/

    Get selections for a block. Response varies by role:
    - Learner: returns own selection (must be enrolled).
    - Staff/Instructor: returns paginated list of all selections.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: HttpRequest, usage_key_str: str) -> Response:
        usage_key = UsageKey.from_string(usage_key_str)
        course_key = usage_key.course_key

        is_staff = (
            CourseStaffRole(course_key).has_user(request.user)
            or CourseInstructorRole(course_key).has_user(request.user)
        )

        if is_staff:
            selections = services.get_block_selections(usage_key, course_key)
            paginator = SelectionPagination()
            page = paginator.paginate_queryset(selections, request)
            serializer = StaffSelectionSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        # Learner path: must be enrolled.
        if not CourseEnrollment.is_enrolled(request.user, course_key):
            return Response(
                {"error": "You are not enrolled in this course."},
                status=status.HTTP_403_FORBIDDEN,
            )

        selection = services.get_learner_selection(request.user, usage_key)
        if selection is None:
            return Response(
                {"error": "No selection found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            block_config = _get_block_config(usage_key)
            can_change = block_config.get("allow_change", True)
        except Exception:
            can_change = True

        serializer = SelectionResponseSerializer(
            selection,
            context={"can_change": can_change},
        )
        return Response(serializer.data)


class StaffOverrideView(APIView):
    """
    POST /api/group-selection/v1/staff/override/

    Override a learner's selection. Staff/Instructor only.
    """

    permission_classes = [IsAuthenticated, IsCourseStaffOrInstructor]

    def post(self, request: HttpRequest) -> Response:
        serializer = StaffOverrideRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        usage_key = UsageKey.from_string(serializer.validated_data["usage_key"])
        course_key = CourseKey.from_string(serializer.validated_data["course_key"])
        user_id = serializer.validated_data["user_id"]
        choice_id = serializer.validated_data["choice_id"]

        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            block_config = _get_block_config(usage_key)
        except Exception:
            log.error("Failed to load block config for %s", usage_key, exc_info=True)
            return Response(
                {"error": "Could not load block configuration."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            selection = services.staff_override_selection(
                staff_user=request.user,
                target_user=target_user,
                usage_key=usage_key,
                course_key=course_key,
                choice_id=choice_id,
                block_config=block_config,
            )
        except NotStaffException:
            return Response(
                {"error": "You do not have permission to override selections."},
                status=status.HTTP_403_FORBIDDEN,
            )
        except InvalidChoiceException:
            return Response(
                {"error": "Invalid choice."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except CohortCreationFailedException:
            log.error(
                "Cohort creation failed for staff override: user %d, block %s, choice %s",
                user_id, usage_key, choice_id,
                exc_info=True,
            )
            return Response(
                {"error": "No cohort mapped for the selected group."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        response_serializer = SelectionResponseSerializer(
            selection,
            context={"can_change": True},
        )
        return Response(response_serializer.data, status=status.HTTP_200_OK)
