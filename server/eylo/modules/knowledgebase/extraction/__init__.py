"""Public exports for the `knowledgebase` domain package."""

from __future__ import annotations

from eylo.modules.knowledgebase.extraction.base import DocumentExtractionError
from eylo.modules.knowledgebase.extraction.extractors import (
    extract_csv,
    extract_docx,
    extract_html,
    extract_legacy_doc,
    extract_pdf,
    extract_plain,
    extract_xls,
    extract_xlsx,
)

__all__ = [
    "SUPPORTED_EXTENSIONS",
    "DocumentExtractionError",
    "extract_text",
    "is_supported",
]

_EXTRACTORS = {
    # Plain text and lightweight markup, passed through as written.
    ".txt": extract_plain,
    ".text": extract_plain,
    ".md": extract_plain,
    ".markdown": extract_plain,
    ".rst": extract_plain,
    ".log": extract_plain,
    ".json": extract_plain,
    ".yaml": extract_plain,
    ".yml": extract_plain,
    # Markup, stripped to what a reader would see.
    ".html": extract_html,
    ".htm": extract_html,
    ".xhtml": extract_html,
    # Delimited tables.
    ".csv": extract_csv,
    ".tsv": extract_csv,
    # Documents.
    ".pdf": extract_pdf,
    ".docx": extract_docx,
    # Listed so it fails with an explanation rather than as an unknown type.
    # An operator whose archive is half `.doc` deserves to be told to convert
    # it, not to watch those files silently not appear.
    ".doc": extract_legacy_doc,
    # Spreadsheets. Two libraries, one output shape.
    ".xlsx": extract_xlsx,
    ".xlsm": extract_xlsx,
    ".xls": extract_xls,
}

# `.doc` is excluded: it dispatches to a refusal, and advertising it as
# supported would be the API telling an operator something the platform then
# contradicts one job later.
SUPPORTED_EXTENSIONS: tuple[str, ...] = tuple(
    sorted(extension for extension in _EXTRACTORS if extension != ".doc")
)


def is_supported(key: str) -> bool:
    """Whether this platform will attempt to read this file.

    True for `.doc` as well, deliberately. Screening it *in* is what lets the
    refusal reach the operator as a job that failed with a reason, rather than
    as a file quietly skipped at listing time for being an unknown type.
    """
    return _extension(key) in _EXTRACTORS


def extract_text(key: str, raw: bytes) -> str:
    """The text this file contributes to a knowledgebase.

    Raises `DocumentExtractionError` for anything that will fail identically
    next time — the wrong format, a corrupt archive, an encrypted PDF, a scan
    with no text layer. The worker treats that as terminal, so an operator sees
    the reason immediately rather than after three rounds of backoff.
    """
    extractor = _EXTRACTORS.get(_extension(key))
    if extractor is None:
        raise DocumentExtractionError(
            f"{key} has an unsupported file type. This platform reads: "
            f"{', '.join(SUPPORTED_EXTENSIONS)}."
        )

    text = extractor(raw, key=key)
    if not text.strip():
        # A parser that succeeded and produced nothing is the quiet failure
        # worth catching: the job would report success and the document would
        # not be in the knowledgebase, with nothing anywhere saying so.
        raise DocumentExtractionError(
            f"{key} parsed successfully but contains no text to index."
        )
    return text


def _extension(key: str) -> str:
    _, separator, extension = key.lower().rpartition(".")
    return f".{extension}" if separator else ""
