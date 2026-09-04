# agent-cli-spec: the contract, its schemas and its conformance kit.
MAELYS_RELEASE_DIR ?= ../maelys-release
PYTHON ?= python3

.PHONY: check test socle-check clean

check: test socle-check

test:
	$(PYTHON) -W error -m unittest discover -s tests
	$(PYTHON) -m py_compile conformance/run.py conformance/validate.py tests/fixtures/conformant.py

# The release socle must not drift; checked whenever a checkout of it sits
# next to this repository.
socle-check:
	@if [ -x $(MAELYS_RELEASE_DIR)/bin/maelys-release ]; then \
		$(MAELYS_RELEASE_DIR)/bin/maelys-release check .; \
	else echo "socle-check: skipped ($(MAELYS_RELEASE_DIR) not found)"; fi

clean:
	rm -rf dist build conformance/__pycache__ tests/__pycache__ tests/fixtures/__pycache__
