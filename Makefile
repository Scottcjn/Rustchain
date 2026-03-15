.PHONY: install run test lint clean docker

# Install dependencies
install:
	pip install -r requirements.txt

# Run the node
run:
	python node/rustchain_v2_integrated_v2.2.1_rip200.py

# Run the miner
mine:
	clawrtc start

# Run tests
test:
	pytest tests/ -v

# Lint
lint:
	ruff check .
	ruff format --check .

# Format
format:
	ruff format .

# Docker build
docker:
	docker build -t rustchain-node .

# Docker run
docker-run:
	docker compose up -d

# Health check
health:
	curl -s https://rustchain.org/health | python -m json.tool

# Status
status:
	clawrtc status

# Clean
clean:
	find . -name __pycache__ -type d -exec rm -rf {} +
	find . -name "*.pyc" -delete
	rm -rf .pytest_cache .ruff_cache

# Help
help:
	@echo "Available targets:"
	@echo "  install    - Install Python dependencies"
	@echo "  run        - Start the node"
	@echo "  mine       - Start mining"
	@echo "  test       - Run tests"
	@echo "  lint       - Check code style"
	@echo "  format     - Auto-format code"
	@echo "  docker     - Build Docker image"
	@echo "  docker-run - Start with Docker Compose"
	@echo "  health     - Check node health"
	@echo "  status     - Check miner status"
	@echo "  clean      - Remove build artifacts"
