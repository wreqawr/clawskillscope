"""CLI 入口"""
import asyncio
import logging
from pathlib import Path

import typer

from src.clawskillscope.attribution import attribute
from src.clawskillscope.comparator import compare
from src.clawskillscope.evaluator import evaluate
from src.clawskillscope.parser import parse_skill
from src.clawskillscope.reporter import generate_markdown
from src.clawskillscope.runner import OpenClawRunner
from src.clawskillscope.visualizer import render_html

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = typer.Typer(help="ClawSkillScope - OpenClaw Skill 评测与可视化工具")


@app.command()
def analyze(
        skill_path: str = typer.Argument(..., help="SKILL.md 文件路径"),
        prompt: str = typer.Option(None, "--prompt", "-p", help="测试 prompt"),
        compare_mode: bool = typer.Option(False, "--compare", "-c", help="执行对照实验"),
        use_llm: bool = typer.Option(False, "--llm", "-l", help="启用 LLM Judge 评分"),
        output_html: str = typer.Option("report.html", "--output-html", "-o", help="HTML 报告输出路径"),
        output_md: str = typer.Option("", "--output-md", "-m", help="Markdown 报告输出路径（可选）"),
):
    """分析并评测一个 OpenClaw skill"""
    # 1. 解析
    typer.echo(f"📖 正在解析 Skill: {skill_path}")
    skill = parse_skill(skill_path)
    typer.echo(f"✅ 解析完成: {skill.name}")

    if skill.warnings:
        typer.echo(f"⚠️ 发现 {len(skill.warnings)} 个警告:")
        for w in skill.warnings:
            typer.echo(f"   - {w}")

    # 2. 静态评测
    typer.echo(f"\n📊 正在进行静态评测{' (使用 LLM Judge)' if use_llm else ''}...")
    report = evaluate(skill, use_llm=use_llm)
    typer.echo(f"📊 静态评分: {report.total_score:.1f}/100")

    # 显示各维度分数
    for dim in report.dimensions:
        typer.echo(f"   - {dim.name}: {dim.score:.0f}/100")

    # 3. 动态 trace（如果有 prompt）
    trace = None
    comparison = None
    if prompt:
        typer.echo(f"\n🚀 正在执行任务 trace...")
        runner = OpenClawRunner()
        try:
            trace = asyncio.run(runner.run_task(prompt, skill_dir=str(Path(skill_path).parent)))

            if trace.error:
                typer.echo(f"❌ Trace 收集失败: {trace.error}")
            else:
                trace = attribute(trace, skill)
                typer.echo(f"✅ Trace 收集完成: {len(trace.steps)} 步")

                # 显示 skill 注入信息
                injected_steps = [s for s in trace.steps if s.skill_injected]
                if injected_steps:
                    typer.echo(f"🎯 Skill 注入: {len(injected_steps)} 步")

            # 对照实验
            if compare_mode and not trace.error:
                typer.echo(f"\n⚖️ 正在执行对照实验...")
                try:
                    comparison = asyncio.run(compare(skill, prompt))
                    typer.echo(f"✅ 对照实验完成")
                    typer.echo(f"   {comparison.summary}")
                except Exception as e:
                    typer.echo(f"❌ 对照实验失败: {e}")
        except Exception as e:
            typer.echo(f"❌ 任务执行失败: {e}")

    # 4. 生成报告
    typer.echo(f"\n📝 正在生成报告...")
    html_content = render_html(skill, report, trace, comparison)
    Path(output_html).write_text(html_content, encoding="utf-8")
    typer.echo(f"✅ HTML 报告已生成: {output_html}")

    if output_md:
        md_content = generate_markdown(skill, report, trace, comparison)
        Path(output_md).write_text(md_content, encoding="utf-8")
        typer.echo(f"✅ Markdown 报告已生成: {output_md}")

    typer.echo(f"\n🎉 评测完成！")


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
