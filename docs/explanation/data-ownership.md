# Data ownership and deletion

The organization owns its platform data. Eylo processes that data and provides
tools for lifecycle control; it does not redefine the organization's contract
with an external vendor.

## Ownership graph

- Organization owns members, Agents, provider configs, integrations,
  knowledgebases, contacts, campaigns, and operational records.
- A contact participates in conversations.
- A conversation owns participants and messages.
- A campaign references contacts and an Agent revision.
- A call/voice session references its conversation and may reference a campaign
  attempt.
- Files, chunks, memories, recordings, and transcripts retain their exact
  organization and owning resource.

References do not reverse ownership. Deleting a call cannot delete its campaign
or contacts. Deleting a campaign cannot delete contacts. Deleting a conversation
does not authorize deletion of organization knowledge.

## Tenant isolation

Authenticated context supplies organization/contact ownership. Repositories
filter by organization, and composite foreign keys preserve ownership across
related rows. A caller cannot broaden scope with a model-generated identifier
or storage path. Hidden/mismatched resources return `404`.

## Files and object storage

Operators choose a bucket or trusted root. The platform builds every deeper key
from organization and owning resource IDs. Conversation uploads, knowledge
sources, and recordings cannot select another organization's namespace.

## External providers

Deleting an Eylo record removes or redacts the data Eylo owns according to the
module's lifecycle. It does not imply that Twilio, Google, AWS, or another
provider deleted its copy. The organization must exercise its provider-side
rights through that provider.

## Async controls

Recording, redaction, memory formation, and other data controls may run after a
live call or conversation. Their failure is visible and retryable but does not
interrupt the primary product flow unless a future explicit policy says it
must.
