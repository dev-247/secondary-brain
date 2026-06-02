.PHONY: audit chat compile doctor eval ingest smoke smoke-retrieval status test web

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

smoke-retrieval:
	$(PYTHON) -m scripts.eval_smoke

eval: smoke-retrieval

ingest:
	$(PYTHON) main.py ingest

chat:
	$(PYTHON) main.py chat

web:
	$(PYTHON) main.py web

smoke: compile test doctor status audit smoke-retrieval
