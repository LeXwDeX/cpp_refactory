"""End-to-end refactoring task test — validates the full analysis pipeline
against the legacy_monster.cpp fixture.

This test simulates what an AI agent would do:
  1. Load a legacy C++ file via MCP
  2. Run all analyzers to identify problems
  3. Generate a refactoring report
  4. Validate the report contains actionable findings

This is the ultimate integration test — if this passes, the MCP system
is ready to drive real C++ refactoring tasks.

Run:
    .venv/bin/python tests/test_e2e_refactor.py
"""
from __future__ import annotations

import importlib
import json
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

# Clear cached modules
for _name in list(sys.modules):
    if _name.startswith("clang_ast_mcp"):
        del sys.modules[_name]
importlib.invalidate_caches()

from clang_ast_mcp.ast_engine import get_engine
from clang_ast_mcp.refactor_report import (
    generate_report,
    RefactorThresholds,
)


LEGACY = HERE / "fixtures" / "legacy_monster.cpp"
DB = HERE / "fixtures" / "compile_commands.json"


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


def section(title: str) -> None:
    print(_color(f"\n=== {title} ===", "1;36"))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_report_generation():
    """Test that generate_report produces a complete assessment."""
    section("E2E: Report Generation")

    t0 = time.perf_counter()
    report = generate_report(str(LEGACY), str(DB))
    t_total = time.perf_counter() - t0

    print(f"  Report generated in {t_total*1000:.1f}ms")
    print(f"  File: {Path(report.file).name}")
    print(f"  Lines: {report.total_lines}")
    print(f"  Functions: {report.total_functions}")
    print(f"  Globals: {report.total_globals}")
    print(f"  Virtual calls: {report.total_virtual_calls}")
    print(f"  Overall risk: {report.overall_risk}")
    print(f"  Maintainability: {report.maintainability_index:.1f}/100")

    # Basic completeness
    assert_true(report.total_lines > 300, f"file has > 300 lines (got {report.total_lines})")
    assert_true(report.total_functions >= 15, f"found >= 15 functions (got {report.total_functions})")
    assert_true(report.total_globals >= 5, f"found >= 5 globals (got {report.total_globals})")
    assert_true(report.total_virtual_calls >= 3, f"found >= 3 virtual calls (got {report.total_virtual_calls})")


def test_god_functions_detected():
    """Test that ProcessLegacyRequest and InitializeSubsystem are flagged."""
    section("E2E: God Function Detection")

    report = generate_report(str(LEGACY), str(DB))

    god_names = {gf.name for gf in report.god_functions}
    print(f"  God functions found: {sorted(god_names)}")

    assert_true(
        "ProcessLegacyRequest" in god_names,
        "ProcessLegacyRequest detected as god function",
    )
    assert_true(
        "InitializeSubsystem" in god_names,
        "InitializeSubsystem detected as god function",
    )
    assert_true(
        len(report.god_functions) >= 2,
        f"at least 2 god functions (got {len(report.god_functions)})",
    )

    # Verify ProcessLegacyRequest has high complexity
    plr = next((gf for gf in report.god_functions if gf.name == "ProcessLegacyRequest"), None)
    if plr:
        print(f"  ProcessLegacyRequest: {plr.line_count} lines, CC={plr.cyclomatic_complexity}")
        assert_true(
            plr.line_count >= 80,
            f"ProcessLegacyRequest is long (got {plr.line_count} lines)",
        )
        assert_true(
            plr.cyclomatic_complexity >= 15,
            f"ProcessLegacyRequest is complex (CC={plr.cyclomatic_complexity})",
        )
        assert_true(
            plr.risk_score >= 2.0,
            f"ProcessLegacyRequest has high risk (score={plr.risk_score:.2f})",
        )


def test_dangerous_globals_detected():
    """Test that SIOF-risk globals are identified."""
    section("E2E: Dangerous Globals Detection")

    report = generate_report(str(LEGACY), str(DB))

    print(f"  Dangerous globals found: {len(report.dangerous_globals)}")
    for dg in report.dangerous_globals[:10]:
        print(f"    L{dg.line:>3} [{dg.risk_level:<8}] {dg.kind:<14} {dg.name}")

    assert_true(
        len(report.dangerous_globals) >= 2,
        f"at least 2 dangerous globals (got {len(report.dangerous_globals)})",
    )

    # g_log_prefix should be flagged (file_static with dynamic init)
    names = {dg.name for dg in report.dangerous_globals}
    assert_true(
        "g_log_prefix" in names or "g_error_history" in names,
        "dynamic-init globals flagged (g_log_prefix or g_error_history)",
    )

    # Check risk levels
    risk_levels = {dg.risk_level for dg in report.dangerous_globals}
    assert_true(
        "high" in risk_levels or "critical" in risk_levels,
        f"at least one high/critical risk global (got {sorted(risk_levels)})",
    )


def test_virtual_dispatch_hotspots():
    """Test detection of functions with heavy virtual dispatch."""
    section("E2E: Virtual Dispatch Hotspots")

    # Use lower threshold for the test
    thresholds = RefactorThresholds(virtual_call_threshold=2)
    report = generate_report(str(LEGACY), str(DB), thresholds=thresholds)

    print(f"  Virtual dispatch hotspots: {len(report.virtual_hotspots)}")
    for vh in report.virtual_hotspots:
        print(f"    {vh.caller}: {vh.call_count} calls, {vh.override_complexity} overrides")

    assert_true(
        len(report.virtual_hotspots) >= 1,
        f"at least 1 virtual dispatch hotspot (got {len(report.virtual_hotspots)})",
    )

    # ProcessLegacyRequest has multiple virtual calls
    plr_hotspot = next(
        (vh for vh in report.virtual_hotspots if vh.caller == "ProcessLegacyRequest"),
        None,
    )
    if plr_hotspot:
        assert_true(
            plr_hotspot.call_count >= 3,
            f"ProcessLegacyRequest has >= 3 virtual calls (got {plr_hotspot.call_count})",
        )


def test_macro_jungle_detected():
    """Test that #ifdef-heavy functions are identified."""
    section("E2E: Macro Jungle Detection")

    report = generate_report(str(LEGACY), str(DB))

    print(f"  Macro jungle targets: {len(report.macro_jungle_targets)}")
    for mj in report.macro_jungle_targets[:5]:
        print(
            f"    {mj.name}: score={mj.complexity_score}, "
            f"branches={mj.branch_count}, macros={len(mj.macros_used)}"
        )

    assert_true(
        len(report.macro_jungle_targets) >= 1,
        f"at least 1 macro jungle target (got {len(report.macro_jungle_targets)})",
    )

    # ProcessLegacyRequest should be top offender
    plr = next(
        (mj for mj in report.macro_jungle_targets if mj.name == "ProcessLegacyRequest"),
        None,
    )
    assert_true(plr is not None, "ProcessLegacyRequest in macro jungle targets")
    if plr:
        assert_true(
            plr.branch_count >= 4,
            f"ProcessLegacyRequest has >= 4 #ifdef branches (got {plr.branch_count})",
        )


def test_recommendations_generated():
    """Test that actionable recommendations are produced."""
    section("E2E: Recommendations")

    report = generate_report(str(LEGACY), str(DB))

    print(f"  Total recommendations: {len(report.recommendations)}")
    for rec in report.recommendations[:5]:
        print(f"    P{rec.priority} [{rec.category}] {rec.target} (L{rec.line})")

    assert_true(
        len(report.recommendations) >= 5,
        f"at least 5 recommendations (got {len(report.recommendations)})",
    )

    # Should have recommendations across multiple categories
    categories = {rec.category for rec in report.recommendations}
    print(f"  Categories: {sorted(categories)}")
    assert_true(
        len(categories) >= 3,
        f"recommendations span >= 3 categories (got {sorted(categories)})",
    )

    # Should have at least one P1 (critical) recommendation
    priorities = {rec.priority for rec in report.recommendations}
    assert_true(
        1 in priorities or 2 in priorities,
        f"has P1 or P2 recommendations (got priorities {sorted(priorities)})",
    )


def test_overall_risk_assessment():
    """Test that overall risk is correctly assessed for this monster file."""
    section("E2E: Overall Risk Assessment")

    report = generate_report(str(LEGACY), str(DB))

    print(f"  Overall risk: {report.overall_risk}")
    print(f"  Maintainability index: {report.maintainability_index:.1f}/100")

    # This file is bad — should be medium or higher
    assert_true(
        report.overall_risk in ("medium", "high", "critical"),
        f"overall risk is medium+ (got {report.overall_risk})",
    )

    # Maintainability should be below 80 (it's a mess)
    assert_true(
        report.maintainability_index < 80,
        f"maintainability < 80 (got {report.maintainability_index:.1f})",
    )


def test_report_serialization():
    """Test that report can be serialized to JSON (for MCP tool output)."""
    section("E2E: Report Serialization")

    report = generate_report(str(LEGACY), str(DB))

    # to_dict should not raise
    data = report.to_dict()
    assert_true(isinstance(data, dict), "to_dict returns dict")

    # Should be JSON-serializable
    json_str = json.dumps(data, indent=2, default=str)
    assert_true(len(json_str) > 1000, f"JSON output is substantial ({len(json_str)} chars)")

    # Round-trip
    parsed = json.loads(json_str)
    assert_true(parsed["file"] == report.file, "round-trip preserves file path")
    assert_true(
        len(parsed["recommendations"]) == len(report.recommendations),
        "round-trip preserves recommendation count",
    )


def test_summary_output():
    """Test human-readable summary."""
    section("E2E: Summary Output")

    report = generate_report(str(LEGACY), str(DB))
    summary = report.summary()

    print(f"\n{summary}\n")

    assert_true(len(summary) > 200, f"summary is substantial ({len(summary)} chars)")
    assert_true("ProcessLegacyRequest" in summary, "summary mentions ProcessLegacyRequest")
    assert_true("God functions" in summary or "god_function" in summary, "summary mentions god functions")


def test_performance():
    """Test that the full pipeline runs within acceptable time."""
    section("E2E: Performance")

    # Warm up
    generate_report(str(LEGACY), str(DB))

    # Timed run (should hit cache)
    t0 = time.perf_counter()
    report = generate_report(str(LEGACY), str(DB))
    t_warm = time.perf_counter() - t0

    print(f"  Warm pipeline: {t_warm*1000:.1f}ms")
    assert_true(
        t_warm < 5.0,
        f"full pipeline < 5s (got {t_warm*1000:.1f}ms)",
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print(_color("\n╔══════════════════════════════════════╗", "1;35"))
    print(_color("║  E2E Refactoring Task Test           ║", "1;35"))
    print(_color("╚══════════════════════════════════════╝", "1;35"))

    test_report_generation()
    test_god_functions_detected()
    test_dangerous_globals_detected()
    test_virtual_dispatch_hotspots()
    test_macro_jungle_detected()
    test_recommendations_generated()
    test_overall_risk_assessment()
    test_report_serialization()
    test_summary_output()
    test_performance()

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
