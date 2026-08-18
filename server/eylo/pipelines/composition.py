"""Process-level registration for pipeline-owned tools and actions."""

from eylo.pipelines.system_tools.registration import register_pipeline_system_tools


def register_pipeline_extensions() -> None:
    """Register pipeline extensions idempotently before serving or polling."""
    register_pipeline_system_tools()
    import eylo.pipelines.telephony.scheduled_actions  # noqa: F401


__all__ = ["register_pipeline_extensions"]
