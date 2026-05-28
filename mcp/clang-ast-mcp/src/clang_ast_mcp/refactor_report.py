"""Refactoring report generator — aggregates all analyzer outputs into an
actionable report for AI-driven C++ refactoring.

Takes a source file + compile_commands.json, runs all 4 analyzers, then
produces a structured assessment with:
  - God functions (high complexity, high line count)
  - Dangerous globals (SIOF risk, dynamic init)
  - Virtual dispatch hotspots (heavy polymorphism)
  - Macro jungle (preprocessor complexity targets)
  - Priority-ranked refactoring recommendations
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .ast_engine import get_engine
from .analyzers.list_functions import list_functions
from .analyzers.globals_finder import globals_in_file
from .analyzers.virtual_calls import virtual_calls
from .analyzers.macro_jungle import macro_jungle


# ---------------------------------------------------------------------------
# Thresholds (configurable per-project)
# ---------------------------------------------------------------------------
@dataclass
class RefactorThresholds:
    """Thresholds for identifying refactoring targets."""
    god_function_lines: int = 50          # lines to qualify as "too long"
    god_function_complexity: int = 10     # cyclomatic threshold
    dangerous_global_dynamic: bool = True  # flag dynamic-init globals
    macro_jungle_score: int = 6           # preprocessor complexity score
    virtual_call_threshold: int = 3       # calls in single function


# ---------------------------------------------------------------------------
# Report data classes
# ---------------------------------------------------------------------------
@dataclass
class GodFunctionFinding:
    name: str
    qualified_name: str
    start_line: int
    end_line: int
    line_count: int
    cyclomatic_complexity: int
    is_virtual: bool
    risk_score: float = 0.0  # computed


@dataclass
class DangerousGlobalFinding:
    name: str
    qualified_name: str
    kind: str
    type_name: str
    line: int
    has_dynamic_init: bool
    is_const: bool
    risk_level: str = "low"  # low/medium/high/critical


@dataclass
class VirtualDispatchHotspot:
    caller: str
    call_count: int
    callees: list[dict] = field(default_factory=list)
    override_complexity: int = 0  # total candidate overrides


@dataclass
class MacroJungleFinding:
    name: str
    qualified_name: str
    start_line: int
    end_line: int
    branch_count: int
    macros_used: list[str] = field(default_factory=list)
    complexity_score: int = 0


@dataclass
class RefactorRecommendation:
    priority: int           # 1=critical, 2=high, 3=medium, 4=low
    category: str           # god_function / dangerous_global / virtual_dispatch / macro_jungle
    target: str             # function or variable name
    line: int
    reason: str
    suggested_action: str


@dataclass
class RefactorReport:
    """Complete refactoring assessment for a single source file."""
    file: str
    total_functions: int
    total_globals: int
    total_virtual_calls: int
    total_lines: int

    god_functions: list[GodFunctionFinding] = field(default_factory=list)
    dangerous_globals: list[DangerousGlobalFinding] = field(default_factory=list)
    virtual_hotspots: list[VirtualDispatchHotspot] = field(default_factory=list)
    macro_jungle_targets: list[MacroJungleFinding] = field(default_factory=list)
    recommendations: list[RefactorRecommendation] = field(default_factory=list)

    # Summary scores
    overall_risk: str = "low"  # low/medium/high/critical
    maintainability_index: float = 100.0  # 0-100, lower is worse

    def to_dict(self) -> dict:
        """Serialize to plain dict for JSON output."""
        import dataclasses
        return dataclasses.asdict(self)

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            f"=== Refactoring Report: {Path(self.file).name} ===",
            f"Total lines: {self.total_lines}",
            f"Total functions: {self.total_functions}",
            f"Total globals: {self.total_globals}",
            f"Total virtual calls: {self.total_virtual_calls}",
            f"Overall risk: {self.overall_risk}",
            f"Maintainability index: {self.maintainability_index:.1f}/100",
            "",
            f"God functions: {len(self.god_functions)}",
            f"Dangerous globals: {len(self.dangerous_globals)}",
            f"Virtual dispatch hotspots: {len(self.virtual_hotspots)}",
            f"Macro jungle targets: {len(self.macro_jungle_targets)}",
            "",
            f"Recommendations ({len(self.recommendations)}):",
        ]
        for i, rec in enumerate(self.recommendations[:10], 1):
            lines.append(
                f"  {i}. [P{rec.priority}] {rec.category}: {rec.target} "
                f"(L{rec.line}) — {rec.reason}"
            )
            lines.append(f"     → {rec.suggested_action}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Report generator
# ---------------------------------------------------------------------------
def generate_report(
    source_file: str,
    compile_db: str,
    thresholds: Optional[RefactorThresholds] = None,
) -> RefactorReport:
    """Run all analyzers and produce a structured refactoring report."""
    if thresholds is None:
        thresholds = RefactorThresholds()

    src = str(Path(source_file).resolve())
    eng = get_engine()
    tu = eng.get_tu(src, compile_db, full_bodies=True)

    # Count lines
    try:
        with open(src, "r", encoding="utf-8", errors="replace") as f:
            total_lines = sum(1 for _ in f)
    except OSError:
        total_lines = 0

    # --- Run all analyzers ---
    funcs = list_functions(tu, src)
    globs = globals_in_file(tu, src)
    vcalls = virtual_calls(tu, src)
    mj = macro_jungle(tu, src)

    report = RefactorReport(
        file=src,
        total_functions=len(funcs),
        total_globals=len(globs),
        total_virtual_calls=len(vcalls),
        total_lines=total_lines,
    )

    # --- God functions ---
    for f in funcs:
        is_god = (
            f["line_count"] >= thresholds.god_function_lines
            or f["cyclomatic_complexity"] >= thresholds.god_function_complexity
        )
        if is_god:
            risk = (
                f["line_count"] / thresholds.god_function_lines
                + f["cyclomatic_complexity"] / thresholds.god_function_complexity
            ) / 2.0
            report.god_functions.append(GodFunctionFinding(
                name=f["name"],
                qualified_name=f["qualified_name"],
                start_line=f["start_line"],
                end_line=f["end_line"],
                line_count=f["line_count"],
                cyclomatic_complexity=f["cyclomatic_complexity"],
                is_virtual=f["is_virtual"],
                risk_score=min(risk, 5.0),
            ))

    # --- Dangerous globals ---
    for g in globs:
        risk_level = "low"
        if g["has_dynamic_init"] and not g["is_const"]:
            risk_level = "critical" if g["kind"] == "extern" else "high"
        elif g["has_dynamic_init"]:
            risk_level = "medium"
        elif g["kind"] == "extern" and not g["is_const"]:
            risk_level = "medium"

        if risk_level in ("medium", "high", "critical"):
            report.dangerous_globals.append(DangerousGlobalFinding(
                name=g["name"],
                qualified_name=g["qualified_name"],
                kind=g["kind"],
                type_name=g["type"],
                line=g["line"],
                has_dynamic_init=g["has_dynamic_init"],
                is_const=g["is_const"],
                risk_level=risk_level,
            ))

    # --- Virtual dispatch hotspots ---
    caller_groups: dict[str, list[dict]] = {}
    for vc in vcalls:
        caller = vc["caller"] or "<unknown>"
        caller_groups.setdefault(caller, []).append(vc)

    for caller, calls in caller_groups.items():
        if len(calls) >= thresholds.virtual_call_threshold:
            total_overrides = sum(
                len(c["candidate_overrides"]) for c in calls
            )
            report.virtual_hotspots.append(VirtualDispatchHotspot(
                caller=caller,
                call_count=len(calls),
                callees=[
                    {
                        "callee": c["callee"],
                        "class": c["callee_class"],
                        "line": c["line"],
                        "overrides": len(c["candidate_overrides"]),
                    }
                    for c in calls
                ],
                override_complexity=total_overrides,
            ))

    # --- Macro jungle ---
    for mf in mj.get("functions", []):
        if mf["complexity_score"] >= thresholds.macro_jungle_score:
            report.macro_jungle_targets.append(MacroJungleFinding(
                name=mf["name"],
                qualified_name=mf["qualified_name"],
                start_line=mf["start_line"],
                end_line=mf["end_line"],
                branch_count=mf["preprocessor"]["branch_count"],
                macros_used=mf["macros_used"],
                complexity_score=mf["complexity_score"],
            ))

    # --- Generate recommendations ---
    _generate_recommendations(report, thresholds)

    # --- Compute overall scores ---
    _compute_scores(report)

    return report


def _generate_recommendations(report: RefactorReport, thresholds: RefactorThresholds) -> None:
    """Generate prioritized refactoring recommendations."""
    recs = report.recommendations

    # God functions → Extract Method / Strategy Pattern
    for gf in sorted(report.god_functions, key=lambda x: -x.risk_score):
        if gf.line_count >= thresholds.god_function_lines * 3:
            priority = 1
            action = (
                "拆分为多个职责单一函数。"
                "识别内聚代码块，用 Extract Method 逐块抽取。"
                "如有 type-dispatch（if/switch on type），考虑 Strategy 模式。"
            )
        elif gf.cyclomatic_complexity >= thresholds.god_function_complexity * 2:
            priority = 2
            action = (
                "降低圈复杂度。"
                "提取条件判断为 Guard Clause，switch 改为查表或策略。"
            )
        else:
            priority = 3
            action = "提取内聚逻辑块为命名良好的子函数。"

        recs.append(RefactorRecommendation(
            priority=priority,
            category="god_function",
            target=gf.qualified_name,
            line=gf.start_line,
            reason=f"{gf.line_count} 行，圈复杂度 {gf.cyclomatic_complexity}",
            suggested_action=action,
        ))

    # Dangerous globals → Singleton / Dependency Injection
    for dg in sorted(
        report.dangerous_globals,
        key=lambda x: {"critical": 0, "high": 1, "medium": 2}.get(x.risk_level, 3),
    ):
        if dg.risk_level == "critical":
            priority = 1
            action = (
                "消除 SIOF 风险：改为 Meyer's Singleton（函数内 static）"
                "或延迟初始化，确保初始化顺序可控。"
            )
        elif dg.risk_level == "high":
            priority = 2
            action = "移入匿名 namespace 限制作用域，或改为依赖注入。"
        else:
            priority = 3
            action = "评估是否可以 constexpr 化或移入类内 static。"

        recs.append(RefactorRecommendation(
            priority=priority,
            category="dangerous_global",
            target=dg.qualified_name,
            line=dg.line,
            reason=f"{dg.kind}, 动态初始化={dg.has_dynamic_init}, 类型={dg.type_name}",
            suggested_action=action,
        ))

    # Virtual dispatch hotspots
    for vh in sorted(report.virtual_hotspots, key=lambda x: -x.override_complexity):
        priority = 2 if vh.override_complexity > 5 else 3
        action = (
            f"该函数含 {vh.call_count} 处虚调用，"
            f"涉及 {vh.override_complexity} 个候选覆写。"
            "考虑：(1) 模板化热路径 (CRTP) (2) 内联简单虚函数 "
            "(3) 引入 Visitor 模式减少动态分派。"
        )
        recs.append(RefactorRecommendation(
            priority=priority,
            category="virtual_dispatch",
            target=vh.caller,
            line=vh.callees[0]["line"] if vh.callees else 0,
            reason=f"{vh.call_count} 虚调用，{vh.override_complexity} 候选覆写",
            suggested_action=action,
        ))

    # Macro jungle → Platform Abstraction / Policy Pattern
    for mj in sorted(report.macro_jungle_targets, key=lambda x: -x.complexity_score):
        priority = 2 if mj.branch_count >= 6 else 3
        action = (
            f"预处理复杂度 {mj.complexity_score}（{mj.branch_count} 分支，"
            f"{len(mj.macros_used)} 宏）。"
            "建议：提取平台相关代码到独立文件（platform_linux.cpp 等），"
            "用编译期策略模式替代 #ifdef 丛林。"
        )
        recs.append(RefactorRecommendation(
            priority=priority,
            category="macro_jungle",
            target=mj.qualified_name,
            line=mj.start_line,
            reason=f"分支 {mj.branch_count}, 宏 {len(mj.macros_used)}, 分数 {mj.complexity_score}",
            suggested_action=action,
        ))

    # Sort by priority
    recs.sort(key=lambda x: (x.priority, x.line))


def _compute_scores(report: RefactorReport) -> None:
    """Compute overall risk and maintainability index."""
    # Risk: based on critical findings
    critical_count = sum(
        1 for dg in report.dangerous_globals if dg.risk_level == "critical"
    )
    high_risk_gods = sum(
        1 for gf in report.god_functions if gf.risk_score >= 3.0
    )

    if critical_count > 0 or high_risk_gods >= 3:
        report.overall_risk = "critical"
    elif len(report.god_functions) >= 3 or len(report.dangerous_globals) >= 5:
        report.overall_risk = "high"
    elif len(report.god_functions) >= 1 or len(report.dangerous_globals) >= 2:
        report.overall_risk = "medium"
    else:
        report.overall_risk = "low"

    # Maintainability index (simplified):
    # Start at 100, deduct for complexity
    score = 100.0
    for gf in report.god_functions:
        score -= min(gf.risk_score * 5, 20)
    for dg in report.dangerous_globals:
        penalty = {"critical": 10, "high": 5, "medium": 2, "low": 0}
        score -= penalty.get(dg.risk_level, 0)
    for mj in report.macro_jungle_targets:
        score -= min(mj.complexity_score * 0.5, 5)
    report.maintainability_index = max(0.0, min(100.0, score))
