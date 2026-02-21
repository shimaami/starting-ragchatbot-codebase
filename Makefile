.PHONY: format check lint all

format:
	uv run black backend/

check:
	uv run black --check backend/

lint:
	uv run ruff check backend/

all: format lint
