# Connect your MCP client to the hub

The hub speaks the modern **Streamable HTTP** MCP transport (spec 2025-03-26 /
2025-06-18) at a single endpoint, authenticated with a per-user bearer token.
Once configured, its tools appear in your client. The endpoint negotiates the
protocol version on `initialize`, issues an `Mcp-Session-Id`, replies to a
JSON-RPC request with a single `application/json` response, and returns `202`
for notifications. (It serves no server-initiated `GET` stream — a `GET`
returns `405`, which is spec-compliant; clients tolerate it.)

## 1. Get your token
Dashboard → **Profile** → **Issue token** (shown once, prefix `ash_`), or the
**Manual / Connect** page which builds the config for you with the token filled
in. Admins can issue tokens for others (Employees → Token).

You can hold **several** tokens — name them after where each one lives (laptop,
CI, claude.ai) so revoking one does not black out the rest, and give anything
long-lived an expiry. The hub stores only a hash, so a token is unrecoverable
after that first screen: if you lose it, issue a new one and revoke the old.

## 2. Point your client at the hub

Base URL of the MCP endpoint = `<HUB>/mcp` — the path every PixOn app mounts its
connector at, so the address follows from the host alone. For the local dev
stack that is `http://localhost:28080/mcp` (or via the dashboard proxy
`http://localhost:28081/mcp`). For a deployed hub, use its domain:
`https://skillhub.pixon.cc/mcp`.

The hub also still answers on the older `/api/mcp` so clients configured before
the move keep working, but it is advertised nowhere and new setups must not use
it — the OAuth metadata names `/mcp`, and a mismatch there is what makes a
connector fail to attach.

### Claude Code (one command)
```bash
claude mcp add --transport http skill-hub http://localhost:28080/mcp \
  --header "Authorization: Bearer ash_YOUR_TOKEN"
```

### `.mcp.json` / Cursor `.cursor/mcp.json`
```json
{
  "mcpServers": {
    "skill-hub": {
      "type": "http",
      "url": "http://localhost:28080/mcp",
      "headers": { "Authorization": "Bearer ash_YOUR_TOKEN" }
    }
  }
}
```

### Claude Desktop (stdio, co-located with the hub only)
Build `ash-mcp` from the hub repo (`go build -o ash-mcp ./backend/cmd/mcp`) and,
in `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "skill-hub": {
      "command": "/path/to/ash-mcp",
      "env": { "ASH_MCP_TOKEN": "ash_YOUR_TOKEN", "ASH_DB_PATH": "/path/to/ash.db" }
    }
  }
}
```
The stdio binary reads the hub's SQLite DB directly, so it only works on the
machine hosting the hub. Prefer the HTTP transport for remote use.

### claude.ai / Claude Desktop / mobile — as a custom connector
Adds the hub's tools to Claude everywhere at once, with no local config and no
token to paste: the hub is its own OAuth 2.1 authorization server.

1. **Settings → Connectors → Add custom connector**
2. URL: `<HUB>/mcp` (for PixOn: `https://skillhub.pixon.cc/mcp`) — must be a
   **public** HTTPS URL. Claude connects from
   Anthropic's cloud, not from your machine, so `localhost` and VPN-only hosts
   cannot work no matter which device you are on.
3. **Add**. Leave Advanced settings empty — Claude registers itself
   (RFC 7591) and the hub issues it a client id.
4. A window opens on the hub console: sign in, choose which permissions to
   grant, **Approve**.
5. In a chat: **Search and tools** → enable it.

The connector ends up holding an ordinary hub token — scoped to what you
granted, expiring in a week, refreshed automatically. It shows up in
Profile → MCP tokens named after the client; revoking it there disconnects the
connector for good (the refresh token dies with it).

Behind Cloudflare Access, add a Bypass policy for `/mcp`,
`/.well-known/*` and `/oauth/*`; Claude carries no Access cookie and is
otherwise stopped before it reaches the hub.

## 3. Verify
Call `ping` → `"pong"`, then `search_skills({})`. If tools are missing, the
client is not connected; if calls 401, the token is wrong or expired. The hub
answers **401 with a `WWW-Authenticate` challenge** for any unauthenticated
call — that is what makes a connector offer to sign in rather than silently
failing every tool.

## Test it from a terminal (no client)
```bash
curl -X POST http://localhost:28080/mcp \
  -H "Authorization: Bearer ash_YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"search_skills","arguments":{"q":""}}}'
```
