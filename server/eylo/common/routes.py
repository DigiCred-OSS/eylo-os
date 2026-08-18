"""FastAPI router composition for private, public, callback, and WebSocket APIs."""

from fastapi import APIRouter, Depends

from eylo.common.config import Environment, settings
from eylo.modules.auth.dependencies.member_auth import (
    require_member_path_organization,
)
from eylo.modules.auth.dependencies.widget_auth import get_current_contact

# Initialize routers
private_router = APIRouter(dependencies=[Depends(require_member_path_organization)])
public_router = APIRouter()
widget_router = APIRouter(dependencies=[Depends(get_current_contact)])


def setup_private_routes():
    """Set up private routes for authenticated access."""
    from eylo.modules.agent_runs.routes import router as _agent_runs
    from eylo.modules.agents.routes import agent_stats_router as _agent_stats
    from eylo.modules.agents.routes import agent_swarm_router as _agent_swarm
    from eylo.modules.agents.routes import (
        background_agent_router as _agent_background,
    )
    from eylo.modules.agents.routes import router as _agents
    from eylo.modules.analytics.routes import router as _analytics
    from eylo.modules.auth.routes.api_keys import router as _api_keys
    from eylo.modules.auth.routes.private import router as _auth
    from eylo.modules.auth.routes.widget_invitations import (
        private_router as _widget_invitations,
    )
    from eylo.modules.contacts.routes import router as _contacts
    from eylo.modules.conversations.routes.private import router as _conversations
    from eylo.modules.conversations.routes.private.aggregate import (
        aggregate_router as _aggregates,
    )
    from eylo.modules.conversations.routes.private.message import (
        message_router as _messages,
    )
    from eylo.modules.conversations.routes.private.participant import (
        participant_router as _participants,
    )
    from eylo.modules.deletions.routes import router as _deletions
    from eylo.modules.email_configs.routes import router as _email_configs
    from eylo.modules.embedding_configs.routes import router as _embedding_configs
    from eylo.modules.integrations_v2.routes import router as _curated_integrations
    from eylo.modules.knowledgebase.routes.ingestion import (
        router as _kb_ingestion,
    )
    from eylo.modules.knowledgebase.routes.knowledgebases import (
        router as _knowledgebases,
    )
    from eylo.modules.llm_configs.routes import router as _llm_configs
    from eylo.modules.mcp_servers.routes import router as _mcp_servers
    from eylo.modules.members.routes import router as _members
    from eylo.modules.memory.routes import router as _memories
    from eylo.modules.memory_configs.routes import router as _memory_configs
    from eylo.modules.provider_configs.routes import router as _provider_configs
    from eylo.modules.provider_onboarding.routes import router as _provider_onboarding
    from eylo.modules.reranking_configs.routes import router as _reranking_configs
    from eylo.modules.sandbox.routes import router as _objectives
    from eylo.modules.sandbox_configs.routes import router as _sandbox_configs
    from eylo.modules.scheduler.routes import router as _schedules
    from eylo.modules.storage_configs.routes import router as _storage_configs
    from eylo.modules.telephony.call_routes import router as _telephony_calls
    from eylo.modules.telephony.provider_config_routes import (
        router as _telephony_providers,
    )
    from eylo.modules.telephony.routes import router as _telephony
    from eylo.modules.templates.routes import router as _templates
    from eylo.modules.tools.routes import router as _tools
    from eylo.modules.user_sessions.routes import router as _user_sessions
    from eylo.modules.voice.recording.routes import router as _voice_recordings
    from eylo.modules.voice.routes.voice_configs import router as _voice
    from eylo.modules.voice_configs.routes import realtime_router as _realtime_configs
    from eylo.modules.voice_configs.routes import stt_router as _stt_configs
    from eylo.modules.voice_configs.routes import tts_router as _tts_configs
    from eylo.modules.voice_transcripts.routes.private import (
        conversation_router as _voice_transcript_conversations,
    )
    from eylo.modules.voice_transcripts.routes.private import (
        router as _voice_transcripts,
    )
    from eylo.modules.webrtc_configs.routes import router as _webrtc_configs
    from eylo.pipelines.durable_events.routes import router as _event_health
    from eylo.pipelines.telephony.number_routes import (
        router as _number_management,
    )
    from eylo.products.campaigns.routes import router as _campaigns

    private_router.include_router(_agents)
    private_router.include_router(_agent_runs)
    private_router.include_router(_agent_background)
    private_router.include_router(_mcp_servers)
    private_router.include_router(_embedding_configs)
    private_router.include_router(_reranking_configs)
    private_router.include_router(_sandbox_configs)
    private_router.include_router(_objectives)
    private_router.include_router(_memory_configs)
    private_router.include_router(_memories)
    private_router.include_router(_schedules)
    private_router.include_router(_knowledgebases)
    private_router.include_router(_kb_ingestion)
    private_router.include_router(_agent_stats)
    private_router.include_router(_telephony)
    private_router.include_router(_telephony_calls)
    private_router.include_router(_templates)
    private_router.include_router(_telephony_providers)
    private_router.include_router(_number_management)
    private_router.include_router(_event_health)
    private_router.include_router(_members)
    private_router.include_router(_user_sessions)
    private_router.include_router(_curated_integrations)
    private_router.include_router(_llm_configs)
    private_router.include_router(_provider_configs)
    private_router.include_router(_provider_onboarding)
    private_router.include_router(_tools)
    private_router.include_router(
        _aggregates
    )  # Must be before _conversations to match /aggregate before /{conversation_id}
    private_router.include_router(_conversations)
    private_router.include_router(_messages)
    private_router.include_router(_participants)
    private_router.include_router(_auth)
    private_router.include_router(_widget_invitations)
    private_router.include_router(_api_keys)
    private_router.include_router(_contacts)
    private_router.include_router(_deletions)
    private_router.include_router(_analytics)
    private_router.include_router(_voice)
    private_router.include_router(_stt_configs)
    private_router.include_router(_tts_configs)
    private_router.include_router(_realtime_configs)
    private_router.include_router(_webrtc_configs)
    private_router.include_router(_email_configs)
    private_router.include_router(_storage_configs)
    private_router.include_router(_voice_recordings)
    private_router.include_router(_voice_transcripts)
    private_router.include_router(_voice_transcript_conversations)
    private_router.include_router(_agent_swarm)
    private_router.include_router(_campaigns)

def setup_public_routes():
    """Set up public routes that don't require authentication."""
    from eylo.modules.auth.routes.public import router as _auth
    from eylo.modules.auth.routes.public_session import (
        router as _public_session,
    )
    from eylo.modules.auth.routes.widget_invitations import (
        public_router as _widget_invitation_exchange,
    )
    from eylo.modules.conversations.routes.public import router as _conversations
    from eylo.modules.integrations_v2.routes import (
        public_router as _curated_oauth,
    )
    from eylo.modules.telephony.voice_routes import router as _voice_routes
    from eylo.pipelines.telephony.media_stream import router as _generic_telephony_ws
    from eylo.pipelines.telephony.webhook_routes import router as _webhooks
    from eylo.pipelines.websocket.routes import router as _websocket

    public_router.include_router(_auth)
    public_router.include_router(_conversations)
    public_router.include_router(_public_session)
    public_router.include_router(_widget_invitation_exchange)
    if settings.ENV is Environment.LOCAL:
        from eylo.modules.auth.routes.widget_development import (
            router as _widget_development,
        )

        public_router.include_router(_widget_development)
    public_router.include_router(_curated_oauth)
    public_router.include_router(_websocket)
    public_router.include_router(_webhooks)
    public_router.include_router(_generic_telephony_ws)

    # voice_routes mounted on private_router — outbound calls require auth
    private_router.include_router(_voice_routes)

def setup_widget_routes():
    """Set up widget routes with session-based authentication.

    Widget routes are for end users (contacts) interacting through the widget.
    These routes use X-Session-ID header authentication instead of JWT tokens.

    Widget routes provide:
    - Curated capabilities for published Agents
    - Contact-owned curated connection initiation

    Note: Agents and messages are primarily delivered via WebSocket.

    All widget routes are prefixed with /widget/{organization_id}/
    """
    from eylo.modules.integrations_v2.routes import (
        widget_router as _curated_widget,
    )
    from eylo.modules.knowledgebase.routes.widget import router as _knowledge_widget

    widget_router.include_router(_curated_widget)
    widget_router.include_router(_knowledge_widget)


# Initialize routes
setup_private_routes()
setup_public_routes()
setup_widget_routes()
