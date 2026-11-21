.PHONY: dev-backend dev-frontend dev-mock test test-live build knowledge
dev-backend:  ; cd backend && uv run uvicorn app.main:app --reload --port 8000
dev-frontend: ; cd frontend && npm run dev
dev-mock:     ; cd frontend && VITE_USE_MOCKS=true npm run dev
test:         ; cd backend && uv run pytest && cd ../frontend && npm run build
test-live:    ; cd backend && uv run pytest -m live
knowledge:    ; cd backend && uv run --with pypdf --with python-docx python ../scripts/fetch_knowledge.py
