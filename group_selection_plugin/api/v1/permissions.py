"""
Permissions for group_selection_plugin API.
"""

from rest_framework.permissions import BasePermission

from common.djangoapps.student.models import CourseEnrollment
from common.djangoapps.student.roles import CourseStaffRole, CourseInstructorRole
from opaque_keys.edx.keys import CourseKey


def _get_course_key(request, view):
    """Extract and parse the course key from the request or view kwargs."""
    course_key_str = (
        request.data.get("course_key")
        or request.query_params.get("course_key")
        or view.kwargs.get("course_key")
    )
    if not course_key_str:
        return None
    return CourseKey.from_string(course_key_str)


class IsEnrolledInCourse(BasePermission):
    """Learner must be enrolled in the course."""

    def has_permission(self, request, view):
        course_key = _get_course_key(request, view)
        if not course_key:
            return False
        return CourseEnrollment.is_enrolled(request.user, course_key)


class IsCourseStaffOrInstructor(BasePermission):
    """User must have staff or instructor role on the course."""

    def has_permission(self, request, view):
        course_key = _get_course_key(request, view)
        if not course_key:
            return False
        return (
            CourseStaffRole(course_key).has_user(request.user)
            or CourseInstructorRole(course_key).has_user(request.user)
        )
