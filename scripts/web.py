from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from scripts.config import VAULT_DIR, WIKI_DIR
from scripts.graph import list_relationships
from scripts.qdrant_setup import check_qdrant_health, qdrant_status_label


def _markdown_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.md") if path.is_file())


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


def _status_chip(ready: bool) -> str:
    label = "ready" if ready else "down"
    tone = "good" if ready else "bad"
    return f'<span class="chip {tone}">{label}</span>'


def render_dashboard(
    *,
    status: dict[str, object],
    wiki_pages: list[dict[str, str]],
) -> str:
    wiki_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(page['title'])}</td>"
        f"<td>{html.escape(page['review_status'])}</td>"
        f"<td>{html.escape(page['path'])}</td>"
        "</tr>"
        for page in wiki_pages
    ) or '<tr><td colspan="3" class="muted">No wiki pages yet.</td></tr>'

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Second Brain</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #172026;
      --muted: #66727d;
      --line: #d8dee4;
      --panel: #f6f8fa;
      --paper: #ffffff;
      --accent: #0f766e;
      --accent-2: #7c3aed;
      --warn: #b45309;
      --bad: #b91c1c;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font: 14px/1.45 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--paper);
    }}
    .shell {{
      display: grid;
      grid-template-columns: 260px minmax(0, 1fr);
      min-height: 100vh;
    }}
    aside {{
      border-right: 1px solid var(--line);
      background: var(--panel);
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
        <a href="#search">Search</a>
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
        <div class="panel" id="wiki">
          <h2>Wiki</h2>
          <table>
            <thead><tr><th>Title</th><th>Status</th><th>Path</th></tr></thead>
            <tbody>{wiki_rows}</tbody>
          </table>
        </div>
        <div class="panel">
          <h2>Workflow</h2>
          <div class="command-list">
            <div id="ingestion"><strong>Ingestion</strong><br><code>uv run python main.py ingest</code></div>
            <div id="search"><strong>Search</strong><br><code>uv run python main.py search "query"</code></div>
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


class SecondBrainWebHandler(BaseHTTPRequestHandler):
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
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            self._send_json(build_status_payload())
            return
        if parsed.path == "/api/wiki":
            self._send_json({"pages": list_wiki_pages()})
            return
        if parsed.path == "/":
            self._send_html(
                render_dashboard(
                    status=build_status_payload(),
                    wiki_pages=list_wiki_pages(),
                )
            )
            return
        self._send_json({"error": "not found"}, status=404)

    def log_message(self, format: str, *args: object) -> None:
        return


def run_web_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ThreadingHTTPServer((host, port), SecondBrainWebHandler)
    print(f"Second Brain web UI running at http://{host}:{port}")
    server.serve_forever()
