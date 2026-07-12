"""Markdown 报告生成器"""
from typing import Optional

from src.clawskillscope.models import SkillModel, ScoreReport, TaskTrace, ComparisonReport


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
        f"**文件路径**: `{skill.path}`",
        "",
    ]

    # 警告信息
    if skill.warnings:
        lines.append("## ⚠️ 警告")
        lines.append("")
        for w in skill.warnings:
            lines.append(f"- {w}")
        lines.append("")

    # 静态评分
    lines.append("## 📊 静态评分")
    lines.append("")
    lines.append(f"**总分**: {report.total_score:.1f}/100")
    lines.append("")
    lines.append("| 维度 | 分数 | 详情 |")
    lines.append("|------|------|------|")
    for d in report.dimensions:
        lines.append(f"| {d.name} | {d.score:.0f}/100 | {d.details} |")
    lines.append("")

    # 改进建议
    if report.overall_suggestions:
        lines.append("## 💡 改进建议")
        lines.append("")
        for i, s in enumerate(report.overall_suggestions, 1):
            lines.append(f"{i}. {s}")
        lines.append("")

    # 推理链
    if trace and trace.steps:
        lines.append("## 🔗 推理链")
        lines.append("")
        lines.append(f"**总步数**: {len(trace.steps)}")
        lines.append(f"**总 Token**: {trace.total_tokens}")
        lines.append(f"**总耗时**: {trace.total_duration_ms:.0f}ms")
        lines.append(f"**工具调用次数**: {trace.tool_call_count}")
        lines.append("")

        skill_injected_count = sum(1 for step in trace.steps if step.skill_injected)
        if skill_injected_count > 0:
            lines.append(f"**Skill 注入步数**: {skill_injected_count}")
            lines.append("")

        for i, step in enumerate(trace.steps):
            marker = " 🎯" if step.skill_injected else ""
            skill_tag = f" (skill: {step.injected_skill_name})" if step.skill_injected else ""
            lines.append(f"### Step {i + 1}{marker}: {step.step_type}{skill_tag}")
            lines.append(f"- ⏱️ 耗时: {step.duration_ms:.0f}ms")
            lines.append(f"- 📝 Token: {step.token_count}")
            if step.content:
                content_preview = step.content[:200] + "..." if len(step.content) > 200 else step.content
                lines.append(f"- 📄 内容: {content_preview}")
            for tc in step.tool_calls:
                lines.append(f"- 🔧 工具调用: **{tc.tool_name}**")
                if tc.arguments:
                    import json
                    args_str = json.dumps(tc.arguments, ensure_ascii=False, indent=2)
                    lines.append(f"  ```json")
                    lines.append(f"  {args_str}")
                    lines.append(f"  ```")
                if tc.result:
                    result_preview = tc.result[:200] + "..." if len(tc.result) > 200 else tc.result
                    lines.append(f"- 📤 结果: {result_preview}")
            lines.append("")

    # 对照实验
    if comparison:
        lines.append("## ⚖️ 对照实验")
        lines.append("")
        lines.append("| 指标 | 带 Skill | 不带 Skill | 差异 |")
        lines.append("|------|----------|------------|------|")

        token_trend = "↑" if comparison.token_diff > 0 else "↓"
        duration_trend = "↑" if comparison.duration_diff_ms > 0 else "↓"

        lines.append(
            f"| Token 数 | {comparison.with_skill.total_tokens} | "
            f"{comparison.without_skill.total_tokens} | "
            f"{token_trend} {abs(comparison.token_diff)} |"
        )
        lines.append(
            f"| 耗时 (ms) | {comparison.with_skill.total_duration_ms:.0f} | "
            f"{comparison.without_skill.total_duration_ms:.0f} | "
            f"{duration_trend} {abs(comparison.duration_diff_ms):.0f}ms |"
        )
        lines.append(
            f"| 工具调用次数 | {comparison.with_skill.tool_call_count} | "
            f"{comparison.without_skill.tool_call_count} | "
            f"{comparison.with_skill.tool_call_count - comparison.without_skill.tool_call_count:+d} |"
        )
        lines.append(
            f"| 回答质量评分 | {comparison.quality_score_with:.1f}/10 | "
            f"{comparison.quality_score_without:.1f}/10 | "
            f"{comparison.quality_score_with - comparison.quality_score_without:+.1f} |"
        )
        lines.append("")
        lines.append(f"**摘要**: {comparison.summary}")
        lines.append("")

    # 生成时间
    from datetime import datetime
    lines.append("---")
    lines.append(f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    lines.append("*由 ClawSkillScope 自动生成*")

    return "\n".join(lines)
