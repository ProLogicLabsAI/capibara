# capibara — install and dev tasks (requires GNU Make)
#
# Override Python: make dev PY=python3
# Override pip cap: make dev PIP_VERSION_SPEC='>=24.2'
# If .venv is broken: make clean && make dev

# Quieter pip logs (still respects PIP_VERSION_SPEC for the actual pip version)
export PIP_DISABLE_PIP_VERSION_CHECK = 1

.PHONY: help venv upgrade-pip dev-install install dev test lint fmt capibara clean

VENV   ?= .venv
PY     ?= python3.12
PYTHON := $(VENV)/bin/python
RUFF   := $(VENV)/bin/ruff
PYTEST := $(VENV)/bin/pytest

PIP = $(PYTHON) -m pip

# Forward to .venv/bin/capibara, e.g. make capibara ARGS='--help'
ARGS ?=

# pip 26.x: KeyError _PYPROJECT_HOOKS_BUILD_BACKEND on some editable installs — default cap at 25.x
PIP_VERSION_SPEC ?= >=24.2,<26

help:
	@echo "capibara — targets:"
	@echo "  make venv          Create $(VENV) (if missing)"
	@echo "  make upgrade-pip   pip install --upgrade pip setuptools wheel (see PIP_VERSION_SPEC)"
	@echo "  make dev-install   upgrade-pip + pip install -e \".[dev]\""
	@echo "  make install       upgrade-pip + pip install -e ."
	@echo "  make dev             alias for dev-install"
	@echo "  make test / lint / fmt  (need dev-install once per invocation)"
	@echo "  make capibara ARGS='--help'   Run CLI via $(VENV)/bin/capibara"
	@echo "  make clean"
	@echo "  PIP_VERSION_SPEC=$(PIP_VERSION_SPEC)  PY=$(PY)"

$(VENV)/bin/python:
	@test -x "$$(command -v $(PY) 2>/dev/null)" || (echo "Error: $(PY) not found. Install Python 3.12+ or set PY=python3" >&2; exit 1)
	$(PY) -m venv $(VENV)

venv: $(VENV)/bin/python

upgrade-pip: $(VENV)/bin/python
	$(PIP) install --upgrade "pip$(PIP_VERSION_SPEC)" setuptools wheel

dev-install: upgrade-pip
	$(PIP) install -e ".[dev]"

install: upgrade-pip
	$(PIP) install -e .

dev: dev-install

test: dev-install
	$(PYTEST) -q

lint: dev-install
	$(RUFF) check src tests
	$(RUFF) format --check src tests

fmt: dev-install
	$(RUFF) format src tests

capibara: dev-install
	$(VENV)/bin/capibara $(ARGS)

clean:
	rm -rf $(VENV)
