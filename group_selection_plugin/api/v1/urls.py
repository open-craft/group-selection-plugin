"""
URL routing for group_selection_plugin API v1.
"""

from django.urls import path

from . import views

urlpatterns = [
    path("select/", views.SelectionSubmitView.as_view(), name="selection-submit"),
    path(
        "selection/<str:usage_key_str>/",
        views.SelectionDetailView.as_view(),
        name="selection-detail",
    ),
    path("staff/override/", views.StaffOverrideView.as_view(), name="staff-override"),
]
