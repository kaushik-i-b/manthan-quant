PY=backend/.venv/bin
ENGINE?=http://127.0.0.1:8741

.PHONY: install test backend frontend demo probe

install:
	python3 -m venv backend/.venv
	$(PY)/pip install -r backend/requirements.txt
	cd frontend && npm install

test:
	cd backend && .venv/bin/pytest -q
	cd frontend && npm test

backend:
	cd backend && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8741

frontend:
	cd frontend && npm run dev

demo:
	bash scripts/demo.sh

probe:
	$(PY)/python scripts/check_venue.py
