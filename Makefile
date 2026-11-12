.PHONY: install seed run test smoke clean

install:
	sh install.sh

seed:
	python3 -m app.seed

run:
	python3 -m app.server

test:
	python3 -m pytest tests -q

smoke:
	python3 tests/smoke.py

clean:
	rm -rf data .pytest_cache
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
