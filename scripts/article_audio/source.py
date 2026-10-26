"""Source selection and lightweight Markdown normalization."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from .config import ConfigError, SectionSelector, SourceConfig


@dataclass(frozen=True)
class ExtractedSource:
    text: str
    source_name: str
    selector: str
    source_line_start: int
    source_line_end: int


_HEADING = re.compile(r"^(?P<marks>#{1,6})\s+(?P<title>.+?)\s*$")
_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_PREFIX = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+|>\s*)")


def _select_lines(lines: list[str], selector: SectionSelector) -> tuple[list[str], int, int]:
    if selector.type == "all":
        return lines, 1, len(lines)
    if selector.type == "line_range":
        assert selector.start_line is not None and selector.end_line is not None
        if selector.start_line < 1 or selector.end_line < selector.start_line or selector.end_line > len(lines):
            raise ConfigError(validation_errors=["source.section line range is outside the source"])
        return lines[selector.start_line - 1 : selector.end_line], selector.start_line, selector.end_line
    if selector.type == "markers":
        assert selector.value is not None and selector.end is not None
        start = next((index for index, line in enumerate(lines) if selector.value in line), None)
        if start is None:
            raise ConfigError(validation_errors=["source.section start marker was not found"])
        end = next((index for index in range(start + 1, len(lines)) if selector.end in lines[index]), None)
        if end is None:
            raise ConfigError(validation_errors=["source.section end marker was not found"])
        return lines[start + 1 : end], start + 2, end

    assert selector.type == "heading" and selector.value is not None
    found: tuple[int, int] | None = None
    for index, line in enumerate(lines):
        match = _HEADING.match(line)
        if not match:
            continue
        level = len(match.group("marks"))
        title = match.group("title").strip()
        if title == selector.value and (selector.level is None or selector.level == level):
            found = (index, level)
            break
    if found is None:
        raise ConfigError(validation_errors=["source.section heading was not found"])
    start, level = found
    end = len(lines)
    for index in range(start + 1, len(lines)):
        match = _HEADING.match(lines[index])
        if match and len(match.group("marks")) <= level:
            end = index
            break
    selected_start = start if selector.include_heading else start + 1
    return lines[selected_start:end], selected_start + 1, end


def _normalize_plain(lines: list[str]) -> str:
    paragraphs: list[str] = []
    pending: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped:
            pending.append(stripped)
        elif pending:
            paragraphs.append(" ".join(pending))
            pending = []
    if pending:
        paragraphs.append(" ".join(pending))
    return "\n\n".join(paragraphs).strip()


def _normalize_markdown(lines: list[str], *, include_code: bool) -> str:
    cleaned: list[str] = []
    in_fence = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            if include_code:
                cleaned.append("")
            continue
        if in_fence and not include_code:
            continue
        match = _HEADING.match(line)
        if match:
            line = match.group("title")
        else:
            line = _PREFIX.sub("", line)
        line = _LINK.sub(r"\1", line)
        cleaned.append(line)
    return _normalize_plain(cleaned)


def extract_source(source: SourceConfig, *, stdin_text: str | None = None) -> ExtractedSource:
    """Read, select, and normalize one local or standard-input article."""

    if source.path is None:
        raise ConfigError(missing_parameters=["source.path"])
    if str(source.path) == "-":
        text = sys.stdin.read() if stdin_text is None else stdin_text
        source_name = "stdin"
    else:
        try:
            text = source.path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConfigError(validation_errors=[f"cannot read source: {exc.strerror}"]) from exc
        source_name = source.path.name
    lines = text.splitlines()
    if not lines:
        raise ConfigError(validation_errors=["source is empty"])
    selected, start, end = _select_lines(lines, source.section)
    source_format = source.format.casefold()
    if source_format == "auto":
        source_format = "markdown" if source.path.suffix.casefold() in {".md", ".markdown"} else "text"
    if source_format not in {"markdown", "text"}:
        raise ConfigError(validation_errors=["source.format must be auto, markdown, or text"])
    normalized = (
        _normalize_markdown(selected, include_code=source.include_code)
        if source_format == "markdown"
        else _normalize_plain(selected)
    )
    if not normalized:
        raise ConfigError(validation_errors=["selected source contains no narratable text"])
    return ExtractedSource(
        text=normalized,
        source_name=source_name,
        selector=source.section.type,
        source_line_start=start,
        source_line_end=end,
    )
