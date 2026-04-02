"""
AppConfig for group_selection_plugin.
"""

from django.apps import AppConfig


class GroupSelectionPluginConfig(AppConfig):
    name = "group_selection_plugin"
    verbose_name = "Group Selection Plugin"
    default_auto_field = "django.db.models.BigAutoField"

    plugin_app = {
        "url_config": {
            "lms.djangoapp": {
                "namespace": "group_selection_plugin",
                "regex": r"^api/group-selection/",
                "relative_path": "urls",
            },
        },
    }
