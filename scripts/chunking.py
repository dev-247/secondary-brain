from __future__ import annotations

import re
from dataclasses import dataclass

MAX_CHUNK_CHARS = 2000
MIN_CHUNK_CHARS = 100


@dataclass
class Chunk:
    text: str
    heading: str
    index: int


def chunk_markdown(text: str) -> list[Chunk]:
    sections: list[tuple[str, str]] = []
    current_heading = "Document"
    current_lines: list[str] = []

    for line in text.splitlines():
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            if current_lines:
                sections.append((current_heading, "\n".join(current_lines).strip()))
            current_heading = heading_match.group(2).strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_heading, "\n".join(current_lines).strip()))

    if not sections:
        sections = [("Document", text.strip())]

    chunks: list[Chunk] = []
    chunk_index = 0

    for heading, body in sections:
        if not body:
            continue
        if len(body) <= MAX_CHUNK_CHARS:
            chunks.append(Chunk(text=body, heading=heading, index=chunk_index))
            chunk_index += 1
            continue

        paragraphs = re.split(r"\n\s*\n", body)
        buffer = ""
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            candidate = f"{buffer}\n\n{paragraph}".strip() if buffer else paragraph
            if len(candidate) <= MAX_CHUNK_CHARS:
                buffer = candidate
                continue
            if buffer and len(buffer) >= MIN_CHUNK_CHARS:
                chunks.append(Chunk(text=buffer, heading=heading, index=chunk_index))
                chunk_index += 1
            buffer = paragraph

        if buffer:
            chunks.append(Chunk(text=buffer, heading=heading, index=chunk_index))
            chunk_index += 1

    return chunks


def chunk_plain_text(text: str, title: str = "Document") -> list[Chunk]:
    cleaned = text.strip()
    if not cleaned:
        return []
    if len(cleaned) <= MAX_CHUNK_CHARS:
        return [Chunk(text=cleaned, heading=title, index=0)]

    chunks: list[Chunk] = []
    start = 0
    index = 0
    while start < len(cleaned):
        end = min(start + MAX_CHUNK_CHARS, len(cleaned))
        if end < len(cleaned):
            split_at = cleaned.rfind("\n\n", start, end)
            if split_at > start + MIN_CHUNK_CHARS:
                end = split_at
        chunk_text = cleaned[start:end].strip()
        if chunk_text:
            chunks.append(Chunk(text=chunk_text, heading=title, index=index))
            index += 1
        start = end

    return chunks
