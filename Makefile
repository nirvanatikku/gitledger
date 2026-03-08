.PHONY: test lint build clean install dev

dev:
	pip install -e ".[dev]"

test:
	pytest tests/ -v

coverage:
	pytest tests/ -v --cov=gitledger --cov-report=term-missing

build:
	python -m build

clean:
	rm -rf dist/ build/ *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +

install:
	pip install .
