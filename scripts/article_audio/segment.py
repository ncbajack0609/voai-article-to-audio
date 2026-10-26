"""Deterministic semantic-first text segmentation."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .config import SegmentationConfig


@dataclass(frozen=True)
class Segment:
    index: int
    text: str
    spoken_text: str
    character_count: int
    source_start: int
    source_end: int
    boundary: str
    exception_reason: str | None


def readable_count(text: str) -> int:
    return sum(not character.isspace() for character in text)


def _boundary_positions(text: str, start: int) -> dict[str, list[int]]:
    tail = text[start:]
    patterns = (
        ("paragraph", r"\n\n+"),
        ("sentence", r"(?<=[。！？.!?])\s*"),
        ("clause", r"(?<=[；;：:])\s*"),
        ("phrase", r"(?<=[，,、])\s*"),
        ("word", r"\s+"),
    )
    positions: dict[str, list[int]] = {}
    for name, pattern in patterns:
        found = {start + match.end() for match in re.finditer(pattern, tail)}
        positions[name] = sorted(position for position in found if position > start)
    return positions


def _hard_position(text: str, start: int, maximum: int) -> int:
    count = 0
    for position in range(start, len(text)):
        if not text[position].isspace():
            count += 1
        if count >= maximum:
            return position + 1
    return len(text)


def _choose_boundary(
    text: str,
    start: int,
    config: SegmentationConfig,
) -> tuple[int, str, str | None]:
    if readable_count(text[start:]) <= config.max_characters:
        return len(text), "source_end", (
            "tail_below_minimum"
            if readable_count(text[start:]) < config.min_characters
            else None
        )
    positions = _boundary_positions(text, start)
    ranked: list[tuple[int, int, int, str]] = []
    priorities = {"paragraph": 0, "sentence": 1, "clause": 2, "phrase": 3, "word": 4}
    for name, candidates in positions.items():
        for position in candidates:
            count = readable_count(text[start:position])
            if config.min_characters <= count <= config.max_characters:
                ranked.append((priorities[name], abs(count - config.target_characters), position, name))
    if ranked:
        _, _, position, name = min(ranked)
        return position, name, None

    soft_limit = config.max_characters * 2
    semantic_after: list[tuple[int, int, str]] = []
    for name in ("paragraph", "sentence", "clause"):
        for position in positions[name]:
            count = readable_count(text[start:position])
            if config.max_characters < count <= soft_limit:
                semantic_after.append((priorities[name], count, name))
                break
    if semantic_after:
        priority, count, name = min(semantic_after)
        del priority
        for position in positions[name]:
            if readable_count(text[start:position]) == count:
                return position, name, "semantic_unit_exceeds_maximum"

    position = _hard_position(text, start, config.max_characters)
    return position, "hard", "no_semantic_boundary_in_range"


def segment_text(text: str, config: SegmentationConfig) -> tuple[Segment, ...]:
    """Partition normalized text exactly while preferring semantic boundaries."""

    if not text:
        return ()
    segments: list[Segment] = []
    start = 0
    while start < len(text):
        end, boundary, exception = _choose_boundary(text, start, config)
        if end <= start:
            raise RuntimeError("segmenter did not make progress")
        raw_text = text[start:end]
        spoken = raw_text.strip()
        if spoken:
            segments.append(
                Segment(
                    index=len(segments) + 1,
                    text=raw_text,
                    spoken_text=spoken,
                    character_count=readable_count(spoken),
                    source_start=start,
                    source_end=end,
                    boundary=boundary,
                    exception_reason=exception,
                )
            )
        start = end
    if "".join(segment.text for segment in segments) != text:
        raise RuntimeError("segmentation failed source conservation")
    return tuple(segments)
