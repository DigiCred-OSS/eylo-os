# Architecture diagrams

## System context

```mermaid
flowchart LR
    contact[Contact]
    member[Organization Member]
    widget[Widget SDK and Preact UI]
    console[Operator Console]
    cli[CLI]
    api[Eylo API]
    worker[Durable Worker]
    postgres[(PostgreSQL and pgvector)]
    redis[(Redis)]
    vendors[Provider and Integration APIs]

    contact --> widget
    member --> console
    member --> cli
    widget --> api
    console --> api
    cli --> api
    api --> postgres
    api --> redis
    worker --> postgres
    worker --> redis
    api --> vendors
    worker --> vendors
```

The API owns authenticated entrypoints and live transport managers. The worker
owns durable attempts. Both resolve organization authority from PostgreSQL
before contacting a provider.

## Backend dependency direction

```mermaid
flowchart LR
    framework["Framework: provider-neutral Agent loop"]
    modules["Modules: domain and persistence"]
    sockets["Sockets: vendor protocols"]
    pipelines["Pipelines: cross-layer composition"]
    products["Products: campaign composition"]
    api_worker["API and Worker entrypoints"]

    pipelines --> framework
    pipelines --> modules
    pipelines --> sockets
    products --> modules
    products --> pipelines
    api_worker --> modules
    api_worker --> pipelines
    api_worker --> products
```

Arrows point from a dependent layer to the layer it uses. The enforced negative
rules are the important part: Framework imports no platform; Modules and
Sockets do not import one another.

## Local deployment

```mermaid
flowchart TB
    subgraph browser[Browser]
        console[React Console]
        widget[Preact Widget]
    end

    subgraph application[Application]
        api[FastAPI and Gunicorn]
        worker[Absurd Durable Worker]
    end

    subgraph data[Data Services]
        postgres[(PostgreSQL 17 and pgvector)]
        redis[(Redis 7)]
    end

    provider[External Providers]

    console --> api
    widget --> api
    api --> postgres
    api --> redis
    worker --> postgres
    worker --> redis
    api --> provider
    worker --> provider
```

## Data ownership

```mermaid
flowchart TB
    organization[Organization]
    member[Member]
    agent[Agent and Revisions]
    contact[Contact]
    conversation[Conversation]
    user_session[User Session]
    message[Messages and Participants]
    campaign[Campaign and Attempts]
    voice[Voice Session and Recording]
    knowledge[Knowledgebase and Chunks]
    memory[Typed Memories]
    provider[Provider Configs]

    organization --> member
    organization --> agent
    organization --> contact
    organization --> conversation
    organization --> user_session
    organization --> campaign
    organization --> knowledge
    organization --> memory
    organization --> provider
    contact --> conversation
    user_session --> conversation
    conversation --> message
    campaign --> contact
    campaign --> agent
    voice --> conversation
    knowledge --> agent
    memory --> agent
    memory --> contact
    memory --> conversation
```

Reference arrows mean association when the target retains independent
ownership. Campaign-to-contact and campaign-to-Agent therefore do not imply
delete cascade.
