"""CLI 入口"""
import asyncio
from pathlib import Path

import typer

from .attribution import attribute
from .comparator import compare
from .evaluator import evaluate
from .parser import parse_skill
from .reporter import generate_markdown
from .runner import OpenClawRunner
from .visualizer import render_html

app = typer.Typer(help="ClawSkillScope - OpenClaw Skill 评测与可视化工具")


@app.command()
def analyze(
        skill_path: str = typer.Argument(..., help="SKILL.md 文件路径"),
        prompt: str = typer.Option(None, "--prompt", "-p", help="测试 prompt"),
        compare_mode: bool = typer.Option(False, "--compare", "-c", help="执行对照实验"),
        output_html: str = typer.Option("report.html", "--output", "-o", help="HTML 报告输出路径"),
        output_md: str = typer.Option("", "--markdown", "-m", help="Markdown 报告输出路径（可选）"),
):
    """分析并评测一个 OpenClaw skill"""
    # 1. 解析
    skill = parse_skill(skill_path)
    typer.echo(f"✅ 解析完成: {skill.name}")

    # 2. 静态评测
    report = evaluate(skill, use_llm=False)
    typer.echo(f"📊 静态评分: {report.total_score:.1f}/100")

    # 3. 动态 trace（如果有 prompt）
    trace = None
    comparison = None
    if prompt:
        runner = OpenClawRunner()
        trace = asyncio.run(runner.run_task(prompt, skill_dir=str(Path(skill_path).parent)))
        trace = attribute(trace, skill)
        typer.echo(f"🔍 Trace 收集完成: {len(trace.steps)} 步")

        # 对照实验
        if compare_mode:
            comparison = asyncio.run(compare(skill, prompt))
            typer.echo(f"⚖️ 对照实验完成: {comparison.summary}")

    # 4. 生成报告
    html_content = render_html(skill, report, trace, comparison)
    Path(output_html).write_text(html_content, encoding="utf-8")
    typer.echo(f"📄 HTML 报告已生成: {output_html}")

    if output_md:
        md_content = generate_markdown(skill, report, trace, comparison)
        Path(output_md).write_text(md_content, encoding="utf-8")
        typer.echo(f"📝 Markdown 报告已生成: {output_md}")


@app.command()
def version():
    """显示版本信息"""
    from importlib.metadata import version as get_version
    try:
        v = get_version("clawskillscope")
    except Exception:
        v = "0.1.0"
    typer.echo(f"ClawSkillScope v{v}")


if __name__ == "__main__":
    app()
