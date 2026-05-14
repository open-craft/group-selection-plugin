# group_selection_plugin

Open edX plugin for learner group selection. Allows learners to self-select into content groups within a course, backed by cohort assignment.

## Installation

```bash
pip install -e .
```

## Runtime Dependencies

This plugin runs inside the Open edX LMS/CMS process and depends on:

- Django >= 4.2
- djangorestframework
- opaque-keys
- edx-platform (provides cohort APIs, enrollment models, and course roles)
