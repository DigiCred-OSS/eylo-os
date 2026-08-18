"""Errors for the `agents` domain."""


class AgentError(Exception):
    """AgentError behavior for the "agents" domain."""

    pass


class AgentNotFoundError(AgentError):
    """AgentNotFoundError behavior for the "agents" domain."""

    def __init__(self, message: str = "Agent not found"):
        self.message = message
        super().__init__(self.message)


class AgentLLMConfigNotFoundError(AgentError):
    """Raised when an agent's LLM config cannot resolve within its organization."""

    def __init__(self, message: str = "LLM provider config not found"):
        self.message = message
        super().__init__(self.message)


class AgentEmbeddingConfigError(AgentError):
    """Raised when conversation file uploads cannot pin an embedding config."""

    def __init__(self, message: str = "Embedding provider config is not ready"):
        self.message = message
        super().__init__(self.message)


class AgentRerankingConfigError(AgentError):
    """Raised when a published agent cannot pin its requested reranker."""

    def __init__(self, message: str = "Reranking provider config is not ready"):
        self.message = message
        super().__init__(self.message)


class AgentMemoryConfigError(AgentError):
    """Raised when a published agent cannot pin its requested memory config."""

    def __init__(self, message: str = "Memory provider config is not ready"):
        self.message = message
        super().__init__(self.message)


class AgentEmailConfigError(AgentError):
    """Raised when a published agent cannot pin its requested email config."""

    def __init__(self, message: str = "Email provider config is not ready"):
        self.message = message
        super().__init__(self.message)


class AgentWebRTCConfigError(AgentError):
    """Raised when a published agent cannot pin its requested WebRTC config."""

    def __init__(self, message: str = "WebRTC provider config is not ready"):
        self.message = message
        super().__init__(self.message)


class AgentVoiceConfigError(AgentError):
    """Raised when a published agent cannot pin its voice provider configs."""

    def __init__(self, message: str = "Voice provider config is not ready"):
        self.message = message
        super().__init__(self.message)


class DuplicateAgentError(AgentError):
    """DuplicateAgentError behavior for the "agents" domain."""

    def __init__(self, message: str = "Agent already exists"):
        self.message = message
        super().__init__(self.message)


class DuplicateAssignmentError(AgentError):
    """DuplicateAssignmentError behavior for the "agents" domain."""

    def __init__(self, message: str = "Tool is already assigned to this agent"):
        self.message = message
        super().__init__(self.message)


class ToolAssignmentError(AgentError):
    """ToolAssignmentError behavior for the "agents" domain."""

    def __init__(self, message: str = "Error assigning tool to agent"):
        self.message = message
        super().__init__(self.message)


class MaxToolsExceededError(AgentError):
    """MaxToolsExceededError behavior for the "agents" domain."""

    def __init__(
        self, message: str = "Maximum number of tools exceeded for this agent"
    ):
        self.message = message
        super().__init__(self.message)


class IncompatibleToolError(AgentError):
    """IncompatibleToolError behavior for the "agents" domain."""

    def __init__(self, message: str = "Tool is not compatible with this agent"):
        self.message = message
        super().__init__(self.message)


class ToolNotAssignedError(AgentError):
    """ToolNotAssignedError behavior for the "agents" domain."""

    def __init__(self, message: str = "Tool is not assigned to this agent"):
        self.message = message
        super().__init__(self.message)


class ToolNotFoundError(AgentError):
    """ToolNotFoundError behavior for the "agents" domain."""

    def __init__(self, message: str = "Tool not found"):
        self.message = message
        super().__init__(self.message)
