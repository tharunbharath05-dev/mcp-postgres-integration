import asyncio
from client.mcp_client import PostgresMCPClient, logger


async def run_e2e_tests() -> None:
    client = PostgresMCPClient()
    try:
        await client.connect()

        tools = await client.discover_tools()
        tool_names = {t["name"] for t in tools}
        assert tool_names == {"get_all_employees", "get_employee_by_id"}, f"Unexpected tools: {tool_names}"

        all_res = await client.execute_tool("get_all_employees")
        assert all_res["status"] == "success"
        assert all_res["count"] >= 5

        valid_res = await client.execute_tool("get_employee_by_id", {"employee_id": 2})
        assert valid_res["status"] == "success"
        assert valid_res["data"]["first_name"] == "Priya"

        missing_res = await client.execute_tool("get_employee_by_id", {"employee_id": 9999})
        assert missing_res["status"] == "error"

        schema_err_res = await client.execute_tool("get_employee_by_id", {"employee_id": -1})
        assert schema_err_res["status"] == "error"
        assert schema_err_res["source"] == "mcp_validation"

        logger.info("All Day 7 end-to-end MCP client-server tests passed!")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(run_e2e_tests())