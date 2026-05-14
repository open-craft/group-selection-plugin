SHELL := /bin/bash

.PHONY: lint test requirements upgrade

lint:
	black group_selection_plugin

test:
	pytest --cov-report term-missing group_selection_plugin

requirements:
	pip install -q pip-tools
	pip-compile --output-file=requirements/base.txt requirements/base.in
	pip-compile --output-file=requirements/dev.txt requirements/dev.in
