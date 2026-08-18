# Curated integration catalog

The curated registry is the executable catalog. Vendor and tool contracts live
in Python; installation rows store organization choices, connections, tool
policy, and Agent grants rather than duplicate tool schemas.

## Vendors and tools

The current registry carries 29 vendors and 148 tools.

| Vendor | Auth | Tools |
| --- | --- | ---: |
| Airtable | API key | 5 |
| Asana | API key | 6 |
| Calendly | OAuth 2, API key | 5 |
| Confluence | Basic, OAuth 2 | 5 |
| Dropbox | OAuth 2 | 6 |
| Freshdesk | Basic | 6 |
| GitHub | OAuth 2, API key | 7 |
| GitLab | API key | 6 |
| Gmail | OAuth 2 | 8 |
| Google Calendar | OAuth 2 | 6 |
| Google Docs | OAuth 2 | 4 |
| Google Drive | OAuth 2 | 6 |
| Google Sheets | OAuth 2 | 6 |
| Google Tasks | OAuth 2 | 5 |
| HubSpot | OAuth 2 | 6 |
| Intercom | OAuth 2, API key | 5 |
| Jira | Basic, OAuth 2 | 4 |
| Linear | OAuth 2, API key | 3 |
| Notion | OAuth 2, API key | 5 |
| Outlook | OAuth 2 | 4 |
| PagerDuty | API key | 4 |
| Pipedrive | API key | 5 |
| Sentry | OAuth 2, API key | 4 |
| Shopify | API key | 5 |
| Slack | OAuth 2 | 4 |
| Stripe | API key | 5 |
| Typeform | OAuth 2, API key | 3 |
| Zendesk | Basic | 6 |
| Zoom | OAuth 2 | 4 |

Exact names, descriptions, Pydantic inputs, effects, and scopes are returned by
the curated-vendor API and defined under
`eylo/pipelines/integrations_v2/vendors/`.

## Registry contract

- `CuratedVendorSpec`: identity, categories, fixed or installation-specific
  origin, auth kinds, API-key placement, OAuth metadata, scopes, and static
  non-secret headers.
- `CuratedToolSpec`: stable `vendor.name` wire ID, display text, effect, input
  model, required scopes, and Python handler.
- `VendorToolContext`: connection identity plus origin-bound `read()` and
  durable `mutate()` methods.
- `ToolExecutionMode`: `auto`, `requires_approval`, or `disabled`, read live at
  execution.

## Security boundary

Curated tools receive neither credentials nor DB access. They address relative
paths only. The transport pins the configured credential to the registered or
installation-specific origin, rejects redirects, bounds replies, and separates
read calls from durable mutations.

## Persistence relationships

- installation: one organization's decision to configure a vendor;
- connection: one organization or contact credential authority;
- installed-tool policy: execution mode for a registered tool;
- Agent grant: exact Agent-to-tool relation, copied into published revisions;
- OAuth state: short-lived authorization transaction;
- outbound receipt: durable proof for each mutation attempt.

Installing a vendor does not grant its tools to an Agent. Connecting an end
user does not expose that credential to another contact or organization.
