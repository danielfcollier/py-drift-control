# ==============================================================================
# DRIFT CONTROL | Self-Healing Infrastructure Agent
# ==============================================================================

# Variables
PYTHON := uv run python
APP_MODULE := src.drift_control.daemon
CHAOS_SCRIPT := src/chaos_monkey.py
VENV := .venv

# ==============================================================================
# 🛠️ SETUP & INSTALLATION
# ==============================================================================

.PHONY: help
help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: setup
setup: ## Install uv (if needed) and initialize project
	@echo "Checking for uv..."
	@which uv > /dev/null || (echo "Installing uv..." && curl -LsSf https://astral.sh/uv/install.sh | sh)
	@echo "Setup complete. Run 'make install' to sync dependencies."

.PHONY: install
install: ## Sync dependencies using uv (creates .venv)
	@echo "📦 Syncing dependencies..."
	@uv sync

# ==============================================================================
# 🧪 CODE QUALITY (Linting, Formatting, Typing)
# ==============================================================================

.PHONY: format
format: ## Auto-format code using Ruff
	@echo "🎨 Formatting code..."
	@uv run ruff format src/
	@uv run ruff check --fix src/

.PHONY: lint
lint: ## Run static analysis (Ruff) and type checking (MyPy)
	@echo "🔍 Running Linter (Ruff)..."
	@uv run ruff check src/
	@echo "Types Checking (MyPy)..."
	@uv run mypy src/

.PHONY: test
test: ## Run unit tests
	@echo "🧪 Running Tests..."
	@uv run pytest

# ==============================================================================
# 🎮 RUNTIME & DEMO (The "Suggested Actions")
# ==============================================================================

.PHONY: start
start: ## Start the DriftControl Daemon (The Controller)
	@echo "🚀 Starting Reconciliation Loop..."
	@$(PYTHON) -m $(APP_MODULE)

.PHONY: conflict
conflict: ## Block Port 8080 to force the Daemon to use the Fallback Port
	@echo "🧱 Blocking Port 8080 manually..."
	@docker run --rm -d --name port-blocker -p 8080:80 nginx:alpine > /dev/null
	@echo "⚠️  Port 8080 is now BUSY. The Daemon should fail to bind and switch to 8081."

.PHONY: attack
attack: ## Start the Chaos Monkey (The Adversary)
	@echo "👹 Releasing Chaos Monkey..."
	@$(PYTHON) $(CHAOS_SCRIPT)

.PHONY: stop-demo
stop-demo: ## Helper to forcibly kill the demo container
	@echo "🛑 Cleaning up Docker containers..."
	@docker rm -f critical-service 2>/dev/null || true
	@echo "Cleanup done."

# ==============================================================================
# 🧹 HOUSEKEEPING
# ==============================================================================

.PHONY: clean
clean: ## Clean cache files (.pyc, .pytest_cache, etc)
	@echo "🧹 Cleaning caches..."
	@rm -rf .pytest_cache
	@rm -rf .ruff_cache
	@rm -rf .mypy_cache
	@find . -type d -name "__pycache__" -exec rm -rf {} +

.PHONY: clean-all
clean-all: clean ## Clean caches AND remove the virtual environment
	@echo "🔥 Destroying virtual environment..."
	@rm -rf $(VENV)