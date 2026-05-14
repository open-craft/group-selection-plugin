"""
URL routing for group_selection_plugin.
"""

from django.urls import include, path

urlpatterns = [
    path("v1/", include("group_selection_plugin.api.v1.urls")),
]
