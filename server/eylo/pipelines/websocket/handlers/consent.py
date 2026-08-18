"""Apply recording-consent events to the active voice session."""

from eylo.pipelines.voice.consent import handle_recording_consent_event


async def handle_recording_consent(event, ctx):
    return await handle_recording_consent_event(event, ctx)
