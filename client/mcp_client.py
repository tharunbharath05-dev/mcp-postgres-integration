import asyncio
import json
import logging
import os
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import MCPError


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
    """Enterprise MCP Client for loading config, discovering tools, and invoking tools over stdio."""

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
        load_dotenv(dotenv_path=self.config_path.resolve().parent / ".env")
        merged_env = {**server_cfg.get("env", {}), **os.environ}

        return StdioServerParameters(
            command=server_cfg["command"],
            args=server_cfg.get("args", []),
            env=merged_env,
        )

    async def connect(self) -> None:
        """Spawn the MCP server subprocess and complete the MCP protocol initialization handshake."""
        server_params = self._load_server_params()
        logger.info(
            f"Launching MCP server '{self.server_name}' via: "
            f"{server_params.command} {' '.join(server_params.args)}"
        )

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

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Invoke an MCP tool by name and return a normalized response dictionary."""
        if self.session is None:
            raise RuntimeError("Client is not connected. Call connect() before execute_tool().")

        args = arguments or {}
        logger.info(f"Calling MCP tool '{tool_name}' with arguments={args}")

        try:
            result = await self.session.call_tool(tool_name, arguments=args)
            is_protocol_error = bool(getattr(result, "is_error", False) or getattr(result, "isError", False))

            # Extract text payload from MCP TextContent blocks
            text_chunks = [
                block.text for block in result.content if getattr(block, "type", None) == "text"
            ]
            raw_text = "\n".join(text_chunks).strip()

            if is_protocol_error:
                logger.warning(f"MCP protocol/schema validation error from '{tool_name}': {raw_text}")
                return {"status": "error", "source": "mcp_validation", "message": raw_text}

            try:
                parsed = json.loads(raw_text)
                return parsed if isinstance(parsed, dict) else {"status": "success", "data": parsed}
            except json.JSONDecodeError:
                return {"status": "success", "raw_output": raw_text}

        except MCPError as e:
            logger.error(f"MCPError invoking '{tool_name}': {e}")
            return {"status": "error", "source": "mcp_protocol", "message": str(e)}
        except Exception as e:
            logger.exception(f"Unexpected client error invoking '{tool_name}'")
            return {"status": "error", "source": "client_runtime", "message": str(e)}

    async def close(self) -> None:
        """Cleanly shut down the MCP session and terminate the server subprocess."""
        await self.exit_stack.aclose()
        self.session = None
        logger.info("MCP Client session closed cleanly.")


async def main() -> None:
    """End-to-end demonstration: connect, discover tools, invoke valid & invalid queries."""
    client = PostgresMCPClient()
    try:
        # 1. Connect & Handshake
        await client.connect()

        # 2. Tool Discovery
        tools = await client.discover_tools()
        print("\n=== 1. Discovered MCP Tools ===")
        for tool in tools:
            print(f"- {tool['name']}: {tool['description'].splitlines()[0]}")

        # 3. Execute get_all_employees()
        print("\n=== 2. Executing get_all_employees() ===")
        all_employees = await client.execute_tool("get_all_employees")
        print(json.dumps(all_employees, indent=2))

        # 4. Execute get_employee_by_id(2) — Valid ID
        print("\n=== 3. Executing get_employee_by_id(employee_id=2) ===")
        employee_2 = await client.execute_tool("get_employee_by_id", {"employee_id": 2})
        print(json.dumps(employee_2, indent=2))

        # 5. Execute get_employee_by_id(999) — Non-existent ID (Database layer error)
        print("\n=== 4. Executing get_employee_by_id(employee_id=999) [Non-existent ID] ===")
        missing_employee = await client.execute_tool("get_employee_by_id", {"employee_id": 999})
        print(json.dumps(missing_employee, indent=2))

        # 6. Execute get_employee_by_id(-5) — Schema Violation (FastMCP Pydantic validation error)
        print("\n=== 5. Executing get_employee_by_id(employee_id=-5) [Schema Validation Error] ===")
        invalid_employee = await client.execute_tool("get_employee_by_id", {"employee_id": -5})
        print(json.dumps(invalid_employee, indent=2))

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())