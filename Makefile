# Quimera MarkX — Makefile
.PHONY: all install test lint clean docker-up docker-down docker-build

all: lint test

install:
	pip install -r requirements_minimal.txt
	pip install -e . 2>/dev/null || true

test:
	PYTHONPATH=. pytest quimera/tests_fase3/ -v --tb=short -x || true

test-battery:
	PYTHONPATH=. python -m quimera.cli repair test_battery/

lint:
	ruff check quimera/ --select E,F,W --ignore E501,E402,W503
	black --check --diff quimera/ || true

format:
	black quimera/
	ruff check quimera/ --fix --select E,F,W

typecheck:
	mypy quimera/ --ignore-missing-imports --no-error-summary || true

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
	find . -type f -name '.coverage*' -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache

docker-build:
	docker build -f Dockerfile.api -t quimera-api .
	docker build -f Dockerfile -t quimera .

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down -v

docker-logs:
	docker-compose logs -f api

health:
	curl -s http://localhost:8000/api/v1/health | python -m json.tool || echo "API not running"
