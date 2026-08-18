"""Realtime voice module — unified vendor WebSocket (Gemini Live / OpenAI Realtime).

Alternative to the decomposed STT → LLM → TTS pipeline. The vendor owns the entire
agentic loop; this module manages lifecycle, tool dispatch, and persistence.
"""
