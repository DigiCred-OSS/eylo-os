#!/usr/bin/env python3
"""Verify the platform-neutral and domain-driven import boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[1]
EYLO_ROOT = SERVER_ROOT / "eylo"


def python_files(relative_root: str) -> list[Path]:
    """Return first-party Python files below one architecture boundary."""
    return sorted((EYLO_ROOT / relative_root).rglob("*.py"))


def imported_modules(path: Path) -> set[str]:
    """Return absolute import targets without executing the inspected module."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    relative = path.relative_to(SERVER_ROOT).with_suffix("")
    package_parts = list(relative.parts[:-1])
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parent_count = node.level - 1
                if parent_count > len(package_parts):
                    continue
                base_parts = package_parts[: len(package_parts) - parent_count]
            else:
                base_parts = []
            module_parts = node.module.split(".") if node.module else []
            imported_base = ".".join([*base_parts, *module_parts])
            if imported_base:
                imports.add(imported_base)
            imports.update(
                ".".join(part for part in (imported_base, alias.name) if part)
                for alias in node.names
                if alias.name != "*"
            )
    return imports


def validate_boundary(
    files: list[Path],
    forbidden_prefixes: tuple[str, ...],
    errors: list[str],
    *,
    allowed_prefixes: tuple[str, ...] = (),
) -> int:
    """Reject imports that cross one documented architecture boundary."""
    inspected = 0
    for path in files:
        for imported in imported_modules(path):
            inspected += 1
            is_forbidden = any(
                imported == prefix or imported.startswith(f"{prefix}.")
                for prefix in forbidden_prefixes
            )
            is_allowed = any(
                imported == prefix or imported.startswith(f"{prefix}.")
                for prefix in allowed_prefixes
            )
            if is_forbidden and not is_allowed:
                relative = path.relative_to(SERVER_ROOT)
                errors.append(f"{relative} imports forbidden module {imported}")
    return inspected


def main() -> int:
    """Enforce the standalone framework and modules/sockets separation."""
    errors: list[str] = []
    framework_files = python_files("framework")
    module_files = python_files("modules")
    socket_files = python_files("sockets")

    inspected = validate_boundary(
        framework_files,
        ("eylo",),
        errors,
        allowed_prefixes=("eylo.framework",),
    )
    inspected += validate_boundary(module_files, ("eylo.sockets",), errors)
    inspected += validate_boundary(socket_files, ("eylo.modules",), errors)

    if errors:
        print("DIY-FOUNDATION-VERIFY-FAILED")
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        "DIY-FOUNDATION-VERIFY-OK "
        f"framework_files={len(framework_files)} "
        f"module_files={len(module_files)} socket_files={len(socket_files)} "
        f"imports={inspected}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
