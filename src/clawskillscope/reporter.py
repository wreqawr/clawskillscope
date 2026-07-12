"""Markdown 报告生成器"""
from typing import Optional

from .models import SkillModel, ScoreReport, TaskTrace, ComparisonReport


def generate_markdown(
        skill: SkillModel,
        report: ScoreReport,
        trace: Optional[TaskTrace] = None,
        comparison: Optional[ComparisonReport] = None,
) -> str:
    """生成 Markdown 格式报告"""
    lines = [
        f"# ClawSkillScope 评测报告：{skill.name}",
        "",
        f"**描述**: {skill.description}",
        "",
        "## 静态评分",
        "| 维度 | 分数 | 详情 |",
        "|------|------|------|",
    ]
    for d in report.dimensions:
        lines.append(f"| {d.name} | {d.score:.0f} | {d.details} |")
    lines.append(f"| **总分** | **{report.total_score:.1f}** | |")
    lines.append("")

    if report.overall_suggestions:
        lines.append("## 改进建议")
        for s in report.overall_suggestions:
            lines.append(f"- {s}")
        lines.append("")

    if trace and trace.steps:
        lines.append("## 推理链")
        for i, step in enumerate(trace.steps):
            marker = " 🎯" if step.skill_injected else ""
            lines.append(f"### Step {i + 1}{marker}: {step.step_type}")
            lines.append(f"- 耗时: {step.duration_ms:.0f}ms")
            lines.append(f"- Token: {step.token_count}")
            for tc in step.tool_calls:
                lines.append(f"- 工具调用: {tc.tool_name}")
            lines.append("")

    if comparison:
        lines.append("## 对照实验")
        lines.append(f"| 指标 | 带 Skill | 不带 Skill |")
        lines.append(f"|------|----------|------------|")
        lines.append(f"| Token 数 | {comparison.with_skill.total_tokens} | {comparison.without_skill.total_tokens} |")
        lines.append(
            f"| 耗时 (ms) | {comparison.with_skill.total_duration_ms:.0f} | {comparison.without_skill.total_duration_ms:.0f} |")
        lines.append(
            f"| 工具调用次数 | {comparison.with_skill.tool_call_count} | {comparison.without_skill.tool_call_count} |")
        lines.append("")
        lines.append(f"**摘要**: {comparison.summary}")

    return "\n".join(lines)
