# Configure and rotate a provider

Provider configurations are organization-owned, encrypted, revisioned, and
capability-specific. Saving, verification, enabling, and Agent binding are
separate actions.

## Create a configuration

1. Open **Sockets**, then select the capability you are configuring, such as
   **LLM**, **STT**, or **Storage**.
2. Open the required capability.
3. Choose a vendor from the server-provided catalog.
4. Complete the vendor-specific fields.
5. Save the configuration.
6. Run **Verify provider**.
7. Enable the configuration.

A ready configuration is configured, verified, enabled, and not deleted.
Verification contacts the actual vendor through the capability's verification
pipeline. It is not a schema-only check.

## Bind it to an Agent

Open the Agent draft, select the relevant configuration, save, then publish a
new Agent revision. Runtime work pins the configuration ID and revision
selected by that immutable Agent revision.

An organization may keep multiple configurations for the same capability.
Eylo does not select one implicitly.

## Rotate credentials or settings

1. Open the existing configuration.
2. Edit the values that changed.
3. Save to create the next configuration revision.
4. Verify the new revision.
5. Publish affected Agent drafts when their pinned selection must change.

Secret fields left blank during an ordinary update retain their encrypted
value only when the API contract explicitly supports secret preservation.
Never copy masked values back as credentials.

## Handle embedding changes

Changing the embedding configuration or its revision invalidates vectors made
under the previous embedding space. Knowledgebases and memories expose a
reindex-required state. Run their reindex actions before treating semantic
retrieval as current. Eylo rejects mixed embedding spaces instead of silently
combining incompatible vectors.

## Delete a configuration

Deletion checks live references. Remove or replace Agent, knowledgebase,
memory, voice, or other bindings first. A reference conflict is a product
guard, not a reason to delete rows directly.
