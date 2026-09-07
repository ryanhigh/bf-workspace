# Ethereum Replay Lab — Makefile
#
# Single-entrypoint for the operator. Each target calls a small script
# under controller/. The Makefile exists so that `./Makefile` and `make X`
# have the same surface; we do not put logic in this file.

SHELL := /bin/bash
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
ACTIVE_PROFILE ?= pos-baseline
ACTIVE_SCENARIO ?= normal

# 12-byte hex run id prefix, default = epoch seconds in hex + 4 random bytes
RUN_ID ?= $(shell date +%s)-$(shell od -An -N4 -tx1 /dev/urandom | tr -d ' \n')

PYTHON ?= python3

.PHONY: help doctor status build baseline run repeat collect analyze clean \
        ps ls-runs smoke-baseline smoke-bunnyfinder \
        clean-all-networks clean-all-volumes

help:
	@echo "Targets:"
	@echo "  doctor               — host + artefact + capability check, writes docs/STATUS.md"
	@echo "  status               — append-only evidence capture (alias of doctor)"
	@echo "  build                — pull/build only the images needed by \$$ACTIVE_PROFILE"
	@echo "  baseline             — one healthy \$$ACTIVE_PROFILE run (no attack) into runs/<run_id>"
	@echo "  run                  — one \$$ACTIVE_PROFILE+\$$ACTIVE_SCENARIO run into runs/<run_id>"
	@echo "  repeat               — same scenario N times (N=\$$REPEAT_COUNT, default 3)"
	@echo "  collect              — normalise outputs into runs/<run_id>/events.jsonl + manifest.json"
	@echo "  analyze              — produce result.json from events.jsonl + manifest.json"
	@echo "  clean                — tear down ONLY this project's containers, networks, volumes"
	@echo "  ps / ls-runs         — list running containers / past runs"
	@echo ""
	@echo "Vars:"
	@echo "  ACTIVE_PROFILE       (default pos-baseline; also: bunnyfinder, eclipse, gethlighting-legacy)"
	@echo "  ACTIVE_SCENARIO      (default normal; also: basic, exante, sandwich, ..)"
	@echo "  RUN_ID               (default: <epoch_secs>-<4 random bytes>)"
	@echo "  REPEAT_COUNT         (default 3)"
	@echo "  CLEAN_INCLUDE_VOLUMES=1 to also drop this project's named volumes"

doctor:
	@$(PYTHON) $(ROOT)/controller/doctor.py $(ROOT)

status:
	@$(PYTHON) $(ROOT)/controller/capture_status.py all

build:
	@ACTIVE_PROFILE=$(ACTIVE_PROFILE) $(PYTHON) $(ROOT)/controller/build.py $(ROOT)

baseline:
	@$(MAKE) run ACTIVE_SCENARIO=normal RUN_ID=$(RUN_ID)

run:
	@ACTIVE_PROFILE=$(ACTIVE_PROFILE) ACTIVE_SCENARIO=$(ACTIVE_SCENARIO) RUN_ID=$(RUN_ID) \
	  $(PYTHON) $(ROOT)/controller/run.py $(ROOT)

repeat:
	@for i in $$(seq 1 $${REPEAT_COUNT:-3}); do \
	  rid=$(RUN_ID_BASE)-$$i; \
	  echo ">>> repeat $$i / $${REPEAT_COUNT:-3}  rid=$$rid"; \
	  ACTIVE_PROFILE=$(ACTIVE_PROFILE) ACTIVE_SCENARIO=$(ACTIVE_SCENARIO) RUN_ID=$$rid \
	    $(PYTHON) $(ROOT)/controller/run.py $(ROOT) || exit 1; \
	done

collect:
	@RUN_ID=$(RUN_ID) ACTIVE_PROFILE=$(ACTIVE_PROFILE) $(PYTHON) $(ROOT)/controller/collect.py $(ROOT)

analyze:
	@RUN_ID=$(RUN_ID) ACTIVE_PROFILE=$(ACTIVE_PROFILE) $(PYTHON) $(ROOT)/controller/analyze.py $(ROOT)

ps:
	@docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Networks}}' | \
	    (head -1; grep -E "$(shell $(PYTHON) $(ROOT)/controller/project_prefix.py)" || true)

ls-runs:
	@ls -1 $(ROOT)/runs 2>/dev/null | sort || echo "(no runs yet)"

clean:
	@ACTIVE_PROFILE=$(ACTIVE_PROFILE) RUN_ID=$(RUN_ID) CLEAN_INCLUDE_VOLUMES=$(CLEAN_INCLUDE_VOLUMES) \
	  $(PYTHON) $(ROOT)/controller/clean.py $(ROOT)

# ---- admin / debug ----

smoke-baseline:
	@ACTIVE_PROFILE=pos-baseline ACTIVE_SCENARIO=normal \
	  $(PYTHON) $(ROOT)/controller/run.py $(ROOT)

smoke-bunnyfinder:
	@ACTIVE_PROFILE=bunnyfinder ACTIVE_SCENARIO=basic \
	  $(PYTHON) $(ROOT)/controller/run.py $(ROOT)

clean-all-networks:
	@echo "Removing ONLY networks starting with the project prefix"
	@for n in $$(docker network ls --format '{{.Name}}' | grep -E '^erl_' || true); do \
	    echo "  rm $$n"; docker network rm "$$n" || true; \
	done

clean-all-volumes:
	@echo "Removing ONLY volumes starting with the project prefix"
	@for v in $$(docker volume ls --format '{{.Name}}' | grep -E '^erl_' || true); do \
	    echo "  rm $$v"; docker volume rm "$$v" || true; \
	done