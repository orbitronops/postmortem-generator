.PHONY: demo test lint clean

demo:
	PYTHONPATH=src python3 -m orbitronops_postmortem generate examples/incident-oomkilled.json

test:
	python -m pytest -q || python -m unittest discover -s tests -v

lint:
	python -m compileall -q src tests

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache
