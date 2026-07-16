.PHONY: local-checks-pr lint package-policy test

PYTHON ?= .venv\Scripts\python

local-checks-pr: lint package-policy test

lint:
	$(PYTHON) -m ruff check . --exclude "*.ipynb"

package-policy:
	$(PYTHON) scripts/validate_repo_structure.py
	$(PYTHON) scripts/lifecycle.py check

test:
	$(PYTHON) -m pytest -p no:cacheprovider tests -q
