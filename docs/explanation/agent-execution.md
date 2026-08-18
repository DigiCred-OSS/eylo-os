# Agent execution

An Agent is a revisioned definition. An Agent run is one durable attempt to
achieve a goal under explicit provider, tool, budget, and principal authority.

## Conversational run

1. A contact sends a message through the widget/WebSocket path.
2. The conversation module persists the canonical message and request state.
3. The Agent-run module creates a queued run with the conversation/message
   origin and pinned Agent revision.
4. Post-commit work binds the run to Absurd.
5. The worker reloads the run, Agent revision, conversation context, provider
   mappings, tools, knowledge grants, memory config, and execution budget.
6. The provider-neutral framework asks the pipeline-supplied model adapter for
   the next turn.
7. Tool calls return through platform, MCP, or curated execution boundaries.
8. The pipeline persists transcript items, usage, request-state transitions,
   and the canonical assistant message.
9. Ephemeral events project live changes to connected widget sessions.
10. The run reaches a terminal outcome or yields on durable input/approval.

## Tool availability

Tool assignment and tool availability are different facts.

- Assignment: the published Agent revision contains the tool relation.
- Availability: current org provider readiness, Agent capability mapping, and
  runtime facts satisfy the tool's requirements.

For example, `place_call` needs ready telephony, an Agent telephony mapping,
and durable execution. `dial_keypad` needs an active call. `end_call` needs an
active voice session and works for widget/realtime voice as well as telephony.

## Durable waits

When the Agent needs information or approval, the run persists an input request
and enters a waiting state. Absurd releases execution capacity. A later user
response commits first, then wakes the named wait. The run can wait
indefinitely; a missing answer is not itself a failure.

## Budgets

Per-organization limits cover concurrency, tokens, active time, and cost.
Budget authority is checked before an external side effect or persisted output.
Exhaustion rejects the operation; Eylo does not truncate or publish partial
results as success.

## Background Agents and swarms

Background Agents enter the same durable run model from an objective or
attachment rather than a live contact turn. Swarm handoff changes which Agent
reasons next, but the conversation, user session, primary voice configuration,
and transport remain stable.
