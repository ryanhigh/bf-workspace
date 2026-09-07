#!/usr/bin/env python3
"""Single source of truth for the project's docker resource prefix.

Every container / network / volume / image label created by this project
starts with `erl_`. `clean` and `ps` use this prefix to avoid touching
anything that does not belong to the project.
"""
PREFIX = "erl_"