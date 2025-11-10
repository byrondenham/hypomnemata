.PHONY: venv dev lint test cov build install

venv:
	python -m venv .venv && . .venv/bin/activate && pip install -U pip

dev:
	. .venv/bin/activate && pip install -e ".[dev]"

lint:
	. .venv/bin/activate && ruff check src tests && mypy src

test:
	. .venv/bin/activate && pytest -q

cov:
	. .venv/bin/activate && pytest --cov=hypomnemata --cov-report=term-missing

build:
	. .venv/bin/activate && python -m build

install:
	. .venv/bin/activate && pip install -e .
