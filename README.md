# sensorbio-mcp-server (Python)

Python MCP (Model Context Protocol) server for **Sensr** (https://api.getsensr.io).

## Requirements
- Python **3.11+**
- `uv` / `uvx`

## Authentication

This server supports **two** authentication modes:

### 1) Organization token (recommended if you have it)

- Env var: `SENSR_ORG_TOKEN`
- Request header: `Authorization: APIKey <token>`

### 2) OAuth2 (client_credentials)

- Env vars: `SENSR_CLIENT_ID`, `SENSR_CLIENT_SECRET`
- Optional: `SENSR_SCOPE`
- Token URL: `https://auth.getsensr.io/token`
- (Documented, not used for client_credentials) Auth URL: `https://auth.getsensr.io/authorize`
- (Documented) Redirect URL: `https://developers.getsensr.io/`

Notes:
- `SensrClient.from_env()` **prefers** `SENSR_ORG_TOKEN` when present; otherwise it uses OAuth.
- OAuth access tokens are cached in-memory and refreshed when there are **< 60s** left before expiry.

## Install / Run (uvx)

### From local checkout
```bash
uvx --from . sensorbio-mcp-server
```

### From GitHub
```bash
uvx --from git+https://github.com/Biostrap/sensorbio-mcp-server-python sensorbio-mcp-server
```

## Claude Desktop config

Add this to Claude Desktop `mcpServers`.

### Option A: Organization token
```json
{
  "mcpServers": {
    "sensorbio": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/Biostrap/sensorbio-mcp-server-python",
        "sensorbio-mcp-server"
      ],
      "env": {
        "SENSR_ORG_TOKEN": "YOUR_SENSR_ORG_TOKEN"
      }
    }
  }
}
```

### Option B: OAuth2 client_credentials
```json
{
  "mcpServers": {
    "sensorbio": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/Biostrap/sensorbio-mcp-server-python",
        "sensorbio-mcp-server"
      ],
      "env": {
        "SENSR_CLIENT_ID": "YOUR_CLIENT_ID",
        "SENSR_CLIENT_SECRET": "YOUR_CLIENT_SECRET",
        "SENSR_SCOPE": "optional"
      }
    }
  }
}
```

## Tools exposed (matching Node server)
- `list_users(page=1, limit=100, search=None)`
- `get_user_ids()`
- `get_sleep(user_id, date=None)`
- `get_scores(user_id, date=None)`
- `get_activities(user_id, last_timestamp=0, limit=50)`
- `get_biometrics(user_id, last_timestamp=0, limit=50)`
- `get_calories(user_id, date=None, granularity=None)`
- `debug_request(path, query=None)`

## Smoke test

Calls `/v1/organizations/users/ids` using the active auth mode:

```bash
uv run python3 scripts/smoke_test.py
```

## Publishing to GitHub (instructions)

```bash
cd /home/ubuntu/.openclaw/shared/projects/sensorbio-mcp-server-python
gh repo create Biostrap/sensorbio-mcp-server-python --public --source . --remote origin --push
```

Then update the GitHub URL in the Claude Desktop snippet above.
