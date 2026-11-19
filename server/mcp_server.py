import json
from typing import Annotated
from pydantic import Field
from mcp.server.mcpserver import MCPServer

from server.db import fetch_all_employees, fetch_employee_by_id
from server.logger import get_logger

logger = get_logger("mcp.server.protocol")

# Initialize the MCP v2 server instance
mcp = MCPServer(
    name="postgres-employee-service",
    instructions=(
        "Enterprise HR database service providing read-only access to employee records. "
        "Use get_all_employees to list the directory or get_employee_by_id for a specific person."
    ),
)


@mcp.tool()
def get_all_employees() -> str:
    """
    Retrieve all employee records from the PostgreSQL database.

    Use this tool when the user asks to list, count, filter, or summarize
    all employees across the company or within a specific department.

    Returns:
        A JSON-formatted string containing status, record count, and a list
        of employee objects (id, first_name, last_name, email, department, role, salary, hire_date).
    """
    logger.info("Tool invoked: get_all_employees()")
    result = fetch_all_employees()
    return json.dumps(result, indent=2)


@mcp.tool()
def get_employee_by_id(
    employee_id: Annotated[
        int,
        Field(
            gt=0,
            description="The unique positive integer primary key ID of the employee (e.g., 1, 2, 3).",
        ),
    ],
) -> str:
    """
    Retrieve detailed profile information for a single employee using their unique employee ID.

    Use this tool when the user asks about a specific employee by their numeric ID.

    Args:
        employee_id: Positive integer ID of the employee to look up.

    Returns:
        A JSON-formatted string containing status and the employee record,
        or a structured error message if the ID does not exist or is invalid.
    """
    logger.info(f"Tool invoked: get_employee_by_id(employee_id={employee_id})")
    result = fetch_employee_by_id(employee_id=employee_id)
    return json.dumps(result, indent=2)


def main() -> None:
    """Entry point for running the MCP server over stdio transport."""
    logger.info("Starting postgres-employee-service MCP server on stdio transport...")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()