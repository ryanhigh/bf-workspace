#!/usr/bin/env python3
"""Profile registry.

Each entry is an adapter object (callable) that knows how to prepare the
per-run BASEDIR for its profile, compose up/down, and capture events into
the per-run events.jsonl.

Adding a new profile = adding a new module under profiles/<name>/adapter.py
that exposes `prepare(run_dir, scenario, env)` and `tear_down(run_dir, env)`.
"""
from __future__ import annotations
import importlib
import os
import sys
from pathlib import Path
from typing import Any, Callable

ROOT_DEFAULT = Path("/data/DeAtkVer/ethereum-replay-lab")

ADAPTERS: dict[str, str] = {
    "pos-baseline": "profiles.pos_baseline",
    "bunnyfinder": "profiles.bunnyfinder",
    "eclipse": "profiles.eclipse",
    "gethlighting-legacy": "profiles.gethlighting_legacy",
}


def load_adapter(profile: str):
    """Return the loaded Adapter class (callable) for the given profile."""
    if profile not in ADAPTERS:
        raise KeyError(f"unknown profile: {profile}; available={list(ADAPTERS)}")
    sys.path.insert(0, str(ROOT_DEFAULT))
    mod = importlib.import_module(ADAPTERS[profile])
    cls = getattr(mod, "Adapter", None)
    if cls is None:
        raise ImportError(f"module {ADAPTERS[profile]} does not expose class Adapter")
    return cls


def list_profiles() -> list[str]:
    return list(ADAPTERS.keys())


def profile_descriptions() -> dict[str, str]:
    return {
        "pos-baseline":       "Healthy EL+CL PoS private network with 1 EL, 1 CL, 4 validators",
        "bunnyfinder":        "Wrapper around /data/DeAtkVer/Bunnyfinder/bf_workspace author artefact "
                              "(v5 by default). Each run copies the bf_workspace into runs/<run_id>/bf_workspace "
                              "read-only and then launches the requested case compose.",
        "eclipse":            "Eclipse mechanism reproduction (discovery-table + connection-slot). "
                              "Pinned modern ethetcoin on a clique chain with internal bootnode + DNS discovery.",
        "gethlighting-legacy":"Gethlighting mechanism reproduction. Pinned ethereum/client-go:v1.10.20 "
                              "(vulnerable) and v1.11.0 (control) on a clique chain.",
    }