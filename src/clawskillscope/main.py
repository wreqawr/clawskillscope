import typer

app = typer.Typer(help="ClawSkillScope - OpenClaw Skill 评测与可视化工具")


@app.command()
def analyze(
        skill_path: str = typer.Argument(..., help="SKILL.md 文件路径"),
        prompt: str = typer.Option(None, "--prompt", "-p", help="测试 prompt（可选）"),
):
    """分析并评测一个 OpenClaw skill"""
    typer.echo(f"正在分析 skill: {skill_path}")
    if prompt:
        typer.echo(f"测试 prompt: {prompt}")
    # TODO: 实现静态评测 + 动态 trace


@app.command()
def version():
    """显示版本信息"""
    typer.echo("ClawSkillScope v0.1.0")


if __name__ == "__main__":
    app()
