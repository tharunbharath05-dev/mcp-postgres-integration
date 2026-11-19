import json
from server.mcp_server import get_all_employees, get_employee_by_id
from server.logger import get_logger

logger = get_logger("mcp.tests.server")


def run_verification_suite() -> None:
    logger.info("Starting MCP Server tool verification suite...")

    # 1. Test get_all_employees
    all_raw = get_all_employees()
    all_res = json.loads(all_raw)
    assert all_res["status"] == "success", f"Expected success, got {all_res}"
    assert len(all_res["data"]) >= 5, "Expected at least 5 seeded employees"
    logger.info(f"PASS: get_all_employees returned {all_res['count']} records.")

    # 2. Test valid employee ID
    emp_raw = get_employee_by_id(employee_id=2)
    emp_res = json.loads(emp_raw)
    assert emp_res["status"] == "success", f"Expected success, got {emp_res}"
    assert emp_res["data"]["id"] == 2
    logger.info(f"PASS: get_employee_by_id(2) returned {emp_res['data']['first_name']}.")

    # 3. Test non-existent employee ID
    missing_raw = get_employee_by_id(employee_id=9999)
    missing_res = json.loads(missing_raw)
    assert missing_res["status"] == "error", f"Expected error envelope, got {missing_res}"
    assert "does not exist" in missing_res["message"]
    logger.info(f"PASS: Non-existent ID handled cleanly -> {missing_res['message']}")

    # 4. Test negative employee ID
    invalid_raw = get_employee_by_id(employee_id=-1)
    invalid_res = json.loads(invalid_raw)
    assert invalid_res["status"] == "error", f"Expected error envelope, got {invalid_res}"
    logger.info(f"PASS: Negative ID handled cleanly -> {invalid_res['message']}")

    logger.info("All Day 4 server verification checks passed!")


if __name__ == "__main__":
    run_verification_suite()