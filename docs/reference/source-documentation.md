# Source documentation policy

Source documentation reduces context needed to use or change a boundary. It is
not a second backlog and must not narrate obvious syntax.

## Python module docstrings

Every non-empty first-party Python module should state its responsibility. Add
boundary or invariant detail when a filename alone cannot explain it.

Good:

```python
"""Resolve organization-scoped LLM configs into vendor adapters."""
```

Avoid:

- Markdown headings and generated “Purpose/Architecture/Dependencies” essays;
- speculative `TODO` plans;
- lists that restate imported classes;
- claims not enforced by current code;
- “This module contains functions for...” boilerplate.

Empty package markers may remain empty when they expose no contract.

## Function and method docstrings

Document a callable when a caller needs information beyond its signature:

- domain meaning or invariant;
- transaction/commit behavior;
- external or durable side effects;
- idempotency, retry, ordering, or cancellation semantics;
- authorization/ownership assumptions;
- non-obvious result or error contract;
- provider/resource cleanup obligations.

Do not add a docstring merely to repeat a clear name, type hints, or one-line
property. Private helpers need documentation only when the reason or boundary
is surprising. Prefer renaming unclear code over explaining a poor name.

Registered system-tool function docstrings are executable product contracts:
the tool registry sends them to the LLM as descriptions. Keep those docs
complete enough for safe tool selection, parameters, outcomes, and refusal
behavior. Shortening them is a runtime change, not cosmetic cleanup.

## Classes and protocols

Document public domain types, ports, adapters, repositories, use cases, and
state machines. Explain what the abstraction owns and what it deliberately
does not own. Pydantic and SQLAlchemy field comments belong only where the
field has non-obvious domain meaning.

## TypeScript and TSX

Use JSDoc for exported headless contracts, stores/services with non-obvious
state ownership, protocol payloads, and cleanup-sensitive media/transport
functions. Do not add file banners or comments that restate JSX.

## TODOs

Actionable backlog belongs in a plan or issue. Keep a source `TODO` only when it
names a concrete, local limitation and the current code remains correct without
it. Never use a docstring to propose whole future subsystems.

## Review checklist

- Does the text describe current behavior?
- Does it identify responsibility, invariant, or consequence?
- Is the nearest code a stronger authority than duplicated prose?
- Can the text become false without a nearby code change?
- Would deleting it make a competent reader load more context?

If the last answer is no, delete or shorten it.

Run the source and documentation checks from the server directory:

```bash
uv run python scripts/verify_documentation.py
```
