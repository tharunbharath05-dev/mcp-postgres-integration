# PostgreSQL MCP server

This project exposes read-only employee lookup tools through the MCP SDK's
`MCPServer` API.

## Setup

Use Python 3.14 or newer and install the project from this directory:

```powershell
uv sync
```

Set `DATABASE_URL` in a local `.env` file. See `.env.example` for the expected
format.

## Run with MCP Inspector

```powershell
uv run mcp dev server\mcp_server.py
```

`uv sync` installs the local `server` package into the project environment so
the MCP CLI can import it when loading the server file.