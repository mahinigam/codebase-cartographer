#!/bin/bash
set -e

echo "Running Backend Tests and Coverage..."
cd backend
uv run pytest --cov=app --cov-report=term-missing --cov-fail-under=90
uv run ruff check app tests
uv run mypy app

echo "Running Frontend Tests and Coverage..."
cd ../frontend
npm run test -- --coverage
npx tsc --noEmit

echo "All checks passed!"
