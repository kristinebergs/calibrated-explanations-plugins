.PHONY: local-checks-pr lint package-policy test

PYTHON ?= .venv\Scripts\python

local-checks-pr: lint package-policy test

lint:
	$(PYTHON) -m ruff check . --exclude "*.ipynb"

package-policy:
	$(PYTHON) scripts/check_docs_install_commands.py
	$(PYTHON) scripts/check_meta_package_sync.py

test:
	$(PYTHON) -m pytest -p no:cacheprovider packages/calibration/calibrated-explanations-calibration-idr/tests
