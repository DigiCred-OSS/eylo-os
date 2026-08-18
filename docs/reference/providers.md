# Provider and socket catalog

Provider configuration is code-catalogued, organization-owned, encrypted,
revisioned, verified, and explicitly bound. The authenticated onboarding
catalog at `/api/provider-onboarding/catalog` is the exact form contract used by
the console.

## Capability vendors

| Capability | Current vendor identifiers | Socket boundary |
| --- | --- | --- |
| LLM | Anthropic, AWS Bedrock, Cerebras, Google Gemini, Groq, OpenAI, OpenAI Responses, Sarvam | `eylo/sockets/llm/` |
| STT | Amazon Transcribe, Deepgram, Deepgram Flux, Sarvam, AssemblyAI, Cartesia, Google Cloud, Gladia, Rev AI, Speechmatics | `eylo/sockets/stt/` and shared voice contracts |
| TTS | Amazon Polly, ElevenLabs, Cartesia, Sarvam, OpenAI, Deepgram, Groq, Rime, Smallest AI, Hume, Murf | `eylo/sockets/tts/` and shared voice contracts |
| Realtime | AWS Amazon Nova 2 Sonic, Google Gemini Live, OpenAI Realtime | `eylo/sockets/realtime/` and `eylo/sockets/voice/vendors/` |
| WebRTC | Metered, Turnix | `eylo/sockets/stun_turn/` |
| Telephony | Twilio, Plivo, Vonage, Exotel | `eylo/sockets/telephony/` |
| Email | SMTP, SendGrid | `eylo/sockets/email/` |
| Storage | Amazon S3, Local filesystem | `eylo/sockets/storage/` |
| Embedding | AWS Bedrock, OpenAI-compatible, Voyage AI | `eylo/sockets/embedding/` |
| Reranking | AWS Bedrock, Cohere, Voyage AI | `eylo/sockets/reranking/` |
| Memory | PostgreSQL + pgvector | `eylo/sockets/memory/` |
| Sandbox | Docker | `eylo/sockets/sandbox/` |

Catalog membership means the implementation carries a configuration and
adapter path. It does not mean every vendor has been live-tested in the current
deployment. Verification state is per organization configuration.

## Readiness

A provider config is ready when all of these are true:

- credentials are available;
- the current revision has verified successfully;
- the config is enabled;
- it is not deleted;
- the selected revision is the current revision.

An update creates a new revision and clears verification. Runtime resolution
pins organization, capability, config ID, revision, and provider.

## Configuration ownership

| Concern | Authority |
| --- | --- |
| vendor identifiers, model/voice/region options | capability catalog |
| encrypted secret material and revision history | `provider_configs` module |
| provider-specific API/stream behavior | socket adapter |
| organization/config lookup and real verification | capability module plus pipeline |
| operator fields | provider-onboarding catalog |
| Agent access | explicit Agent-provider or Agent-tool relation |

## Provider-enabled tools

`GET /api/{organization_id}/tools/provider-catalog?capability=<capability>`
shows the tools a capability can unlock before it is configured. Runtime
availability combines:

1. organization readiness;
2. the Agent's explicit capability/tool mapping;
3. current runtime facts such as an active call or durable Agent run.

Current capability-backed system tools include:

- memory: `memory_remember`, `memory_recall`, `memory_refresh`, `memory_forget`;
- sandbox: `sandbox_exec`, `sandbox_read`, `sandbox_write`;
- telephony: `dial_keypad`, `place_call`, `schedule_call`, `transfer_call`;
- voice session: `end_call` when a voice session is active.

Knowledge tools are controlled by knowledgebase grants and conversation scope,
not by choosing a knowledge vendor as an Agent capability.

## Supporting socket packages

Not every socket is an operator-configurable provider. These packages still
belong to the adapter layer and remain domain-independent:

| Package | Responsibility |
| --- | --- |
| `common` | shared provider schema helpers |
| `http` | bounded async HTTP transport primitives |
| `knowledgebase` | PostgreSQL FTS/pgvector search ports, schemas, and chunking contracts |
| `mcp` | MCP client transport |
| `recording` | recording socket namespace; upload orchestration belongs to the voice/storage pipelines |
| `voice` | shared audio frames, buffering, resampling, and streaming voice adapter contracts |

The remaining socket packages map directly to capability rows in the vendor
table above: `email`, `embedding`, `llm`, `memory`, `realtime`, `reranking`,
`sandbox`, `storage`, `stt`, `stun_turn`, `telephony`, and `tts`.

## Vendor addition contract

Use [Add a capability provider vendor](../how-to/add-provider-vendor.md). A
complete addition updates catalog, module config contract, socket adapter,
factory, pipeline verification/resolution, onboarding form projection, tool
requirements when applicable, and current documentation.
