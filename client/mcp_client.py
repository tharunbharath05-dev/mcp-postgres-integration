import asyncio
import json
import logging
import os
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Dict, List

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def get_client_logger(name: str = "mcp.client") -> logging.Logger:
    """Configure a clean client logger completely decoupled from server modules."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False
    return logger


logger = get_client_logger()


class PostgresMCPClient:
    """Enterprise MCP Client responsible for loading config, connecting over stdio, and discovering tools."""

    def __init__(self, config_path: str = "mcp_config.json", server_name: str = "postgres-employee-service") -> None:
        self.config_path = Path(config_path)
        self.server_name = server_name
        self.exit_stack = AsyncExitStack()
        self.session: ClientSession | None = None

    def _load_server_params(self) -> StdioServerParameters:
        """Read mcp_config.json and build StdioServerParameters for the target server."""
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"MCP configuration file not found at '{self.config_path}'. "
                "Copy mcp_config.example.json to mcp_config.json and set DATABASE_URL."
            )

        with self.config_path.open("r", encoding="utf-8") as f:
            raw_config = json.load(f)

        servers = raw_config.get("mcpServers", {})
        if self.server_name not in servers:
            raise KeyError(
                f"Server '{self.server_name}' not defined in '{self.config_path}'. "
                f"Available servers: {list(servers.keys())}"
            )

        server_cfg = servers[self.server_name]
        # Merge host environment (PATH, SystemRoot on Windows, etc.) with server-specific env vars
        merged_env = {**os.environ, **server_cfg.get("env", {})}

        return StdioServerParameters(
            command=server_cfg["command"],
            args=server_cfg.get("args", []),
            env=merged_env,
        )

    async def connect(self) -> None:
        """Spawn the MCP server subprocess and complete the MCP protocol initialization handshake."""
        server_params = self._load_server_params()
        logger.info(f"Launching MCP server '{self.server_name}' via command: {server_params.command} {' '.join(server_params.args)}")

        read_stream, write_stream = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )

        
        init_result = await self.session.initialize()
        logger.info(
            f"Connected to MCP server: {init_result.server_info.name} "
            f"(protocol version: {init_result.protocol_version})"
            )

    async def discover_tools(self) -> List[Dict[str, Any]]:
        """Query the connected MCP server for all exposed tools and their JSON schemas."""
        if self.session is None:
            raise RuntimeError("Client is not connected. Call connect() before discover_tools().")

        response = await self.session.list_tools()
        discovered: List[Dict[str, Any]] = []

        for tool in response.tools:
            schema = getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", {})
            discovered.append(
                {
                    "name": tool.name,
                    "description": (tool.description or "").strip(),
                    "input_schema": schema,
                }
            )

        logger.info(f"Discovered {len(discovered)} tool(s) from '{self.server_name}'.")
        return discovered

    async def close(self) -> None:
        """Cleanly shut down the MCP session and terminate the server subprocess."""
        await self.exit_stack.aclose()
        self.session = None
        logger.info("MCP Client session closed cleanly.")


async def main() -> None:
    """Day 6 verification entry point: connect and print discovered tools."""
    client = PostgresMCPClient()
    try:
        await client.connect()
        tools = await client.discover_tools()

        print("\n=== Discovered MCP Tools ===")
        for idx, tool in enumerate(tools, start=1):
            print(f"\n[{idx}] Tool Name   : {tool['name']}")
            print(f"    Description : {tool['description'].splitlines()[0]}")
            print(f"    Input Schema: {json.dumps(tool['input_schema'])}")
    except Exception as e:
        logger.error(f"MCP Client discovery failed: {e}")
        raise
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())