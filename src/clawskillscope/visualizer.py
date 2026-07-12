"""HTML 可视化报告生成器"""
import json
from typing import Optional

from .models import SkillModel, ScoreReport, TaskTrace, ComparisonReport


def render_html(
        skill: SkillModel,
        report: ScoreReport,
        trace: Optional[TaskTrace] = None,
        comparison: Optional[ComparisonReport] = None,
) -> str:
    """生成单页 HTML 报告"""
    # 构建评分雷达图数据（Chart.js）
    dim_names = [d.name for d in report.dimensions]
    dim_scores = [d.score for d in report.dimensions]

    # 构建 Mermaid 时序图（如果有 trace）
    mermaid_code = ""
    if trace and trace.steps:
        lines = ["sequenceDiagram"]
        for i, step in enumerate(trace.steps):
            actor = step.step_type.capitalize()
            if step.skill_injected:
                actor = f"{actor}(skill:{step.injected_skill_name})"
            lines.append(f"    {actor}->>{actor}: Step{i + 1} ({step.duration_ms:.0f}ms)")
            for tc in step.tool_calls:
                lines.append(f"    {actor}->>Tool({tc.tool_name}): {tc.arguments}")
                lines.append(f"    Tool({tc.tool_name})->>{actor}: ...")
        mermaid_code = "\n".join(lines)

    # 构建对照实验表格
    comp_table = ""
    if comparison:
        comp_table = f"""
        <table>
            <tr><th>指标</th><th>带 Skill</th><th>不带 Skill</th></tr>
            <tr><td>Token 数</td><td>{comparison.with_skill.total_tokens}</td><td>{comparison.without_skill.total_tokens}</td></tr>
            <tr><td>耗时 (ms)</td><td>{comparison.with_skill.total_duration_ms:.0f}</td><td>{comparison.without_skill.total_duration_ms:.0f}</td></tr>
            <tr><td>工具调用次数</td><td>{comparison.with_skill.tool_call_count}</td><td>{comparison.without_skill.tool_call_count}</td></tr>
        </table>
        <p>{comparison.summary}</p>
        """

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>ClawSkillScope 评测报告 - {skill.name}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
<style>
body {{ font-family: sans-serif; margin: 20px; }}
.container {{ display: flex; gap: 20px; flex-wrap: wrap; }}
.left {{ flex: 1; min-width: 250px; }}
.right {{ flex: 2; min-width: 400px; }}
.card {{ background: #f5f5f5; border-radius: 8px; padding: 15px; margin-bottom: 15px; }}
canvas {{ max-height: 250px; }}
.suggestion {{ color: #d32f2f; font-size: 0.9em; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
th {{ background-color: #f2f2f2; }}
</style>
</head>
<body>
<h1>🔍 ClawSkillScope 评测报告</h1>
<h2>{skill.name}</h2>
<p><strong>描述:</strong> {skill.description}</p>

<div class="container">
    <div class="left">
        <div class="card">
            <h3>评分雷达图</h3>
            <canvas id="radarChart"></canvas>
        </div>
        <div class="card">
            <h3>总分: {report.total_score:.1f}/100</h3>
            <ul>
            {"".join(f'<li>{d.name}: {d.score:.0f} - {d.details}</li>' for d in report.dimensions)}
            </ul>
        </div>
        <div class="card">
            <h3>改进建议</h3>
            <ul>
            {"".join(f'<li class="suggestion">{s}</li>' for s in report.overall_suggestions)}
            </ul>
        </div>
    </div>
    <div class="right">
        <div class="card">
            <h3>推理链</h3>
            <pre class="mermaid">{mermaid_code}</pre>
        </div>
        {comp_table}
    </div>
</div>

<script>
mermaid.initialize({{ startOnLoad: true }});
const ctx = document.getElementById('radarChart').getContext('2d');
new Chart(ctx, {{
    type: 'radar',
    data: {{
        labels: {json.dumps(dim_names)},
        datasets: [{{
            label: '评分',
            data: {json.dumps(dim_scores)},
            backgroundColor: 'rgba(54, 162, 235, 0.2)',
            borderColor: 'rgba(54, 162, 235, 1)',
            pointBackgroundColor: 'rgba(54, 162, 235, 1)',
        }}]
    }},
    options: {{
        scales: {{
            r: {{ beginAtZero: true, max: 100 }}
        }}
    }}
}});
</script>
</body>
</html>"""
    return html
