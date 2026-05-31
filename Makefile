.PHONY: audit chat compile doctor ingest smoke status test

PYTHON := uv run python

test:
	$(PYTHON) -m unittest

compile:
	$(PYTHON) -m compileall main.py scripts tests

doctor:
	$(PYTHON) main.py doctor

status:
	$(PYTHON) main.py status

audit:
	$(PYTHON) main.py audit

ingest:
	$(PYTHON) main.py ingest

chat:
	$(PYTHON) main.py chat

smoke: compile test doctor status audit
