#!/usr/bin/env python3
"""Tiny CLI wrapper that prints the project prefix (used by `make ps`).

Usage:  python3 controller/project_prefix.py
Outputs: a regex fragment that matches every project-owned docker resource.
"""
import sys
from prefix import PREFIX

# We anchor on the prefix; containers/named-volumes use the literal prefix,
# networks use the literal prefix too.
sys.stdout.write(f"^{PREFIX}")