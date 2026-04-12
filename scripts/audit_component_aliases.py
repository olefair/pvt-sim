#!/usr/bin/env python3
"""Audit the component alias contract across the DB and app input surfaces."""

from __future__ import annotations

import sys

from pvtapp.component_catalog import DEFAULT_COMPONENT_ROWS, STANDARD_COMPONENTS
from pvtcore.models import build_component_alias_index, load_components, resolve_component_id


def main() -> None:
    components = load_components()

    try:
        alias_index = build_component_alias_index(components)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    print(f"Canonical components: {len(components)}")
    print(f"Accepted component tokens: {len(alias_index)}")

    errors = 0

    print("\nStandard component picker audit:")
    for token in STANDARD_COMPONENTS:
        try:
            canonical = resolve_component_id(token, components)
            print(f"  OK    {token} -> {canonical}")
        except KeyError as exc:
            errors += 1
            print(f"  ERROR {token}: {exc}")

    print("\nDefault composition rows audit:")
    for token, _fraction in DEFAULT_COMPONENT_ROWS:
        try:
            canonical = resolve_component_id(token, components)
            print(f"  OK    {token} -> {canonical}")
        except KeyError as exc:
            errors += 1
            print(f"  ERROR {token}: {exc}")

    if errors:
        print(f"\nFAILED: Found {errors} component alias contract issue(s).")
        sys.exit(1)

    print("\nSUCCESS: Component alias contract audit passed.")


if __name__ == "__main__":
    main()
