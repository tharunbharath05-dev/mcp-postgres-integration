from contextlib import contextmanager
from typing import Any, Dict, Generator
import psycopg2
from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import RealDictCursor

from server.config import settings
from server.logger import get_logger

logger = get_logger("mcp.server.db")


@contextmanager
def get_db_connection() -> Generator[PgConnection, None, None]:
    """Context manager that safely opens and closes a PostgreSQL connection."""
    conn: PgConnection | None = None
    try:
        conn = psycopg2.connect(
            settings.database_url,
            cursor_factory=RealDictCursor,
            connect_timeout=10,
        )
        yield conn
    except psycopg2.OperationalError as e:
        logger.error(f"Database connection failure: {e}")
        raise
    finally:
        if conn is not None and not conn.closed:
            conn.close()


def fetch_all_employees() -> Dict[str, Any]:
    """Retrieve all employee records ordered by ID."""
    query = """
        SELECT id, first_name, last_name, email, department, role,
               salary::float AS salary, hire_date::text AS hire_date
        FROM employees
        ORDER BY id ASC;
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                rows = cur.fetchall()
                records = [dict(row) for row in rows]
                logger.info(f"Fetched {len(records)} employee records.")
                return {"status": "success", "count": len(records), "data": records}
    except psycopg2.Error as e:
        logger.error(f"PostgreSQL query error in fetch_all_employees: {e}")
        return {"status": "error", "message": "Database error occurred while retrieving employees."}
    except Exception as e:
        logger.exception("Unexpected error in fetch_all_employees")
        return {"status": "error", "message": f"Unexpected system error: {str(e)}"}


def fetch_employee_by_id(employee_id: int) -> Dict[str, Any]:
    """Retrieve a single employee record by primary key ID."""
    if isinstance(employee_id, bool) or not isinstance(employee_id, int) or employee_id <= 0:
        logger.warning(f"Rejected invalid employee_id input: {employee_id!r}")
        return {
            "status": "error",
            "message": f"Invalid employee_id '{employee_id}'. Must be a positive integer.",
        }

    query = """
        SELECT id, first_name, last_name, email, department, role,
               salary::float AS salary, hire_date::text AS hire_date
        FROM employees
        WHERE id = %s;
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (employee_id,))
                row = cur.fetchone()
                if not row:
                    logger.info(f"Employee ID {employee_id} not found.")
                    return {
                        "status": "error",
                        "message": f"Employee with ID {employee_id} does not exist.",
                    }
                logger.info(f"Successfully fetched employee ID {employee_id}.")
                return {"status": "success", "data": dict(row)}
    except psycopg2.Error as e:
        logger.error(f"PostgreSQL query error for employee_id={employee_id}: {e}")
        return {"status": "error", "message": "Database error occurred while retrieving employee details."}
    except Exception as e:
        logger.exception(f"Unexpected error for employee_id={employee_id}")
        return {"status": "error", "message": f"Unexpected system error: {str(e)}"}


if __name__ == "__main__":
    logger.info("Running Day 2 data-access verification...")
    all_res = fetch_all_employees()
    logger.info(f"Test 1 (All Employees): status={all_res['status']}, count={all_res.get('count')}")

    valid_res = fetch_employee_by_id(2)
    logger.info(f"Test 2 (Valid ID 2): {valid_res}")

    missing_res = fetch_employee_by_id(999)
    logger.info(f"Test 3 (Missing ID 999): {missing_res}")

    invalid_res = fetch_employee_by_id(-5)
    logger.info(f"Test 4 (Invalid ID -5): {invalid_res}")