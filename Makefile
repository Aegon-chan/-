# =============================================================================
# Research Agent Makefile
# =============================================================================
.PHONY: install dev test lint clean docker-build docker-run build-exe docs

# ── Environment ──────────────────────────────────────────────────────────────

install:
	powershell -ExecutionPolicy Bypass -File scripts/setup.ps1

activate:
	@echo "Run: .venv\Scripts\Activate.ps1"

dev:
	powershell -ExecutionPolicy Bypass -File scripts/dev.ps1

# ── Quality ──────────────────────────────────────────────────────────────────

test:
	pytest tests/ -v --timeout=60 --tb=short

test-coverage:
	pytest tests/ -v --cov=backend --cov-report=term-missing --timeout=120

lint:
	ruff check backend/ tests/

lint-fix:
	ruff check --fix backend/ tests/

# ── Docker ───────────────────────────────────────────────────────────────────

docker-build:
	docker compose build

docker-run:
	docker compose up -d

docker-stop:
	docker compose down

docker-logs:
	docker compose logs -f

# ── Packaging ────────────────────────────────────────────────────────────────

build-exe:
	powershell -ExecutionPolicy Bypass -File scripts/build_exe.ps1

# ── Database ─────────────────────────────────────────────────────────────────

db-migrate:
	alembic -c backend/alembic.ini upgrade head

db-rollback:
	alembic -c backend/alembic.ini downgrade -1

db-revision:
	alembic -c backend/alembic.ini revision --autogenerate -m "$(msg)"

db-check:
	alembic -c backend/alembic.ini check

# ── Docs ─────────────────────────────────────────────────────────────────────

docs:
	@echo "Open docs/guide.md for user documentation"

# ── Version ──────────────────────────────────────────────────────────────────

version:
	python -c "import tomli; print(tomli.load(open(\"pyproject.toml\",\"rb\"))[\"project\"][\"version\"])"

# ── Cleanup ──────────────────────────────────────────────────────────────────

clean:
	rmdir /s /q .pytest_cache 2>nul || true
	rmdir /s /q .ruff_cache 2>nul || true
	rmdir /s /q backend/__pycache__ 2>nul || true
	rmdir /s /q backend/**/__pycache__ 2>nul || true
	rmdir /s /q backend/**/**/__pycache__ 2>nul || true
	rmdir /s /q tests/__pycache__ 2>nul || true
	rmdir /s /q tests/**/__pycache__ 2>nul || true
	rmdir /s /q build 2>nul || true
	rmdir /s /q dist 2>nul || true
	del /q *.spec 2>nul || true
