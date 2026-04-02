"""
Django admin registration for group_selection_plugin.
"""

from django.contrib import admin

from .models import LearnerSelection, SelectionEvent


@admin.register(LearnerSelection)
class LearnerSelectionAdmin(admin.ModelAdmin):
    list_display = ("user", "course_key", "usage_key", "choice_id", "content_group_id", "cohort_id", "modified")
    list_filter = ("course_key",)
    search_fields = ("user__username", "choice_id")
    raw_id_fields = ("user",)
    list_select_related = ("user",)


@admin.register(SelectionEvent)
class SelectionEventAdmin(admin.ModelAdmin):
    list_display = (
        "user", "course_key", "usage_key", "event_type",
        "previous_choice_id", "new_choice_id", "acted_by", "created",
    )
    list_filter = ("event_type", "course_key")
    search_fields = ("user__username",)
    raw_id_fields = ("user", "acted_by")
    list_select_related = ("user", "acted_by")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
