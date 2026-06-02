# Private Access Guide

Second Brain is local-first. Keep the web UI bound to localhost unless you are intentionally using a private network.

## Local only

```bash
uv run python main.py web
```

This binds to `127.0.0.1:8765` and does not expose the UI to your network.

## Private network access

Use a private overlay network such as Tailscale before exposing the service beyond localhost.

```bash
export SECOND_BRAIN_WEB_TOKEN="choose-a-long-random-token"
uv run python main.py web --host 0.0.0.0 --port 8765
```

Requests must include the token:

```bash
curl -H "X-Second-Brain-Token: choose-a-long-random-token" http://HOST:8765/api/status
```

Do not expose this service directly to the public internet. Add a real authentication layer before any public deployment.
