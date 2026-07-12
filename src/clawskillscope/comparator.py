"""对照实验模块"""
import tempfile

from .models import SkillModel, ComparisonReport
from .runner import OpenClawRunner


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

    # LLM 质量评分（TODO：调用 LLM 对两个回答打分）
    quality_with = 0.0
    quality_without = 0.0
    summary = (
        f"带 skill 时 token 消耗 {'增加' if token_diff > 0 else '减少'} {abs(token_diff)} tokens，"
        f"耗时 {'增加' if duration_diff > 0 else '减少'} {abs(duration_diff):.0f}ms"
    )

    return ComparisonReport(
        with_skill=trace_with,
        without_skill=trace_without,
        token_diff=token_diff,
        duration_diff_ms=duration_diff,
        quality_score_with=quality_with,
        quality_score_without=quality_without,
        summary=summary,
    )
