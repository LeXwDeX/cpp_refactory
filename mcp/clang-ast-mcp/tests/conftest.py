"""pytest fixtures for test_local.py and test_mcp_protocol.py.

Both files were written as standalone scripts (python tests/test_*.py).
This conftest.py bridges them into pytest by providing the `eng` and
`client` session-scoped fixtures, and by patching each module's
assert_true() so that failures surface as pytest FAILED (not just ✗ prints).
"""
from __future__ import annotations

import importlib
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
FIXTURES = HERE / "fixtures"
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
SERVER_MODULE = "clang_ast_mcp.server"

sys.path.insert(0, str(PROJECT_ROOT / "src"))


# ---------------------------------------------------------------------------
# Helper: make assert_true in a module raise AssertionError on failure
# so pytest can report them as FAILED (not just silent ✗ prints).
# ---------------------------------------------------------------------------
def _patch_assert_true(module):
    """Replace module.assert_true with a version that raises on failure."""
    original = module.assert_true

    def strict_assert_true(cond: bool, msg: str) -> None:
        original(cond, msg)  # keep the ✓/✗ print
        if not cond:
            raise AssertionError(f"FAILED: {msg}")

    module.assert_true = strict_assert_true


# ---------------------------------------------------------------------------
# eng fixture — used by test_local.py
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def eng():
    """Return a shared AstEngine instance for the module."""
    # Import here so path insertion above is already in effect
    from clang_ast_mcp.ast_engine import get_engine  # noqa: WPS433

    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location("test_local", HERE / "test_local.py")
    _tl = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_tl)  # type: ignore[union-attr]
    _patch_assert_true(_tl)

    engine = get_engine()
    yield engine
    # AstEngine has no explicit close; just drop the reference.


# ---------------------------------------------------------------------------
# client fixture — used by test_mcp_protocol.py
# ---------------------------------------------------------------------------
class _MCPClientWrapper:
    """Thin wrapper around the MCPClient defined in test_mcp_protocol."""

    def __init__(self, proc: subprocess.Popen):
        self._proc = proc
        self._id = 0

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def send(self, method: str, params=None) -> dict:
        import json
        msg_id = self._next_id()
        payload: dict = {"jsonrpc": "2.0", "id": msg_id, "method": method}
        if params is not None:
            payload["params"] = params
        line = json.dumps(payload, separators=(",", ":")) + "\n"
        self._proc.stdin.write(line.encode("utf-8"))
        self._proc.stdin.flush()
        return self._read_response()

    def send_notification(self, method: str, params=None) -> None:
        import json
        payload: dict = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        line = json.dumps(payload, separators=(",", ":")) + "\n"
        self._proc.stdin.write(line.encode("utf-8"))
        self._proc.stdin.flush()

    def _read_response(self) -> dict:
        import json
        while True:
            line = self._proc.stdout.readline()
            if not line:
                raise EOFError("Server closed stdout")
            line = line.decode("utf-8").strip()
            if not line:
                continue
            return json.loads(line)

    def close(self):
        try:
            self._proc.stdin.close()
        except Exception:
            pass
        try:
            self._proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._proc.kill()


@pytest.fixture(scope="module")
def client():
    """Start MCP server subprocess and return a client; teardown on module end."""
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location("test_mcp_protocol", HERE / "test_mcp_protocol.py")
    _tp = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_tp)  # type: ignore[union-attr]
    _patch_assert_true(_tp)

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
    # Give the server a moment to start
    time.sleep(0.5)

    wrapper = _MCPClientWrapper(proc)
    yield wrapper
    wrapper.close()
