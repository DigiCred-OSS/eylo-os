"""Bedrock adapter for the `llm` socket."""

from anthropic import AsyncAnthropicBedrock

from eylo.sockets.llm.vendors.anthropic import AnthropicAdapter


class AWSBedrockAdapter(AnthropicAdapter):
    """AWS Bedrock adapter using Claude models."""

    def __init__(
        self,
        *,
        aws_access_key: str,
        aws_secret_key: str,
        aws_session_token: str | None = None,
        aws_region: str,
    ):
        if not aws_access_key or not aws_secret_key:
            raise ValueError("Stored Bedrock credentials are required")
        self._aws_access_key = aws_access_key
        self._aws_secret_key = aws_secret_key
        self._aws_session_token = aws_session_token
        self._aws_region = aws_region

    def get_client(self) -> AsyncAnthropicBedrock:
        """Get configured AWS Bedrock client for Claude models."""
        return AsyncAnthropicBedrock(
            aws_access_key=self._aws_access_key,
            aws_secret_key=self._aws_secret_key,
            aws_session_token=self._aws_session_token,
            aws_region=self._aws_region,
        )
