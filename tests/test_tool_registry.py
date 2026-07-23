from pathlib import Path

from agentic.tool_registry import MCPServerDefinition, ToolPermission, ToolRegistry


def make_registry(tmp_path: Path) -> ToolRegistry:
    return ToolRegistry(tmp_path / "data", tmp_path)


def test_raw_terminal_is_blocked(tmp_path):
    terminal = next(item for item in make_registry(tmp_path).tools() if item["id"] == "terminal.raw")
    assert terminal["permission"] == ToolPermission.BLOCKED
    assert terminal["enabled"] is False


def test_server_registration_defaults_disabled(tmp_path):
    registry = make_registry(tmp_path)
    item = registry.add_server(MCPServerDefinition("github-mcp", "GitHub MCP", "https", "https://example.com/mcp", False, ToolPermission.READ))
    assert item["enabled"] is False
    assert registry.servers()[0]["id"] == "github-mcp"


def test_read_and_blocked_tools(tmp_path):
    registry = make_registry(tmp_path)
    assert registry.invoke("aios.health", {})["status"] == "completed"
    assert registry.invoke("terminal.raw", {})["status"] == "blocked"
