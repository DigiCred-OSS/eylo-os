"""Utility for building prompts for LLM-based title generation."""

from typing import Dict, List, Tuple


def build_title_generation_prompt(
    conversation_string: str,
) -> Tuple[str, List[Dict[str, str]]]:
    """Builds the system prompt and user messages for conversation title generation.

    Args:
        conversation_string: The string content of the conversation.

    Returns:
        A tuple containing:
            - system_prompt (str): The system prompt for the LLM.
            - llm_messages (List[Dict[str, str]]): The list of messages for the LLM.

    """
    system_prompt = """
        You are an AI assistant tasked with generating conversation titles.

        Extract the main topic or purpose of the user-assistant conversation.
        Use noun phrases focusing on the core subject matter.
        Avoid actions, emotions, narrative descriptions, or conversational style.

        Output only the summary text directly with no labels or prefixes.

        Requirements:
        - Maximum 10 words
        - Focus on the core subject matter, not the conversational style
        - Use noun phrases rather than full sentences
        - Avoid actions, emotions, or narrative descriptions
        - Do not include formatting, punctuation beyond necessary commas, or prefixes
        - If no clear topic exists, return an empty string
        - Important: generate title in PLAIN TEXT and not markdown, or html or anyother format

        Good examples:
        - Booking a meeting room for a team event
        - Weather forecast for New York City
        - Booking a meeting room about vendor visit
        - Python debugging assistance
        - Current time inquiry
        - Time inquiry

        Bad examples:
        - The current time in Russia is 11:52 PM.
        - Title: Room booking request
        - "Room booking request"
        - User asks about room booking
        - "*loudly* THE TIME IS NOW!"
        - "User asks about the weather today"
        - "Help me with this problem please"
    """

    llm_messages = [{"role": "user", "content": conversation_string}]

    return system_prompt, llm_messages
