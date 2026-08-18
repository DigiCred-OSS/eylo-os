"""Safe Markdown rendering shared by message contracts."""

import logging
import re

import nh3 as bleach
from markdown_it import MarkdownIt

logger = logging.getLogger(__name__)


def normalize_llm_markdown(text: str) -> str:
    # simple fixes often needed for LLM outputs
    # 1) normalize fancy quotes (optional)
    text = text.replace("\r\n", "\n")
    # 2) ensure triple-backtick fences are triple (sometimes LLM uses varying chars)
    text = re.sub(r"(^|\\n)(`{1,2})([^`\\n])", r"\1```\3", text)
    # 3) ensure closing fence exists if code fence is open
    if text.count("```") % 2 == 1:
        text += "\n```"
    return text


def md_to_safe_html(text: str) -> str:
    text = normalize_llm_markdown(text)

    # LLMs often use GitHub-style pipe tables in assistant messages. CommonMark
    # treats those as plain paragraphs unless the table rule is enabled.
    md = MarkdownIt("commonmark").enable("table")
    html = md.render(text)

    # sanitize output: conservative allowed tags/attrs
    allowed_tags = [
        "p",
        "pre",
        "code",
        "blockquote",
        "ul",
        "ol",
        "li",
        "strong",
        "em",
        "a",
        "img",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "br",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
    ]
    allowed_attrs = {
        "*": set(["class", "id"]),
        "a": set(["href", "title"]),
        "img": set(["src", "alt", "title"]),
        "th": set(["colspan", "rowspan"]),
    }
    safe_html = bleach.clean(
        html,
        tags=set(allowed_tags),
        attributes=allowed_attrs,
    )
    return safe_html


def md_to_html(md_text: str) -> str:
    """Convert markdown text to HTML."""
    return md_to_safe_html(md_text)
