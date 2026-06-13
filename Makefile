# ============================================
# StackSense Makefile
# ============================================

.PHONY: dev build test lint clean k8s-deploy k8s-status setup

# ── Local Development ─────────────────────────────────────────────
dev:
	docker-compose up --build

dev-backend:
	cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

# ── Build ─────────────────────────────────────────────────────────
build:
	docker-compose build

# ── Testing ───────────────────────────────────────────────────────
test:
	cd backend && python -m pytest tests/ -v --cov=app

lint:
	cd backend && ruff check . && ruff format --check .

# ── Kubernetes ────────────────────────────────────────────────────
k8s-deploy:
	kubectl apply -f kubernetes/namespace.yaml
	kubectl apply -f kubernetes/backend/
	kubectl apply -f kubernetes/frontend/
	kubectl apply -f kubernetes/chromadb/
	kubectl apply -f kubernetes/monitoring/

k8s-status:
	kubectl get all -n stacksense

k8s-delete:
	kubectl delete namespace stacksense

# ── Setup ─────────────────────────────────────────────────────────
setup:
	cp .env.example .env
	cd backend && python -m venv venv && . venv/bin/activate && pip install -r requirements.txt
	cd frontend && npm install

# ── Clean ─────────────────────────────────────────────────────────
clean:
	docker-compose down -v
	rm -rf backend/data/chromadb
	rm -rf /tmp/stacksense_repos
