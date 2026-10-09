# agent-cli-spec: the contract, its schemas and its conformance kit.
MAELYS_RELEASE_DIR ?= ../maelys-release
PYTHON ?= python3

MAELYS_CLI_DIR ?= ../maelys-cli

.PHONY: check test socle-check siblings-check clean

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

# The kit and the generated lines on the implementation next door, before a tag: a change that fails a
# correct program, or that a program fails, is seen here and not after the release. Not part of `check`:
# it needs that checkout built, and takes minutes.
siblings-check:
	@if [ -x $(MAELYS_CLI_DIR)/build/release/bin/maelys-hello ]; then set -e; \
		for program in $(MAELYS_CLI_DIR)/build/release/bin/maelys-hello $(MAELYS_CLI_DIR)/build/release/bin/maelys \
				$(MAELYS_CLI_DIR)/build/release/tests/catalog_surface; do \
			[ -x $$program ] || continue; echo "== $$program"; \
			$(PYTHON) conformance/run.py $$program | tail -1; \
			$(PYTHON) tests/invocations.py --apply --format-variable MAELYS_CLI_FORMAT $$program | tail -1; \
		done; \
		for script in python/examples/hello.py python/tests/completion_surface.py; do \
			[ -f $(MAELYS_CLI_DIR)/$$script ] || continue; echo "== $$script"; \
			$(PYTHON) conformance/run.py $(PYTHON) $(MAELYS_CLI_DIR)/$$script | tail -1; \
			$(PYTHON) tests/invocations.py --apply --format-variable MAELYS_CLI_FORMAT $(PYTHON) $(MAELYS_CLI_DIR)/$$script | tail -1; \
		done; \
	else echo "siblings-check: skipped ($(MAELYS_CLI_DIR)/build/release not found)"; fi

clean:
	rm -rf dist build conformance/__pycache__ tests/__pycache__ tests/fixtures/__pycache__
