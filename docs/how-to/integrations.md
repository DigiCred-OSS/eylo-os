# Install and grant curated integrations

Curated integrations are code-owned vendor tools, not capability providers and
not imported OpenAPI operations.

## Install a vendor

1. Open **Platform → Integrations**.
2. Select a curated vendor.
3. Choose one of the vendor's supported auth kinds.
4. Enter organization app credentials or direct credentials as requested.
5. Complete OAuth in the provider window when applicable.
6. Check **Configured integrations** and **Connections**.

Connections may be organization-owned or contact-owned. Credentials are never
returned by list/detail APIs.

## Grant tools to an Agent

1. Open the Agent draft.
2. Select exact tools such as `googlecalendar.list_events` or
   `github.get_issue`.
3. Save and publish the Agent.

The Agent-to-tool relation is unique. Installing a vendor does not grant every
tool to every Agent.

## Set mutation policy

Each curated tool is declared read or mutation. Operators may set execution to
automatic, approval-required, or disabled. Policy is read at execution time.
Mutations run through the durable outbound owner and receive one receipt per
mutation attempt.

## Add a curated integration vendor

Create a vendor package under
`eylo/pipelines/integrations_v2/vendors/<vendor>/` with:

- `definition.py` for identity, origin, auth, scopes, and static headers;
- `tools.py` for typed Pydantic inputs and `@curated_tool` callables;
- registration in `_VENDOR_MODULES`.

Tools receive only `VendorToolContext`. Use `ctx.read()` for non-mutating calls
and `ctx.mutate()` for declared mutations. Use relative paths; the transport
pins credentials to the vendor origin. Never access DB sessions, repositories,
or raw credentials from tool code.
