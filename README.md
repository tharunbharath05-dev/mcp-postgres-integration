# PostgreSQL MCP server

This project exposes read-only employee lookup tools through the MCP SDK's
`MCPServer` API.

## Setup

Use Python 3.14 or newer and install the project from this directory:

```powershell
uv sync
```

Copy `.env.example` to `.env` and set `DATABASE_URL` to your PostgreSQL
connection string. Environment variables take precedence over values in
`mcp_config.json`, so a placeholder there cannot override your local database
URL.

To run the agent, set `NVIDIA_API_KEY` to a valid NVIDIA API Catalog key in
`.env` (use the raw key, without a `Bearer` prefix). The agent also accepts the
legacy `LLM_API_KEY` variable. The key shown in `.env.example` is only a
placeholder and will not authenticate. The NVIDIA OpenAI-compatible base URL
is `https://integrate.api.nvidia.com/v1`.

## Run with MCP Inspector

```powershell
uv run mcp dev server\mcp_server.py
```

## Run the employee agent

```powershell
uv run python -m client.agent
```

`uv sync` installs the local `server` package into the project environment so
the MCP CLI can import it when loading the server file.