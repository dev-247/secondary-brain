from __future__ import annotations

import html
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from scripts.config import VAULT_DIR, WIKI_DIR
from scripts.graph import list_relationships
from scripts.qdrant_setup import check_qdrant_health, qdrant_status_label
from scripts.router import ABSTENTION_MESSAGE, synthesize_answer_result
from scripts.search import diagnostic_rows, format_citation, hybrid_search

CHAT_HISTORY_LIMIT = 20
CHAT_HISTORY: list[dict[str, str]] = []
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def web_auth_token() -> str:
    return os.getenv("SECOND_BRAIN_WEB_TOKEN", "").strip()


def validate_web_bind(host: str, auth_token: str | None = None) -> None:
    token = web_auth_token() if auth_token is None else auth_token
    if host in LOCAL_HOSTS:
        return
    if token:
        return
    raise ValueError(
        "Non-local web access requires SECOND_BRAIN_WEB_TOKEN. "
        "Use localhost for local-only access or set a token before binding to the network."
    )


def _markdown_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.md") if path.is_file())


def _supported_source_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".md", ".markdown", ".txt"}
    )


def _frontmatter_value(text: str, key: str, default: str = "") -> str:
    if not text.startswith("---"):
        return default
    for line in text.splitlines()[1:]:
        if line.strip() == "---":
            break
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip() or default
    return default


def build_status_payload(
    *,
    vault_root: Path = VAULT_DIR,
    wiki_root: Path = WIKI_DIR,
) -> dict[str, object]:
    try:
        graph_relationships = len(list_relationships())
    except Exception:
        graph_relationships = 0

    return {
        "qdrant_ready": check_qdrant_health(),
        "qdrant": qdrant_status_label(),
        "vault_files": len(_markdown_files(vault_root)),
        "wiki_pages": len(_markdown_files(wiki_root)),
        "graph_relationships": graph_relationships,
    }


def list_wiki_pages(*, wiki_root: Path = WIKI_DIR) -> list[dict[str, str]]:
    pages: list[dict[str, str]] = []
    for path in _markdown_files(wiki_root):
        text = path.read_text(encoding="utf-8", errors="replace")
        title = _frontmatter_value(text, "title") or path.stem.replace("-", " ").title()
        review_status = _frontmatter_value(text, "review_status", "unknown")
        pages.append(
            {
                "path": path.relative_to(wiki_root).as_posix(),
                "title": title,
                "review_status": review_status,
            }
        )
    return pages


def list_source_files(*, vault_root: Path = VAULT_DIR) -> list[str]:
    return [path.relative_to(vault_root).as_posix() for path in _supported_source_files(vault_root)]


def read_source_file(path: str, *, vault_root: Path = VAULT_DIR) -> dict[str, str]:
    target = (vault_root / path).resolve()
    root = vault_root.resolve()
    if root not in target.parents and target != root:
        raise ValueError("source path must stay inside the vault")
    if not target.exists() or not target.is_file():
        raise FileNotFoundError(path)
    return {
        "path": target.relative_to(root).as_posix(),
        "content": target.read_text(encoding="utf-8", errors="replace"),
    }


def build_search_payload(query: str, *, limit: int = 5) -> dict[str, object]:
    query = query.strip()
    if not query:
        return {"query": query, "results": []}
    if not check_qdrant_health():
        return {"query": query, "results": [], "error": "qdrant is not ready"}

    results = hybrid_search(query, limit=limit)
    rows = diagnostic_rows(results, preview_chars=180)
    return {
        "query": query,
        "results": [
            {
                "path": row["path"],
                "heading": row["heading"],
                "chunk": row["chunk"],
                "score": row["score"],
                "citation": format_citation(result),
                "preview": row["preview"],
            }
            for row, result in zip(rows, results, strict=False)
        ],
    }


def clear_chat_history() -> None:
    CHAT_HISTORY.clear()


def get_chat_history() -> list[dict[str, str]]:
    return list(CHAT_HISTORY)


def _remember_chat_item(item: dict[str, str]) -> None:
    CHAT_HISTORY.insert(0, item)
    del CHAT_HISTORY[CHAT_HISTORY_LIMIT:]


def build_answer_payload(query: str, *, limit: int = 5) -> dict[str, object]:
    query = query.strip()
    if not query:
        return {"query": query, "answer": "", "sources": []}
    if not check_qdrant_health():
        return {
            "query": query,
            "answer": ABSTENTION_MESSAGE,
            "mode": "none",
            "confidence": "low",
            "sources": [],
            "error": "qdrant is not ready",
        }

    results = hybrid_search(query, limit=limit)
    try:
        answer_result = synthesize_answer_result(
            query,
            results,
            mode="fast",
        )
        answer = answer_result.answer
        mode = answer_result.mode
        confidence = answer_result.confidence
    except RuntimeError as exc:
        answer = str(exc)
        mode = "error"
        confidence = "low"

    sources = [
        {
            "path": result.path,
            "heading": result.heading,
            "chunk": result.chunk_index,
            "citation": format_citation(result),
        }
        for result in results
    ]
    _remember_chat_item(
        {
            "question": query,
            "answer": answer,
            "mode": mode,
            "confidence": confidence,
        }
    )
    return {
        "query": query,
        "answer": answer,
        "mode": mode,
        "confidence": confidence,
        "sources": sources,
    }


def _status_chip(ready: bool) -> str:
    label = "ready" if ready else "down"
    tone = "good" if ready else "bad"
    return f'<span class="chip {tone}">{label}</span>'


def render_dashboard(
    *,
    status: dict[str, object],
    wiki_pages: list[dict[str, str]],
    source_files: list[str] | None = None,
    search_payload: dict[str, object] | None = None,
    answer_payload: dict[str, object] | None = None,
    chat_history: list[dict[str, str]] | None = None,
) -> str:
    source_files = source_files or []
    search_payload = search_payload or {"query": "", "results": []}
    answer_payload = answer_payload or {"query": "", "answer": "", "sources": []}
    chat_history = chat_history or []
    wiki_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(page['title'])}</td>"
        f"<td>{html.escape(page['review_status'])}</td>"
        f"<td>{html.escape(page['path'])}</td>"
        "</tr>"
        for page in wiki_pages
    ) or '<tr><td colspan="3" class="muted">No wiki pages yet.</td></tr>'
    source_rows = "\n".join(
        f'<tr><td><a href="/source?path={html.escape(path)}">{html.escape(path)}</a></td></tr>'
        for path in source_files
    ) or '<tr><td class="muted">No supported source files yet.</td></tr>'
    search_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(str(item['score']))}</td>"
        f"<td>{html.escape(str(item['path']))}</td>"
        f"<td>{html.escape(str(item['citation']))}<br><span class=\"muted\">{html.escape(str(item['preview']))}</span></td>"
        "</tr>"
        for item in search_payload.get("results", [])
    ) or '<tr><td colspan="3" class="muted">Run a search to inspect cited chunks.</td></tr>'
    answer_sources = "\n".join(
        f"<li>{html.escape(str(source['citation']))}</li>"
        for source in answer_payload.get("sources", [])
    ) or '<li class="muted">No answer sources yet.</li>'
    history_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(item['question'])}<br><span class=\"muted\">{html.escape(item['mode'])} / {html.escape(item['confidence'])}</span></td>"
        f"<td>{html.escape(item['answer'])}</td>"
        "</tr>"
        for item in chat_history[:8]
    ) or '<tr><td colspan="2" class="muted">Ask a question to start chat history.</td></tr>'

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Second Brain</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #24292f;
      --muted: #57606a;
      --line: #d0d7de;
      --panel: #f6f8fa;
      --paper: #ffffff;
      --accent: #0969da;
      --accent-2: #8250df;
      --warn: #b45309;
      --bad: #cf222e;
      --shadow: 0 1px 0 rgba(27, 31, 36, .04);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font: 14px/1.45 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: #f6f8fa;
    }}
    .shell {{
      display: grid;
      grid-template-columns: 260px minmax(0, 1fr);
      min-height: 100vh;
    }}
    aside {{
      border-right: 1px solid var(--line);
      background: #ffffff;
      padding: 20px;
    }}
    main {{ padding: 24px; }}
    h1 {{ font-size: 22px; margin: 0 0 4px; letter-spacing: 0; }}
    h2 {{ font-size: 15px; margin: 0 0 12px; letter-spacing: 0; }}
    .muted {{ color: var(--muted); }}
    .nav {{ display: grid; gap: 8px; margin-top: 24px; }}
    .nav a {{ color: var(--ink); text-decoration: none; padding: 8px 0; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(150px, 1fr));
      gap: 12px;
      margin-bottom: 20px;
    }}
    .panel {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      background: var(--paper);
      box-shadow: var(--shadow);
    }}
    .metric {{ font-size: 24px; font-weight: 700; }}
    .chip {{
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 2px 8px;
      border-radius: 999px;
      border: 1px solid var(--line);
      font-weight: 600;
    }}
    .chip.good {{ color: var(--accent); border-color: #99d6ce; background: #eefaf8; }}
    .chip.bad {{ color: var(--bad); border-color: #fecaca; background: #fff1f2; }}
    .workbench {{
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(320px, .8fr);
      gap: 16px;
    }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 9px 6px; text-align: left; vertical-align: top; }}
    th {{ font-size: 12px; color: var(--muted); font-weight: 700; text-transform: uppercase; }}
    .command-list {{ display: grid; gap: 10px; }}
    .search-form {{ display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; margin-bottom: 12px; }}
    input, button {{
      min-height: 36px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 6px 10px;
      font: inherit;
    }}
    button {{ background: #24292f; color: white; cursor: pointer; font-weight: 600; }}
    button:hover {{ background: #32383f; }}
    textarea {{
      width: 100%;
      min-height: 88px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px 10px;
      font: inherit;
    }}
    pre {{
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      background: #f6f8fa;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 12px;
    }}
    code {{ background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 2px 6px; }}
    @media (max-width: 900px) {{
      .shell {{ grid-template-columns: 1fr; }}
      aside {{ border-right: 0; border-bottom: 1px solid var(--line); }}
      .grid, .workbench {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <aside>
      <h1>Second Brain</h1>
      <div class="muted">Local-first AI knowledge cockpit</div>
      <nav class="nav" aria-label="Sections">
        <a href="#ingestion">Ingestion</a>
        <a href="#ask">Ask</a>
        <a href="#search">Search</a>
        <a href="#sources">Sources</a>
        <a href="#wiki">Wiki</a>
        <a href="#graph">Graph</a>
      </nav>
    </aside>
    <main>
      <section class="grid" aria-label="Status">
        <div class="panel"><h2>Qdrant</h2>{_status_chip(bool(status['qdrant_ready']))}<div class="muted">{html.escape(str(status['qdrant']))}</div></div>
        <div class="panel"><h2>Vault</h2><div class="metric">{status['vault_files']}</div><div class="muted">markdown files</div></div>
        <div class="panel"><h2>Wiki</h2><div class="metric">{status['wiki_pages']}</div><div class="muted">pages</div></div>
        <div class="panel"><h2>Graph</h2><div class="metric">{status['graph_relationships']}</div><div class="muted">relationships</div></div>
      </section>
      <section class="workbench">
        <div class="panel" id="ask">
          <h2>Ask</h2>
          <form action="/ask" method="get" class="command-list">
            <textarea name="q" placeholder="Ask a source-grounded question">{html.escape(str(answer_payload.get('query', '')))}</textarea>
            <button type="submit">Ask local model</button>
          </form>
          <pre>{html.escape(str(answer_payload.get('answer', 'Ask a question to generate a cited answer.')))}</pre>
          <h2>Sources</h2>
          <ul>{answer_sources}</ul>
        </div>
        <div class="panel" id="search">
          <h2>Search</h2>
          <form action="/search" method="get" class="search-form">
            <input name="q" value="{html.escape(str(search_payload.get('query', '')))}" placeholder="Search your indexed knowledge">
            <button type="submit">Search</button>
          </form>
          <table>
            <thead><tr><th>Score</th><th>Path</th><th>Citation and Preview</th></tr></thead>
            <tbody>{search_rows}</tbody>
          </table>
        </div>
        <div class="panel" id="wiki">
          <h2>Wiki</h2>
          <table>
            <thead><tr><th>Title</th><th>Status</th><th>Path</th></tr></thead>
            <tbody>{wiki_rows}</tbody>
          </table>
        </div>
        <div class="panel" id="sources">
          <h2>Sources</h2>
          <table>
            <thead><tr><th>Path</th></tr></thead>
            <tbody>{source_rows}</tbody>
          </table>
        </div>
        <div class="panel">
          <h2>Chat history</h2>
          <table>
            <thead><tr><th>Question</th><th>Answer</th></tr></thead>
            <tbody>{history_rows}</tbody>
          </table>
        </div>
        <div class="panel">
          <h2>Workflow</h2>
          <div class="command-list">
            <div id="ingestion"><strong>Ingestion</strong><br><code>uv run python main.py ingest</code></div>
            <div><strong>Search</strong><br><code>uv run python main.py search "query"</code></div>
            <div><strong>Ask</strong><br><code>uv run python main.py ask "question"</code></div>
            <div id="graph"><strong>Graph</strong><br><code>uv run python main.py graph-build</code></div>
          </div>
        </div>
      </section>
    </main>
  </div>
</body>
</html>
"""


def render_source_page(
    *,
    status: dict[str, object],
    wiki_pages: list[dict[str, str]],
    source_files: list[str],
    source: dict[str, str],
) -> str:
    dashboard = render_dashboard(
        status=status,
        wiki_pages=wiki_pages,
        source_files=source_files,
    )
    source_panel = (
        '<div class="panel">'
        f"<h2>Source: {html.escape(source['path'])}</h2>"
        f"<pre>{html.escape(source['content'])}</pre>"
        "</div>"
    )
    return dashboard.replace("</main>", f"{source_panel}</main>")


class SecondBrainWebHandler(BaseHTTPRequestHandler):
    def _authorized(self) -> bool:
        token = web_auth_token()
        if not token:
            return True
        parsed = urlparse(self.path)
        query_token = parse_qs(parsed.query).get("token", [""])[0]
        header_token = self.headers.get("X-Second-Brain-Token", "")
        return query_token == token or header_token == token

    def _send_json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, body: str, status: int = 200) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        if not self._authorized():
            self._send_json({"error": "unauthorized"}, status=401)
            return
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            self._send_json(build_status_payload())
            return
        if parsed.path == "/api/wiki":
            self._send_json({"pages": list_wiki_pages()})
            return
        if parsed.path == "/api/search":
            params = parse_qs(parsed.query)
            query = params.get("q", [""])[0]
            limit = int(params.get("limit", ["5"])[0])
            self._send_json(build_search_payload(query, limit=limit))
            return
        if parsed.path == "/api/ask":
            params = parse_qs(parsed.query)
            query = params.get("q", [""])[0]
            limit = int(params.get("limit", ["5"])[0])
            self._send_json(build_answer_payload(query, limit=limit))
            return
        if parsed.path == "/api/source":
            params = parse_qs(parsed.query)
            source_path = params.get("path", [""])[0]
            try:
                self._send_json(read_source_file(source_path))
            except (FileNotFoundError, ValueError) as exc:
                self._send_json({"error": str(exc)}, status=404)
            return
        if parsed.path == "/search":
            params = parse_qs(parsed.query)
            query = params.get("q", [""])[0]
            self._send_html(
                render_dashboard(
                    status=build_status_payload(),
                    wiki_pages=list_wiki_pages(),
                    source_files=list_source_files(),
                    search_payload=build_search_payload(query),
                    chat_history=get_chat_history(),
                )
            )
            return
        if parsed.path == "/ask":
            params = parse_qs(parsed.query)
            query = params.get("q", [""])[0]
            answer_payload = build_answer_payload(query)
            self._send_html(
                render_dashboard(
                    status=build_status_payload(),
                    wiki_pages=list_wiki_pages(),
                    source_files=list_source_files(),
                    answer_payload=answer_payload,
                    chat_history=get_chat_history(),
                )
            )
            return
        if parsed.path == "/source":
            params = parse_qs(parsed.query)
            source_path = params.get("path", [""])[0]
            try:
                source = read_source_file(source_path)
            except (FileNotFoundError, ValueError) as exc:
                self._send_json({"error": str(exc)}, status=404)
                return
            self._send_html(
                render_source_page(
                    status=build_status_payload(),
                    wiki_pages=list_wiki_pages(),
                    source_files=list_source_files(),
                    source=source,
                )
            )
            return
        if parsed.path == "/":
            self._send_html(
                render_dashboard(
                    status=build_status_payload(),
                    wiki_pages=list_wiki_pages(),
                    source_files=list_source_files(),
                    chat_history=get_chat_history(),
                )
            )
            return
        self._send_json({"error": "not found"}, status=404)

    def log_message(self, format: str, *args: object) -> None:
        return


def run_web_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    validate_web_bind(host)
    server = ThreadingHTTPServer((host, port), SecondBrainWebHandler)
    print(f"Second Brain web UI running at http://{host}:{port}")
    server.serve_forever()
