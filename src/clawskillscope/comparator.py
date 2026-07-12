"""对照实验模块"""
import tempfile

from src.clawskillscope.evaluator import evaluate_skill_quality
from src.clawskillscope.models import SkillModel, ComparisonReport, TaskTrace
from src.clawskillscope.runner import OpenClawRunner


def _extract_answer(trace: TaskTrace) -> str:
    """从 trace 中提取最终回答"""
    for step in reversed(trace.steps):
        if step.step_type == "assistant" and step.content:
            return step.content
    return ""


async def compare(skill: SkillModel, prompt: str) -> ComparisonReport:
    """
    执行对照实验：有 skill vs 无 skill。
    返回 ComparisonReport。
    """
    runner = OpenClawRunner()

    # 有 skill：使用 skill 所在目录
    skill_dir = str(skill.path.parent)
    trace_with = await runner.run_task(prompt, skill_dir=skill_dir)

    # 无 skill：使用临时空目录
    with tempfile.TemporaryDirectory() as empty_dir:
        trace_without = await runner.run_task(prompt, skill_dir=empty_dir)

    # 计算差异
    token_diff = trace_with.total_tokens - trace_without.total_tokens
    duration_diff = trace_with.total_duration_ms - trace_without.total_duration_ms

    # LLM 质量评分
    answer_with = _extract_answer(trace_with)
    answer_without = _extract_answer(trace_without)

    quality_with = evaluate_skill_quality(answer_with, answer_without, prompt)
    quality_without = 5.0  # 基准分数

    # 生成摘要
    token_change = "增加" if token_diff > 0 else "减少"
    duration_change = "增加" if duration_diff > 0 else "减少"

    summary_parts = [
        f"带 skill 时 token 消耗 {token_change} {abs(token_diff)} tokens",
        f"耗时 {duration_change} {abs(duration_diff):.0f}ms",
        f"回答质量评分: {quality_with:.1f}/10",
    ]

    if trace_with.tool_call_count != trace_without.tool_call_count:
        tool_diff = trace_with.tool_call_count - trace_without.tool_call_count
        tool_change = "增加" if tool_diff > 0 else "减少"
        summary_parts.append(f"工具调用 {tool_change} {abs(tool_diff)} 次")

    summary = "，".join(summary_parts)

    return ComparisonReport(
        with_skill=trace_with,
        without_skill=trace_without,
        token_diff=token_diff,
        duration_diff_ms=duration_diff,
        quality_score_with=quality_with,
        quality_score_without=quality_without,
        summary=summary,
    )
