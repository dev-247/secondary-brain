from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from qdrant_client import models
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from scripts.chunking import Chunk, chunk_markdown, chunk_plain_text
from scripts.config import METADATA_DB_PATH, QDRANT_COLLECTION, SUPPORTED_EXTENSIONS, VAULT_DIR
from scripts.embeddings import embed_text
from scripts.metadata import (
    CURRENT_INDEX_VERSION,
    DEFAULT_PARSER_VERSION,
    delete_source_record,
    get_source_record,
    list_source_records,
    SourceRecord,
    compute_file_fingerprint,
    mark_source_indexed,
    source_needs_ingest,
)
from scripts.qdrant_setup import check_qdrant_health, ensure_collection, get_client

console = Console()

TEXT_MIME_TYPES = {
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".txt": "text/plain",
}

DOCLING_MIME_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _point_id(source_path: str, chunk_index: int) -> str:
    digest = hashlib.sha256(f"{source_path}:{chunk_index}".encode()).hexdigest()
    return str(uuid.UUID(digest[:32]))


def _extract_with_docling(path: Path) -> tuple[str, str]:
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    result = converter.convert(str(path))
    markdown = result.document.export_to_markdown()
    title = path.stem.replace("_", " ").replace("-", " ").title()
    return title, markdown


def _extract_text(path: Path) -> tuple[str, str]:
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown", ".txt"}:
        text = path.read_text(encoding="utf-8", errors="replace")
        title = path.stem.replace("_", " ").replace("-", " ").title()
        return title, text
    title, markdown = _extract_with_docling(path)
    return title, markdown


def _source_metadata(path: Path) -> dict[str, object]:
    extension = path.suffix.lower()
    return {
        "mime_type": TEXT_MIME_TYPES.get(extension) or DOCLING_MIME_TYPES.get(extension) or "application/octet-stream",
        "extension": extension,
        "parser_name": "direct" if extension in TEXT_MIME_TYPES else "docling",
        "parser_version": DEFAULT_PARSER_VERSION,
        "index_version": CURRENT_INDEX_VERSION,
    }


def _chunk_document(title: str, text: str, suffix: str) -> list[Chunk]:
    if suffix in {".md", ".markdown"}:
        return chunk_markdown(text)
    if suffix == ".txt":
        return chunk_plain_text(text, title=title)
    if text.lstrip().startswith("#"):
        return chunk_markdown(text)
    return chunk_plain_text(text, title=title)


def discover_files(root: Path | None = None) -> list[Path]:
    root = root or VAULT_DIR
    if not root.exists():
        return []
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            if not path.name.startswith("."):
                files.append(path)
    return files


def delete_indexed_source(client: object, relative_path: str, chunks: int) -> None:
    if chunks <= 0:
        return
    point_ids = [_point_id(relative_path, index) for index in range(chunks)]
    client.delete(
        collection_name=QDRANT_COLLECTION,
        points_selector=models.PointIdsList(points=point_ids),
    )


def cleanup_deleted_sources(
    *,
    vault_root: Path,
    indexed_paths: set[str],
    metadata_path: Path,
    client: object,
) -> int:
    deleted = 0
    for record in list_source_records(metadata_path):
        if record.path in indexed_paths:
            continue
        delete_indexed_source(client, record.path, record.chunks)
        delete_source_record(metadata_path, record.path)
        deleted += 1
    return deleted


def ingest_file(
    path: Path,
    vault_root: Path | None = None,
    metadata_path: Path = METADATA_DB_PATH,
    client: object | None = None,
) -> int:
    vault_root = vault_root or VAULT_DIR
    relative_path = path.relative_to(vault_root).as_posix()
    fingerprint = compute_file_fingerprint(path)
    source_metadata = _source_metadata(path)
    if not source_needs_ingest(metadata_path, relative_path, fingerprint):
        return 0
    previous_record = get_source_record(metadata_path, relative_path)

    suffix = path.suffix.lower()
    title, text = _extract_text(path)
    chunks = _chunk_document(title, text, suffix)
    if not chunks:
        mark_source_indexed(
            metadata_path,
            SourceRecord(
                path=relative_path,
                sha256=fingerprint.sha256,
                size_bytes=fingerprint.size_bytes,
                modified_ns=fingerprint.modified_ns,
                chunks=0,
                mime_type=str(source_metadata["mime_type"]),
                extension=str(source_metadata["extension"]),
                parser_name=str(source_metadata["parser_name"]),
                parser_version=str(source_metadata["parser_version"]),
                index_version=int(source_metadata["index_version"]),
            ),
        )
        return 0

    client = client or get_client()
    ensure_collection(client)
    if previous_record is not None:
        delete_indexed_source(client, relative_path, previous_record.chunks)

    ingested_at = datetime.now(timezone.utc).isoformat()
    points: list[models.PointStruct] = []

    for chunk in chunks:
        dense = embed_text(chunk.text)
        points.append(
            models.PointStruct(
                id=_point_id(relative_path, chunk.index),
                vector={
                    "dense": dense,
                    "sparse": models.Document(text=chunk.text, model="qdrant/bm25"),
                },
            payload={
                    "filename": path.name,
                    "path": relative_path,
                    "absolute_path": str(path.resolve()),
                    "mime_type": source_metadata["mime_type"],
                    "extension": source_metadata["extension"],
                    "parser_name": source_metadata["parser_name"],
                    "parser_version": source_metadata["parser_version"],
                    "index_version": source_metadata["index_version"],
                    "heading": chunk.heading,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "chunk_index": chunk.index,
                    "content": chunk.text,
                    "title": title,
                    "ingested_at": ingested_at,
                },
            )
        )

    client.upsert(collection_name=QDRANT_COLLECTION, points=points)
    mark_source_indexed(
        metadata_path,
        SourceRecord(
            path=relative_path,
            sha256=fingerprint.sha256,
            size_bytes=fingerprint.size_bytes,
            modified_ns=fingerprint.modified_ns,
            chunks=len(points),
            mime_type=str(source_metadata["mime_type"]),
            extension=str(source_metadata["extension"]),
            parser_name=str(source_metadata["parser_name"]),
            parser_version=str(source_metadata["parser_version"]),
            index_version=int(source_metadata["index_version"]),
        ),
    )
    return len(points)


def ingest_vault(
    root: Path | None = None,
    metadata_path: Path = METADATA_DB_PATH,
) -> dict[str, int]:
    if not check_qdrant_health():
        raise RuntimeError(
            "Qdrant is not reachable. Start Docker (docker compose up -d) "
            "or set QDRANT_MODE=local in .env for embedded storage."
        )

    root = root or VAULT_DIR
    root.mkdir(parents=True, exist_ok=True)
    files = discover_files(root)
    indexed_paths = {path.relative_to(root).as_posix() for path in files}
    client = get_client()
    ensure_collection(client)
    deleted = cleanup_deleted_sources(
        vault_root=root,
        indexed_paths=indexed_paths,
        metadata_path=metadata_path,
        client=client,
    )
    if not files:
        console.print(f"[yellow]No supported files found in {root}[/yellow]")
        return {
            "files": 0,
            "chunks": 0,
            "skipped": 0,
            "deleted": deleted,
            "failed": 0,
            "failed_files": [],
        }

    total_chunks = 0
    skipped = 0
    failed_files: list[dict[str, str]] = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Ingesting vault...", total=len(files))
        for path in files:
            progress.update(task, description=f"Ingesting {path.name}")
            relative_path = path.relative_to(root).as_posix()
            try:
                chunks = ingest_file(path, vault_root=root, metadata_path=metadata_path, client=client)
            except Exception as exc:
                failed_files.append({"path": relative_path, "error": str(exc)})
                progress.advance(task)
                continue

            if chunks == 0:
                fingerprint = compute_file_fingerprint(path)
                if not source_needs_ingest(metadata_path, relative_path, fingerprint):
                    skipped += 1
            total_chunks += chunks
            progress.advance(task)

    return {
        "files": len(files),
        "chunks": total_chunks,
        "skipped": skipped,
        "deleted": deleted,
        "failed": len(failed_files),
        "failed_files": failed_files,
    }


if __name__ == "__main__":
    stats = ingest_vault()
    console.print(
        f"[green]Done.[/green] Ingested {stats['chunks']} chunks from {stats['files']} files."
    )
