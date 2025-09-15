.PHONY: interview trace plan build run

interview:
	@python interview/engine.py || true

trace:
	@python traceability/trace_gate.py

plan:
	@python gen_universal.py

build: plan  ## alias (builder writes artifacts)

run:
	@uvicorn services.backend.app:app --port 8000 --reload
