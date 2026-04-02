"""
Package metadata for group-selection-plugin.
"""

import re
from pathlib import Path

from setuptools import find_packages, setup


def get_version(file_path):
    """Extract the version string from the file."""
    contents = Path(file_path).read_text(encoding="utf8")
    match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", contents, re.MULTILINE)
    if match:
        return match.group(1)
    raise RuntimeError("Unable to find version string.")


def load_requirements(file_path):
    """Load requirements from a file, ignoring comments and flags."""
    lines = Path(file_path).read_text(encoding="utf8").splitlines()
    return [
        line.strip() for line in lines
        if line.strip() and not line.startswith(("#", "-r", "-c", "-e", "git+"))
    ]


VERSION = get_version("group_selection_plugin/__init__.py")
README = Path("README.md").read_text(encoding="utf8")

setup(
    name="group-selection-plugin",
    version=VERSION,
    description="Open edX plugin for learner group selection backed by cohorts",
    long_description=README,
    long_description_content_type="text/markdown",
    author="OpenCraft",
    url="https://github.com/open-craft/group-selection-plugin",
    packages=find_packages(
        include=["group_selection_plugin", "group_selection_plugin.*"],
        exclude=["*tests"],
    ),
    include_package_data=True,
    install_requires=load_requirements("requirements/base.in"),
    python_requires=">=3.11",
    license="AGPL-3.0",
    zip_safe=False,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Framework :: Django",
        "Framework :: Django :: 4.2",
    ],
    entry_points={
        "lms.djangoapp": [
            "group_selection_plugin = group_selection_plugin.apps:GroupSelectionPluginConfig",
        ],
        "cms.djangoapp": [
            "group_selection_plugin = group_selection_plugin.apps:GroupSelectionPluginConfig",
        ],
    },
)
