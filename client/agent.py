import asyncio
import json
import os
from typing import Any, Dict, List

from dotenv import load_dotenv
from openai import AsyncOpenAI

from client.mcp_client import PostgresMCPClient, get_client_logger

load_dotenv()
logger = get_client_logger("mcp.client.agent")


def _get_llm_api_key() -> str:
    """Read NVIDIA's key name, with support for the legacy project name."""
    api_key = os.getenv("NVIDIA_API_KEY", "").strip() or os.getenv("LLM_API_KEY", "").strip()
    if api_key.lower().startswith("bearer "):
        logger.warning("Remove the 'Bearer' prefix from the API key; the SDK adds it to the request.")
        api_key = api_key[7:].strip()
    return api_key


def _normalize_llm_base_url(base_url: str) -> str:
    """Accept an API base URL or a full OpenAI-compatible chat-completions URL."""
    base_url = base_url.rstrip("/")
    endpoint_suffix = "/chat/completions"
    if base_url.endswith(endpoint_suffix):
        logger.warning(
            "LLM_BASE_URL includes '/chat/completions'; removing it because the SDK appends this route."
        )
        base_url = base_url[: -len(endpoint_suffix)]
    return base_url


def mcp_tools_to_openai_schema(mcp_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert MCP tool definitions into OpenAI function-calling tool schemas."""
    openai_tools: List[Dict[str, Any]] = []
    for tool in mcp_tools:
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"],
                },
            }
        )
    return openai_tools


class EmployeeDatabaseAgent:
    """Autonomous AI Agent that answers HR queries using MCP-exposed PostgreSQL tools."""

    def __init__(self, mcp_client: PostgresMCPClient, max_turns: int = 5) -> None:
        api_key = _get_llm_api_key()
        if not api_key:
            raise EnvironmentError(
                "CRITICAL: NVIDIA_API_KEY is missing. Set NVIDIA_API_KEY, LLM_BASE_URL, "
                "and LLM_MODEL in .env."
            )

        base_url = _normalize_llm_base_url(
            os.getenv("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/").strip()
        )
        self.model = os.getenv("LLM_MODEL", "gemini-2.5-flash").strip()
        self.llm = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.mcp_client = mcp_client
        self.max_turns = max_turns

    async def ask(self, user_prompt: str) -> str:
        """Execute an autonomous Reason + Act (ReAct) loop until the LLM produces a final answer."""
        discovered_tools = await self.mcp_client.discover_tools()
        openai_tools = mcp_tools_to_openai_schema(discovered_tools)

        messages: List[Dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "You are an enterprise HR data assistant. Answer user questions accurately using ONLY "
                    "the employee records retrieved from the available MCP database tools. "
                    "Never fabricate employee names, salaries, or IDs. If an employee ID does not exist, "
                    "state that clearly based on the tool error response."
                ),
            },
            {"role": "user", "content": user_prompt},
        ]

        for turn in range(1, self.max_turns + 1):
            logger.info(f"Agent reasoning turn {turn}/{self.max_turns} using model '{self.model}'...")
            response = await self.llm.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=openai_tools,
                tool_choice="auto",
                temperature=0.0,
            )

            assistant_msg = response.choices[0].message
            messages.append(assistant_msg.model_dump(exclude_none=True))

            # If the LLM did not request any tool calls, it has reached the final answer
            if not assistant_msg.tool_calls:
                return assistant_msg.content or "No response generated."

            # Execute every requested MCP tool call and feed results back into conversation history
            for tool_call in assistant_msg.tool_calls:
                fn_name = tool_call.function.name
                raw_args = tool_call.function.arguments or "{}"
                parsed_args = json.loads(raw_args)

                logger.info(f"Agent selected MCP tool -> {fn_name}({parsed_args})")
                tool_result = await self.mcp_client.execute_tool(fn_name, parsed_args)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result),
                    }
                )

        return "Agent reached maximum reasoning turns without a final answer."


async def main() -> None:
    """Demonstrate autonomous multi-query reasoning over the Neon PostgreSQL MCP server."""
    client = PostgresMCPClient()
    try:
        await client.connect()
        agent = EmployeeDatabaseAgent(mcp_client=client)

        queries = [
            "List all employees in the Engineering department and calculate their average salary.",
            "Give me the full profile of employee ID 2, and also check if employee ID 999 exists.",
        ]

        for idx, query in enumerate(queries, start=1):
            print(f"\n==================== Query {idx} ====================")
            print(f"User : {query}\n")
            answer = await agent.ask(query)
            print(f"Agent:\n{answer}")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())