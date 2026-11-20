import json
from pathlib import Path
from server.logger import get_logger

logger = get_logger("mcp.tests.config")


def validate_mcp_config(file_path: Path, check_live_db_url: bool = False) -> None:
    assert file_path.exists(), f"Configuration file missing: {file_path}"

    with file_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    assert "mcpServers" in data and isinstance(data["mcpServers"], dict), (
        f"{file_path}: Top-level 'mcpServers' object is required."
    )
    assert "postgres-employee-service" in data["mcpServers"], (
        f"{file_path}: Missing 'postgres-employee-service' entry."
    )

    server_cfg = data["mcpServers"]["postgres-employee-service"]
    assert isinstance(server_cfg.get("command"), str) and server_cfg["command"], (
        f"{file_path}: 'command' must be a non-empty string."
    )
    assert isinstance(server_cfg.get("args"), list) and len(server_cfg["args"]) > 0, (
        f"{file_path}: 'args' must be a non-empty list of strings."
    )
    assert isinstance(server_cfg.get("env"), dict), (
        f"{file_path}: 'env' must be a dictionary."
    )

    db_url = server_cfg["env"].get("DATABASE_URL", "")
    assert db_url.startswith("postgresql://"), (
        f"{file_path}: 'DATABASE_URL' must start with 'postgresql://'."
    )
    if check_live_db_url:
        assert "user:password@host" not in db_url, (
            f"{file_path}: Replace placeholder credentials with your real Neon DATABASE_URL."
        )

    logger.info(f"PASS: {file_path.name} validated successfully.")


if __name__ == "__main__":
    validate_mcp_config(Path("mcp_config.example.json"), check_live_db_url=False)
    validate_mcp_config(Path("mcp_config.json"), check_live_db_url=True)
    logger.info("All Day 5 JSON configuration checks passed!")