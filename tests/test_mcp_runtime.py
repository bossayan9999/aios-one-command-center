from agentic.connector_policies import ToolRisk
from agentic.mcp_runtime import MCPRuntime


def test_read_only_tool_allowed():
    runtime = MCPRuntime()
    connector = {"connector_id": "x", "enabled": True, "read_only": True}
    decision = runtime.authorize_tool(connector, risk=ToolRisk.READ_ONLY)
    assert decision.allowed is True


def test_write_blocked_in_read_only_mode():
    runtime = MCPRuntime()
    connector = {"connector_id": "x", "enabled": True, "read_only": True}
    decision = runtime.authorize_tool(connector, risk=ToolRisk.WRITE_PROTECTED, exact_payload_approved=True)
    assert decision.allowed is False


def test_tool_selection_is_limited():
    runtime = MCPRuntime()
    connector = {"allowed_tools": ["a", "b", "c"]}
    selected = runtime.select_tools(
        connector,
        [{"name": "a"}, {"name": "b"}, {"name": "x"}, {"name": "c"}],
        max_tools=2,
    )
    assert [item["name"] for item in selected] == ["a", "b"]
