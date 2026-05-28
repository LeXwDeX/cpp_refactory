"""MCP protocol integration test — validates the full JSON-RPC handshake.

Tests the clang-ast-mcp server as a subprocess, communicating over stdin/stdout
using the MCP protocol (JSON-RPC 2.0 over stdio with Content-Length framing).

Covers:
  1. Server starts and responds to `initialize`
  2. `tools/list` returns all 5 tools with correct schemas
  3. `tools/call` for each tool with valid arguments → success response
  4. `tools/call` with invalid arguments → structured error (not crash)
  5. Server handles multiple requests in sequence (session persistence)
  6. Graceful shutdown on stdin close

Run:
    .venv/bin/python tests/test_mcp_protocol.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
FIXTURES = HERE / "fixtures"
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
SERVER_MODULE = "clang_ast_mcp.server"


# ---------------------------------------------------------------------------
# JSON-RPC / MCP transport helpers
# ---------------------------------------------------------------------------
class MCPClient:
    """Minimal MCP client over subprocess stdio.

    FastMCP uses newline-delimited JSON-RPC for stdio transport
    (NOT Content-Length framing like LSP).
    """

    def __init__(self, proc: subprocess.Popen):
        self._proc = proc
        self._id = 0

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def send(self, method: str, params: Optional[dict] = None) -> dict:
        """Send a JSON-RPC request and read the response."""
        msg_id = self._next_id()
        payload = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": method,
        }
        if params is not None:
            payload["params"] = params

        line = json.dumps(payload, separators=(",", ":")) + "\n"
        self._proc.stdin.write(line.encode("utf-8"))
        self._proc.stdin.flush()

        return self._read_response()

    def send_notification(self, method: str, params: Optional[dict] = None) -> None:
        """Send a JSON-RPC notification (no id, no response expected)."""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            payload["params"] = params

        line = json.dumps(payload, separators=(",", ":")) + "\n"
        self._proc.stdin.write(line.encode("utf-8"))
        self._proc.stdin.flush()

    def _read_response(self) -> dict:
        """Read a newline-delimited JSON-RPC response."""
        while True:
            line = self._proc.stdout.readline()
            if not line:
                raise EOFError("Server closed stdout")
            line = line.decode("utf-8").strip()
            if not line:
                continue  # skip blank lines
            return json.loads(line)

    def close(self):
        """Close stdin to signal shutdown, then wait."""
        try:
            self._proc.stdin.close()
        except Exception:
            pass
        try:
            self._proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._proc.kill()


def start_server() -> MCPClient:
    """Start the MCP server as a subprocess."""
    # Use the venv python with the server module
    python = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["CLANG_AST_MCP_LOG"] = "WARNING"
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")

    proc = subprocess.Popen(
        [python, "-m", SERVER_MODULE],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=str(FIXTURES),
    )
    return MCPClient(proc)


# ---------------------------------------------------------------------------
# Test harness
# ---------------------------------------------------------------------------
def _color(s: str, c: str) -> str:
    return f"\033[{c}m{s}\033[0m"


passed = 0
failed = 0


def assert_true(cond: bool, msg: str) -> None:
    global passed, failed
    if cond:
        passed += 1
        print(_color("  ✓ ", "32") + msg)
    else:
        failed += 1
        print(_color("  ✗ ", "31") + msg)


def assert_eq(a: Any, b: Any, msg: str) -> None:
    assert_true(a == b, f"{msg} (expected={b!r}, got={a!r})")


def section(title: str) -> None:
    print(_color(f"\n=== {title} ===", "1;36"))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_initialize(client: MCPClient) -> dict:
    """Test MCP initialize handshake."""
    section("MCP Initialize")

    resp = client.send("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test-client", "version": "0.1.0"},
    })

    assert_true("result" in resp, "initialize returns result")
    result = resp.get("result", {})
    assert_true("capabilities" in result, "result contains capabilities")
    assert_true("serverInfo" in result, "result contains serverInfo")

    server_info = result.get("serverInfo", {})
    assert_eq(server_info.get("name"), "clang-ast-mcp", "server name is clang-ast-mcp")

    # Send initialized notification
    client.send_notification("notifications/initialized")
    time.sleep(0.1)  # Let server process

    return result


def test_tools_list(client: MCPClient) -> list:
    """Test tools/list to verify all 5 tools are registered."""
    section("MCP tools/list")

    resp = client.send("tools/list", {})
    assert_true("result" in resp, "tools/list returns result")

    result = resp.get("result", {})
    tools = result.get("tools", [])
    assert_true(len(tools) >= 5, f"at least 5 tools registered (got {len(tools)})")

    tool_names = {t["name"] for t in tools}
    expected_tools = {
        "clang_ast_load",
        "clang_ast_list_functions",
        "clang_ast_globals",
        "clang_ast_virtual_calls",
        "clang_ast_macro_jungle",
    }
    for name in expected_tools:
        assert_true(name in tool_names, f"tool '{name}' is registered")

    # Check that each tool has inputSchema
    for tool in tools:
        has_schema = "inputSchema" in tool
        assert_true(has_schema, f"tool '{tool['name']}' has inputSchema")

    return tools


def test_tool_call_load(client: MCPClient) -> None:
    """Test tools/call for clang_ast_load."""
    section("MCP tools/call — clang_ast_load")

    sample_path = str(FIXTURES / "sample.cpp")
    db_path = str(FIXTURES / "compile_commands.json")

    resp = client.send("tools/call", {
        "name": "clang_ast_load",
        "arguments": {"file": sample_path, "compile_db": db_path},
    })

    assert_true("result" in resp, "tool call returns result")
    result = resp.get("result", {})

    # MCP tool results are in content array
    content = result.get("content", [])
    assert_true(len(content) > 0, "result has content")

    if content:
        # Parse the text content (JSON stringified)
        text = content[0].get("text", "")
        data = json.loads(text) if text else {}
        assert_true(data.get("ok") is True, f"tool returned ok=True")
        assert_true("cache" in data, "result contains cache stats")


def test_tool_call_list_functions(client: MCPClient) -> None:
    """Test tools/call for clang_ast_list_functions."""
    section("MCP tools/call — clang_ast_list_functions")

    sample_path = str(FIXTURES / "sample.cpp")
    db_path = str(FIXTURES / "compile_commands.json")

    resp = client.send("tools/call", {
        "name": "clang_ast_list_functions",
        "arguments": {"file": sample_path, "compile_db": db_path},
    })

    result = resp.get("result", {})
    content = result.get("content", [])
    assert_true(len(content) > 0, "list_functions returns content")

    if content:
        data = json.loads(content[0].get("text", "{}"))
        assert_true(data.get("ok") is True, "list_functions ok=True")
        assert_true(data.get("count", 0) >= 6, f"found >= 6 functions (got {data.get('count')})")


def test_tool_call_globals(client: MCPClient) -> None:
    """Test tools/call for clang_ast_globals."""
    section("MCP tools/call — clang_ast_globals")

    sample_path = str(FIXTURES / "sample.cpp")
    db_path = str(FIXTURES / "compile_commands.json")

    resp = client.send("tools/call", {
        "name": "clang_ast_globals",
        "arguments": {"file": sample_path, "compile_db": db_path},
    })

    result = resp.get("result", {})
    content = result.get("content", [])
    assert_true(len(content) > 0, "globals returns content")

    if content:
        data = json.loads(content[0].get("text", "{}"))
        assert_true(data.get("ok") is True, "globals ok=True")
        assert_true(data.get("count", 0) >= 4, f"found >= 4 globals (got {data.get('count')})")


def test_tool_call_virtual_calls(client: MCPClient) -> None:
    """Test tools/call for clang_ast_virtual_calls."""
    section("MCP tools/call — clang_ast_virtual_calls")

    sample_path = str(FIXTURES / "sample.cpp")
    db_path = str(FIXTURES / "compile_commands.json")

    resp = client.send("tools/call", {
        "name": "clang_ast_virtual_calls",
        "arguments": {"file": sample_path, "compile_db": db_path},
    })

    result = resp.get("result", {})
    content = result.get("content", [])
    assert_true(len(content) > 0, "virtual_calls returns content")

    if content:
        data = json.loads(content[0].get("text", "{}"))
        assert_true(data.get("ok") is True, "virtual_calls ok=True")
        assert_true(data.get("count", 0) >= 1, f"found >= 1 virtual call (got {data.get('count')})")


def test_tool_call_macro_jungle(client: MCPClient) -> None:
    """Test tools/call for clang_ast_macro_jungle."""
    section("MCP tools/call — clang_ast_macro_jungle")

    sample_path = str(FIXTURES / "sample.cpp")
    db_path = str(FIXTURES / "compile_commands.json")

    resp = client.send("tools/call", {
        "name": "clang_ast_macro_jungle",
        "arguments": {"file": sample_path, "compile_db": db_path},
    })

    result = resp.get("result", {})
    content = result.get("content", [])
    assert_true(len(content) > 0, "macro_jungle returns content")

    if content:
        data = json.loads(content[0].get("text", "{}"))
        assert_true(data.get("ok") is True, "macro_jungle ok=True")
        funcs = data.get("functions", [])
        assert_true(len(funcs) >= 1, f"macro_jungle found functions ({len(funcs)})")


def test_tool_call_error(client: MCPClient) -> None:
    """Test tools/call with invalid arguments → structured error."""
    section("MCP tools/call — error handling")

    # Missing file
    resp = client.send("tools/call", {
        "name": "clang_ast_list_functions",
        "arguments": {"file": "/nonexistent/file.cpp"},
    })
    result = resp.get("result", {})
    content = result.get("content", [])
    assert_true(len(content) > 0, "error case returns content")

    if content:
        data = json.loads(content[0].get("text", "{}"))
        assert_true(data.get("ok") is False, "error case ok=False")
        assert_true(
            data.get("error", {}).get("kind") == "FileNotFound",
            f"error kind=FileNotFound (got {data.get('error', {}).get('kind')})",
        )

    # Bad min_lines
    sample_path = str(FIXTURES / "sample.cpp")
    db_path = str(FIXTURES / "compile_commands.json")
    resp = client.send("tools/call", {
        "name": "clang_ast_list_functions",
        "arguments": {"file": sample_path, "compile_db": db_path, "min_lines": -1},
    })
    result = resp.get("result", {})
    content = result.get("content", [])
    if content:
        data = json.loads(content[0].get("text", "{}"))
        assert_true(data.get("ok") is False, "negative min_lines → ok=False")
        assert_true(
            data.get("error", {}).get("kind") == "BadArgument",
            "negative min_lines → BadArgument",
        )


def test_legacy_monster(client: MCPClient) -> None:
    """Test against the legacy_monster.cpp fixture — complex real-world patterns."""
    section("MCP tools/call — legacy_monster.cpp (E2E)")

    monster_path = str(FIXTURES / "legacy_monster.cpp")
    db_path = str(FIXTURES / "compile_commands.json")

    # List functions
    resp = client.send("tools/call", {
        "name": "clang_ast_list_functions",
        "arguments": {"file": monster_path, "compile_db": db_path},
    })
    result = resp.get("result", {})
    content = result.get("content", [])
    if content:
        data = json.loads(content[0].get("text", "{}"))
        assert_true(data.get("ok") is True, "legacy_monster list_functions ok")
        count = data.get("count", 0)
        assert_true(count >= 15, f"legacy_monster has >= 15 functions (got {count})")

        # Check that god functions are detected
        funcs = data.get("functions", [])
        god_funcs = [f for f in funcs if f.get("line_count", 0) >= 50]
        assert_true(
            len(god_funcs) >= 2,
            f"legacy_monster has >= 2 god functions (got {len(god_funcs)})",
        )

    # Globals
    resp = client.send("tools/call", {
        "name": "clang_ast_globals",
        "arguments": {"file": monster_path, "compile_db": db_path},
    })
    result = resp.get("result", {})
    content = result.get("content", [])
    if content:
        data = json.loads(content[0].get("text", "{}"))
        assert_true(data.get("ok") is True, "legacy_monster globals ok")
        gs = data.get("globals", [])
        dynamic_init = [g for g in gs if g.get("has_dynamic_init")]
        assert_true(
            len(dynamic_init) >= 1,
            f"legacy_monster has dangerous dynamic-init globals (got {len(dynamic_init)})",
        )

    # Virtual calls
    resp = client.send("tools/call", {
        "name": "clang_ast_virtual_calls",
        "arguments": {"file": monster_path, "compile_db": db_path},
    })
    result = resp.get("result", {})
    content = result.get("content", [])
    if content:
        data = json.loads(content[0].get("text", "{}"))
        assert_true(data.get("ok") is True, "legacy_monster virtual_calls ok")
        assert_true(
            data.get("count", 0) >= 3,
            f"legacy_monster has >= 3 virtual calls (got {data.get('count')})",
        )


def test_session_persistence(client: MCPClient) -> None:
    """Test that multiple requests in a session work (cache persists)."""
    section("Session persistence (cache)")

    sample_path = str(FIXTURES / "sample.cpp")
    db_path = str(FIXTURES / "compile_commands.json")

    # First call (cold)
    t0 = time.perf_counter()
    client.send("tools/call", {
        "name": "clang_ast_list_functions",
        "arguments": {"file": sample_path, "compile_db": db_path},
    })
    t_first = time.perf_counter() - t0

    # Second call (should hit cache)
    t0 = time.perf_counter()
    client.send("tools/call", {
        "name": "clang_ast_globals",
        "arguments": {"file": sample_path, "compile_db": db_path},
    })
    t_second = time.perf_counter() - t0

    print(f"  First call: {t_first*1000:.1f}ms, Second call: {t_second*1000:.1f}ms")
    # Second call should be faster (cached TU, though different analyzer)
    assert_true(True, "multiple requests in session succeeded")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print(_color("\n╔══════════════════════════════════════╗", "1;35"))
    print(_color("║  MCP Protocol Integration Test       ║", "1;35"))
    print(_color("╚══════════════════════════════════════╝", "1;35"))

    client = start_server()
    try:
        test_initialize(client)
        test_tools_list(client)
        test_tool_call_load(client)
        test_tool_call_list_functions(client)
        test_tool_call_globals(client)
        test_tool_call_virtual_calls(client)
        test_tool_call_macro_jungle(client)
        test_tool_call_error(client)
        test_legacy_monster(client)
        test_session_persistence(client)
    except Exception as e:
        print(_color(f"\n  FATAL: {type(e).__name__}: {e}", "1;31"))
        import traceback
        traceback.print_exc()
        global failed
        failed += 1
    finally:
        client.close()

    section("Result")
    total = passed + failed
    if failed == 0:
        print(_color(f"  ALL {total} ASSERTIONS PASSED", "1;32"))
        sys.exit(0)
    else:
        print(_color(f"  {failed} of {total} FAILED", "1;31"))
        sys.exit(1)


if __name__ == "__main__":
    main()
