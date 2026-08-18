# Build and publish an Agent

## Create the draft

1. Open **Platform → Agents**.
2. Create either a conversational or background Agent. The kind is immutable.
3. Write the primary directive and instructions.
4. Select explicit provider configurations.
5. Grant only the platform, MCP, or curated tools the Agent needs.
6. Add knowledgebase grants, memory config, voice config, background-Agent
   attachments, or swarm membership only when the Agent's use case needs them.
7. Save the draft.

Draft changes are resumable in the console but have no runtime authority.

## Publish

Publish the draft to create an immutable Agent definition revision. New work
resolves that published revision and pins its provider and tool relations.
Existing work continues against the revision it already owns.

## Change a published Agent

Edit the draft, review its explicit relations, and publish again. Do not mutate
old revisions. Revoke a revision only when new work must no longer resolve it;
retain historical references required by conversations and runs.

## Background-Agent constraints

Background Agents execute durable objectives rather than joining live
conversation channels. They cannot join swarms, attach another background
Agent, target themselves, or hand off a live call.
