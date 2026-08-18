# Run your first Agent

This tutorial takes a new local installation from an empty organization to one
completed text conversation. It intentionally uses only a language-model
provider; voice, knowledge, memory, and integrations are separate follow-on
paths.

## What you will build

You will configure one organization-owned LLM connection, create and publish a
conversational Agent, talk to it through the widget, then inspect its durable
run and conversation from the operator console.

## Before you start

You need:

- Docker with Compose;
- Node.js 24 or newer and pnpm 11;
- one supported LLM provider credential;
- the repository-local `.env.docker` described in the root README.

Eylo has no default provider or model. The Agent cannot run until its selected
LLM configuration is saved, verified, enabled, and bound to a published Agent
revision.

## 1. Start the runtime

From the repository root:

```bash
docker compose \
  -f infra/docker/eylo/docker-compose.yml \
  -f infra/docker/eylo/docker-compose.dev.yml \
  up -d --build
```

In a second terminal:

```bash
cd web
pnpm install --frozen-lockfile
pnpm dev
```

In a third terminal:

```bash
cd widget
pnpm install --frozen-lockfile
pnpm build
cd preact-ui
pnpm dev
```

Wait for `http://127.0.0.1:8000/health` to return `200`. Open the console at
`http://127.0.0.1:5173` and register the first member. Registration creates the
organization.

## 2. Configure an LLM provider

1. Open **Sockets → LLM**.
2. Choose a provider and model from the catalog.
3. Enter the credential fields requested for that provider.
4. Save the configuration.
5. Run **Verify provider**.
6. Enable the configuration if it is not already enabled.

The resulting configuration is ready only when it is both verified and
enabled. Secrets are encrypted at rest and are not returned to the browser.

## 3. Create and publish the Agent

1. Open **Platform → Agents**.
2. Choose **New Agent**.
3. Select the conversational kind.
4. Give the Agent a clear name, primary directive, and short instructions.
5. In the provider section, bind the ready LLM configuration.
6. Save the draft.
7. Publish the Agent.

Draft Agents are intentionally unusable. Publication creates an immutable
revision that runtime work can pin.

## 4. Start a conversation

Open the widget at `http://127.0.0.1:5174`. Select the published Agent, start a
new conversation, and send a concrete question such as:

> Reply with one sentence that confirms the Agent can receive and answer text.

The widget should show processing state followed by the Agent response. A
conversation message creates a durable Agent run; the worker performs the
model call and persists the resulting message before it is projected back to
the widget.

## 5. Inspect what happened

In the console:

1. Open **Platform → Conversations** and select the conversation.
2. Confirm the user and assistant messages are terminal, not left in a
   processing state.
3. Open **Operations → Agent runs** and inspect the matching run, steps, token
   usage, and outcome.
4. Open **Operations → Sessions** and inspect the user-session timeline.

The same conversation may continue in another user session, and one session
may touch more than one conversation. The timeline correlates facts; it does
not redefine conversation ownership.

## Next steps

- Add retrieval with [Knowledge and memory](../how-to/knowledge-and-memory.md).
- Add voice with [Configure a voice Agent](../how-to/voice.md).
- Add curated tools with [Install an integration](../how-to/integrations.md).
- Understand the flow in [Agent execution](../explanation/agent-execution.md).
