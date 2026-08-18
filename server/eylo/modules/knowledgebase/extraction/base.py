"""Provider-neutral contracts for the `knowledgebase` domain."""

from __future__ import annotations

import io
import zipfile

# Bounds. Each one exists because a specific input shape would otherwise cost
# far more than the document is worth.

# A zip bomb is a small archive that expands enormously. Both .docx and .xlsx
# are zip archives, so both are exposed to it, and the expansion happens inside
# a library rather than in code we control.
MAX_UNCOMPRESSED_BYTES = 200_000_000
MAX_COMPRESSION_RATIO = 200

# A PDF can declare tens of thousands of pages. Reading them is linear, but a
# knowledgebase chunk from page 4,000 of a scanned archive is not what anyone
# meant by "import our policies".
MAX_PDF_PAGES = 2_000

# Spreadsheets address a very large grid, and openpyxl will happily walk to
# whatever the file claims its dimensions are — including a mostly-empty sheet
# that says it is a million rows tall.
MAX_SHEET_ROWS = 50_000
MAX_TOTAL_CELLS = 1_000_000


class DocumentExtractionError(Exception):
    """This file cannot be turned into text, and trying again will not help.

    Terminal by design. Every subclass of this failure — wrong format, corrupt
    archive, encrypted PDF, undecodable bytes — produces the identical result on
    every attempt, so the worker sends it straight to FAILED with the reason
    rather than spending its attempts rediscovering it.
    """


def guard_zip(raw: bytes, *, kind: str) -> None:
    """Refuse an archive that expands out of proportion to its size.

    Checked against the archive's own declared sizes before anything is read,
    because by the time a parser has expanded a bomb the damage is done. The
    declared sizes can lie, but a lie that under-reports is a file whose
    entries then fail to match their headers — which the zip library rejects
    on its own.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            uncompressed = sum(entry.file_size for entry in archive.infolist())
    except zipfile.BadZipFile as error:
        raise DocumentExtractionError(
            f"This {kind} file is not a readable archive: {error}"
        ) from error

    if uncompressed > MAX_UNCOMPRESSED_BYTES:
        raise DocumentExtractionError(
            f"This {kind} file expands to {uncompressed} bytes, over the "
            f"{MAX_UNCOMPRESSED_BYTES} byte limit."
        )
    compressed = max(len(raw), 1)
    if uncompressed // compressed > MAX_COMPRESSION_RATIO:
        raise DocumentExtractionError(
            f"This {kind} file expands {uncompressed // compressed}x, over the "
            f"{MAX_COMPRESSION_RATIO}x limit; it looks like a zip bomb."
        )


def decode_text(raw: bytes, *, key: str) -> str:
    """Bytes to text, strictly.

    UTF-8 with no fallback and no `errors="replace"`. A replacement character
    is a silent corruption that survives into the index and then into an
    answer, where nothing distinguishes it from what the document said. A BOM
    is stripped because it is an encoding artefact, not content.
    """
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise DocumentExtractionError(
            f"{key} is not UTF-8 text ({error.reason} at byte {error.start}). "
            "Convert it, or store it in a format this platform parses."
        ) from error
    return text
