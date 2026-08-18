# Data-flow diagrams

## Text conversation and Agent run

```mermaid
sequenceDiagram
    participant C as Contact
    participant W as Widget
    participant API as API and WebSocket
    participant DB as PostgreSQL
    participant Q as Absurd
    participant WK as Durable Worker
    participant P as LLM or Tool Provider

    C->>W: Send message
    W->>API: Message command
    API->>DB: Persist message and queued Agent run
    DB-->>API: Commit
    API->>Q: Bind persisted run
    API-->>W: Broadcast canonical message and state
    WK->>Q: Claim run
    WK->>DB: Resolve Agent revision, context, tools, budget
    WK->>P: Model inference or tool call
    P-->>WK: Normalized result
    WK->>DB: Persist usage, transcript, status, assistant message
    DB-->>WK: Commit
    WK-->>API: Publish canonical message and lifecycle deltas
    API-->>W: Deliver conversation-scoped WebSocket events
    W-->>C: Render response
```

## Knowledge ingestion and query

```mermaid
flowchart LR
    source["Uploaded or storage-owned source"]
    api[Knowledge API]
    job[(Ingestion Job)]
    worker[Durable Worker]
    storage[Storage Adapter]
    extract[Deterministic Extraction]
    chunk[Chunking]
    embed[Embedding Adapter]
    chunks[(Knowledge Chunks and Vectors)]
    query[Agent kb_query]
    grants[Knowledgebase Grants]
    rerank[Optional Reranker]
    citation[Cited Passages]

    source --> api --> job --> worker
    worker --> storage --> extract --> chunk --> embed --> chunks
    query --> grants --> chunks
    chunks --> rerank --> citation
    chunks --> citation
```

The ingestion job commits before durable execution. Retry replaces chunks for
the same source identity inside the same knowledgebase.

## Memory recall and consolidation

```mermaid
sequenceDiagram
    participant R as Agent Run
    participant M as Memory Application
    participant V as Memory Vector Store
    participant L as LLM
    participant J as Durable Memory Jobs
    participant DB as PostgreSQL

    R->>M: Recall typed owner context
    M->>V: Search current embedding space
    V-->>M: Candidate facts
    M-->>R: Bounded recalled facts
    R->>DB: Persist completed conversation work
    DB-->>J: Formation job committed and bound
    J->>L: Propose memory operations
    L-->>J: Add, refresh, or expire proposals
    J->>DB: Apply facts and provenance
    J->>L: Reconcile duplicate or conflicting candidates
    L-->>J: Typed reconciliation decisions
    J->>DB: Persist relationships and effects
```

## Browser voice

```mermaid
flowchart LR
    microphone[Microphone]
    webrtc[WebRTC Transport]
    voice_session[Voice Session]
    realtime[Realtime Provider]
    stt[STT Provider]
    llm[LLM and Tools]
    tts[TTS Provider]
    playback[Assistant Playback]
    transcript[(Messages and Voice Segments)]
    recording[(Staged Recording)]
    post_call[Durable Post-call Work]
    storage[Storage Provider]

    microphone --> webrtc --> voice_session
    voice_session --> realtime --> playback
    voice_session --> stt --> llm --> tts --> playback
    voice_session --> transcript
    playback --> transcript
    voice_session --> recording --> post_call --> storage
```

Only one provider path is active per voice config: realtime, or decomposed
STT/LLM/TTS. Interruption and lifecycle policy wrap either path.

## Curated integration tool call

```mermaid
sequenceDiagram
    participant A as Agent Run
    participant G as Published Tool Grant
    participant R as Curated Registry
    participant C as Connection Resolver
    participant H as Origin-bound HTTP Client
    participant D as Durable Mutation Owner
    participant V as Vendor API

    A->>G: Resolve exact vendor.tool grant
    G->>R: Resolve registered callable and policy
    R->>C: Select organization or contact connection
    C->>H: Inject scoped credential at pinned origin
    alt Read tool
        H->>V: Bounded read request
        V-->>H: Bounded response
    else Mutation tool
        H->>D: Create exact mutation attempt
        D->>V: Idempotent vendor request
        V-->>D: Vendor response
        D-->>H: Durable receipt and result
    end
    H-->>A: Normalized tool result
```

## Campaign attempt

```mermaid
flowchart LR
    draft[Campaign Draft]
    revision[Published Campaign Revision]
    audience[Selected Contacts]
    preparation[Preparation Warnings and Blockers]
    attempts[(Per-contact Attempts)]
    worker[Durable Worker]
    channel[Voice, Email, or Widget Channel]
    outcome[Attempt Outcome]
    analytics[Campaign Analytics]

    draft --> revision
    audience --> preparation
    revision --> preparation --> attempts --> worker --> channel --> outcome --> analytics
```

Preparation warnings may allow V1 outreach; blockers prevent start. Contacts
remain independently owned organization resources.
