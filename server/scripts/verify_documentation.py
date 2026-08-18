#!/usr/bin/env python3
"""Verify Eylo documentation coverage, links, diagrams, and source docstrings."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from urllib.parse import unquote

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = REPO_ROOT / "docs"

REQUIRED_PAGES = (
    "README.md",
    "AGENTS.md",
    "docs/README.md",
    "docs/tutorials/first-agent.md",
    "docs/how-to/README.md",
    "docs/reference/README.md",
    "docs/explanation/README.md",
    "docs/diagrams/architecture.md",
    "docs/diagrams/data-flows.md",
)

REFERENCE_COVERAGE = (
    ("server/eylo/modules", "docs/reference/modules.md"),
    ("server/eylo/pipelines", "docs/reference/pipelines.md"),
    ("server/eylo/sockets", "docs/reference/providers.md"),
    ("server/eylo/products", "docs/reference/modules.md"),
)

PYTHON_ROOTS = (
    "server/eylo",
    "server/scripts",
    "cli",
)

MERMAID_STARTS = (
    "block-beta",
    "classDiagram",
    "erDiagram",
    "flowchart",
    "gantt",
    "gitGraph",
    "graph",
    "journey",
    "mindmap",
    "packet-beta",
    "pie",
    "quadrantChart",
    "requirementDiagram",
    "sankey-beta",
    "sequenceDiagram",
    "stateDiagram",
    "timeline",
    "xychart-beta",
)

MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def markdown_files() -> list[Path]:
    """Return the canonical documentation surface."""
    files = [REPO_ROOT / "README.md", REPO_ROOT / "AGENTS.md"]
    files.extend(sorted(DOCS_ROOT.rglob("*.md")))
    return files


def python_files() -> list[Path]:
    """Return first-party Python sources covered by the docstring policy."""
    files: set[Path] = {REPO_ROOT / "server/main.py"}
    for relative_root in PYTHON_ROOTS:
        root = REPO_ROOT / relative_root
        files.update(
            path
            for path in root.rglob("*.py")
            if "__pycache__" not in path.parts and ".venv" not in path.parts
        )
    return sorted(path for path in files if path.exists())


def validate_required_pages(errors: list[str]) -> None:
    """Require one entry point for every Diátaxis document kind."""
    for relative in REQUIRED_PAGES:
        if not (REPO_ROOT / relative).is_file():
            errors.append(f"missing required documentation page: {relative}")


def local_link_target(source: Path, raw_target: str) -> Path | None:
    """Resolve a Markdown target when it refers to a local file."""
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    target = target.split(maxsplit=1)[0]
    if not target or target.startswith(("#", "http://", "https://", "mailto:")):
        return None
    without_fragment = unquote(target.split("#", 1)[0])
    if not without_fragment:
        return None
    if without_fragment.startswith("/"):
        return REPO_ROOT / without_fragment.lstrip("/")
    return (source.parent / without_fragment).resolve()


def validate_links(files: list[Path], errors: list[str]) -> int:
    """Check that every relative Markdown link resolves inside the repository."""
    checked = 0
    for source in files:
        text = source.read_text()
        for match in MARKDOWN_LINK.finditer(text):
            target = local_link_target(source, match.group(1))
            if target is None:
                continue
            checked += 1
            if not target.exists():
                relative_source = source.relative_to(REPO_ROOT)
                errors.append(
                    f"broken local link in {relative_source}: {match.group(1)}"
                )
                continue
            try:
                target.relative_to(REPO_ROOT)
            except ValueError:
                relative_source = source.relative_to(REPO_ROOT)
                errors.append(
                    f"local link leaves repository in {relative_source}: "
                    f"{match.group(1)}"
                )
    return checked


def package_names(relative_root: str) -> set[str]:
    """Return non-empty top-level Python packages below one architecture layer."""
    root = REPO_ROOT / relative_root
    names: set[str] = set()
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        relative = path.relative_to(root)
        if len(relative.parts) == 1:
            if path.name != "__init__.py":
                names.add(path.name)
            continue
        names.add(relative.parts[0])
    return names


def validate_reference_coverage(errors: list[str]) -> int:
    """Require every top-level backend package in its canonical reference page."""
    covered = 0
    for source_root, reference_page in REFERENCE_COVERAGE:
        reference = (REPO_ROOT / reference_page).read_text()
        for package in sorted(package_names(source_root)):
            covered += 1
            if f"`{package}`" not in reference:
                errors.append(
                    f"{reference_page} does not cover {source_root}/{package}"
                )
    return covered


def docstring_nodes(tree: ast.AST):
    """Yield nodes that can own a Python docstring."""
    for node in ast.walk(tree):
        if isinstance(
            node,
            (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            yield node


def node_label(node: ast.AST) -> str:
    """Return a stable source label for a docstring owner."""
    if isinstance(node, ast.Module):
        return "module"
    return getattr(node, "name", type(node).__name__)


def validate_docstrings(errors: list[str]) -> tuple[int, int]:
    """Enforce current-behavior module docs and reject backlog-style docstrings."""
    modules = 0
    inspected_docstrings = 0
    for path in python_files():
        source = path.read_text()
        if not source.strip():
            continue
        relative = path.relative_to(REPO_ROOT)
        try:
            tree = ast.parse(source, filename=str(relative))
        except SyntaxError as error:
            errors.append(f"cannot parse {relative}: {error}")
            continue
        modules += 1
        if ast.get_docstring(tree, clean=False) is None:
            errors.append(f"non-empty Python module lacks docstring: {relative}")
        for node in docstring_nodes(tree):
            doc = ast.get_docstring(node, clean=False)
            if not doc:
                continue
            inspected_docstrings += 1
            location = f"{relative}:{getattr(node, 'lineno', 1)}:{node_label(node)}"
            if "TODO" in doc:
                errors.append(f"TODO belongs outside docstring: {location}")
            if any(line.lstrip().startswith("#") for line in doc.splitlines()):
                errors.append(f"Markdown heading inside docstring: {location}")
    return modules, inspected_docstrings


def mermaid_blocks(source: Path, errors: list[str]) -> list[str]:
    """Extract closed Mermaid fences and reject malformed block declarations."""
    blocks: list[str] = []
    active: list[str] | None = None
    for line_number, line in enumerate(source.read_text().splitlines(), start=1):
        if line.strip() == "```mermaid":
            if active is not None:
                errors.append(
                    f"nested Mermaid fence in {source.relative_to(REPO_ROOT)}:"
                    f"{line_number}"
                )
            active = []
            continue
        if line.strip() == "```" and active is not None:
            content = "\n".join(active).strip()
            blocks.append(content)
            active = None
            continue
        if active is not None:
            active.append(line)
    if active is not None:
        errors.append(f"unclosed Mermaid fence in {source.relative_to(REPO_ROOT)}")
    for index, block in enumerate(blocks, start=1):
        first_line = next((line.strip() for line in block.splitlines() if line.strip()), "")
        if not first_line.startswith(MERMAID_STARTS):
            errors.append(
                f"unknown Mermaid declaration in {source.relative_to(REPO_ROOT)} "
                f"block {index}: {first_line or '<empty>'}"
            )
    return blocks


def validate_mermaid(files: list[Path], errors: list[str]) -> int:
    """Validate Mermaid fence structure and the required diagram inventory."""
    counts: dict[str, int] = {}
    total = 0
    for source in files:
        blocks = mermaid_blocks(source, errors)
        if blocks:
            relative = str(source.relative_to(REPO_ROOT))
            counts[relative] = len(blocks)
            total += len(blocks)
    minimums = {
        "docs/diagrams/architecture.md": 4,
        "docs/diagrams/data-flows.md": 6,
    }
    for relative, minimum in minimums.items():
        if counts.get(relative, 0) < minimum:
            errors.append(
                f"{relative} needs at least {minimum} Mermaid diagrams; "
                f"found {counts.get(relative, 0)}"
            )
    return total


def main() -> int:
    """Run all documentation checks and return a shell exit code."""
    errors: list[str] = []
    files = markdown_files()
    validate_required_pages(errors)
    links = validate_links(files, errors)
    packages = validate_reference_coverage(errors)
    modules, docstrings = validate_docstrings(errors)
    diagrams = validate_mermaid(files, errors)

    if errors:
        print("DOCUMENTATION-VERIFY-FAILED")
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        "DOCUMENTATION-VERIFY-OK "
        f"pages={len(files)} links={links} packages={packages} "
        f"python_modules={modules} docstrings={docstrings} diagrams={diagrams}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
