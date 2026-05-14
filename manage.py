#!/usr/bin/env python
"""
Django management script for local development and testing.

Usage:
    python manage.py test
    python manage.py makemigrations group_selection_plugin
"""

import logging
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "test_settings")

    from django.core.management import execute_from_command_line

    logging.disable(logging.CRITICAL)

    execute_from_command_line(sys.argv)
