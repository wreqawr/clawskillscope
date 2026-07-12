"""HTML 可视化报告生成器"""
import json
from typing import Optional

from src.clawskillscope.models import SkillModel, ScoreReport, TaskTrace, ComparisonReport


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
        lines = ["sequenceDiagram",
                 "    participant U as User",
                 "    participant A as Assistant",
                 "    participant T as Tools",
                 "    participant S as System"]

        for i, step in enumerate(trace.steps):
            step_num = i + 1
            duration_text = f"({step.duration_ms:.0f}ms)" if step.duration_ms > 0 else ""

            if step.step_type == "user":
                lines.append(f"    U->>A: Step {step_num}: User Input {duration_text}")
            elif step.step_type == "assistant":
                marker = " 🎯" if step.skill_injected else ""
                content_preview = step.content[:50] + "..." if len(step.content) > 50 else step.content
                lines.append(f"    A->>U: Step {step_num}: Assistant Response{marker} {duration_text}")
                if content_preview:
                    lines.append(f"    Note over A,U: {content_preview}")
            elif step.step_type == "tool":
                for tc in step.tool_calls:
                    lines.append(f"    A->>T: Step {step_num}: Call {tc.tool_name}")
                    lines.append(f"    T->>A: Result {duration_text}")
            elif step.step_type == "system":
                marker = " 🎯" if step.skill_injected else ""
                skill_name = f"(skill:{step.injected_skill_name})" if step.skill_injected else ""
                lines.append(f"    S->>A: Step {step_num}: System{skill_name}{marker} {duration_text}")

        mermaid_code = "\n".join(lines)

    # 构建步骤详情 JSON（用于交互）
    json.dumps([
        {
            "step": i + 1,
            "type": step.step_type,
            "content": step.content[:200] if step.content else "",
            "duration_ms": step.duration_ms,
            "token_count": step.token_count,
            "skill_injected": step.skill_injected,
            "injected_skill_name": step.injected_skill_name,
            "tool_calls": [
                {
                    "tool_name": tc.tool_name,
                    "arguments": str(tc.arguments)[:100],
                    "result": tc.result[:100] if tc.result else "",
                }
                for tc in step.tool_calls
            ],
        }
        for i, step in enumerate(trace.steps)
    ], ensure_ascii=False, indent=2) if trace and trace.steps else "[]"

    # 构建对照实验表格
    comp_table = ""
    if comparison:
        token_trend = "↑" if comparison.token_diff > 0 else "↓"
        duration_trend = "↑" if comparison.duration_diff_ms > 0 else "↓"

        comp_table = f"""
        <div class="card comparison-card">
            <h3>⚖️ 对照实验结果</h3>
            <table>
                <tr>
                    <th>指标</th>
                    <th>带 Skill</th>
                    <th>不带 Skill</th>
                    <th>差异</th>
                </tr>
                <tr>
                    <td>Token 数</td>
                    <td>{comparison.with_skill.total_tokens}</td>
                    <td>{comparison.without_skill.total_tokens}</td>
                    <td class="{'positive' if comparison.token_diff < 0 else 'negative'}">
                        {token_trend} {abs(comparison.token_diff)}
                    </td>
                </tr>
                <tr>
                    <td>耗时 (ms)</td>
                    <td>{comparison.with_skill.total_duration_ms:.0f}</td>
                    <td>{comparison.without_skill.total_duration_ms:.0f}</td>
                    <td class="{'positive' if comparison.duration_diff_ms < 0 else 'negative'}">
                        {duration_trend} {abs(comparison.duration_diff_ms):.0f}ms
                    </td>
                </tr>
                <tr>
                    <td>工具调用次数</td>
                    <td>{comparison.with_skill.tool_call_count}</td>
                    <td>{comparison.without_skill.tool_call_count}</td>
                    <td>{comparison.with_skill.tool_call_count - comparison.without_skill.tool_call_count:+d}</td>
                </tr>
                <tr>
                    <td>回答质量评分</td>
                    <td>{comparison.quality_score_with:.1f}/10</td>
                    <td>{comparison.quality_score_without:.1f}/10</td>
                    <td class="positive">
                        {comparison.quality_score_with - comparison.quality_score_without:+.1f}
                    </td>
                </tr>
            </table>
            <div class="summary-box">
                <strong>📊 摘要:</strong> {comparison.summary}
            </div>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ClawSkillScope 评测报告 - {skill.name}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
* {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}}

body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    padding: 20px;
    color: #333;
}}

.container {{
    max-width: 1400px;
    margin: 0 auto;
}}

header {{
    background: white;
    border-radius: 12px;
    padding: 25px;
    margin-bottom: 20px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}}

header h1 {{
    color: #667eea;
    margin-bottom: 10px;
    font-size: 2em;
}}

header .subtitle {{
    color: #666;
    font-size: 1.1em;
    margin-bottom: 15px;
}}

.badge {{
    display: inline-block;
    background: #667eea;
    color: white;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.85em;
    margin-right: 8px;
    margin-bottom: 8px;
}}

.badge.warning {{
    background: #ff9800;
}}

.badge.error {{
    background: #f44336;
}}

.grid {{
    display: grid;
    grid-template-columns: 1fr 2fr;
    gap: 20px;
    margin-bottom: 20px;
}}

@media (max-width: 1024px) {{
    .grid {{
        grid-template-columns: 1fr;
    }}
}}

.card {{
    background: white;
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    margin-bottom: 20px;
}}

.card h3 {{
    color: #667eea;
    margin-bottom: 15px;
    font-size: 1.3em;
    border-bottom: 2px solid #f0f0f0;
    padding-bottom: 10px;
}}

.score-display {{
    text-align: center;
    padding: 20px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border-radius: 8px;
    margin-bottom: 20px;
}}

.score-display .score {{
    font-size: 3em;
    font-weight: bold;
}}

.score-display .label {{
    font-size: 1.1em;
    opacity: 0.9;
}}

canvas {{
    max-height: 300px;
    margin: 20px 0;
}}

.suggestion-list {{
    list-style: none;
    padding: 0;
}}

.suggestion-list li {{
    background: #fff3cd;
    border-left: 4px solid #ffc107;
    padding: 12px;
    margin-bottom: 10px;
    border-radius: 4px;
    color: #856404;
}}

.suggestion-list li::before {{
    content: "💡 ";
}}

.timeline {{
    position: relative;
    padding-left: 30px;
}}

.timeline::before {{
    content: '';
    position: absolute;
    left: 10px;
    top: 0;
    bottom: 0;
    width: 2px;
    background: #667eea;
}}

.timeline-step {{
    position: relative;
    background: #f8f9fa;
    border-radius: 8px;
    padding: 15px;
    margin-bottom: 15px;
    cursor: pointer;
    transition: all 0.3s ease;
    border: 2px solid transparent;
}}

.timeline-step:hover {{
    border-color: #667eea;
    box-shadow: 0 2px 8px rgba(102, 126, 234, 0.2);
}}

.timeline-step.skill-injected {{
    background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
    border-left: 4px solid #2196f3;
}}

.timeline-step::before {{
    content: '';
    position: absolute;
    left: -26px;
    top: 20px;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: #667eea;
    border: 3px solid white;
    box-shadow: 0 0 0 2px #667eea;
}}

.timeline-step.skill-injected::before {{
    background: #2196f3;
    box-shadow: 0 0 0 2px #2196f3;
}}

.step-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
}}

.step-type {{
    font-weight: bold;
    color: #667eea;
    text-transform: uppercase;
    font-size: 0.85em;
}}

.step-type.skill-injected {{
    color: #2196f3;
}}

.step-meta {{
    display: flex;
    gap: 15px;
    font-size: 0.85em;
    color: #666;
}}

.step-meta span {{
    background: #f0f0f0;
    padding: 2px 8px;
    border-radius: 4px;
}}

.step-content {{
    color: #555;
    font-size: 0.9em;
    line-height: 1.5;
    max-height: 100px;
    overflow: hidden;
    text-overflow: ellipsis;
}}

.step-details {{
    display: none;
    margin-top: 15px;
    padding-top: 15px;
    border-top: 1px solid #e0e0e0;
    background: white;
    border-radius: 4px;
    padding: 15px;
}}

.timeline-step.expanded .step-details {{
    display: block;
}}

.tool-call {{
    background: #f5f5f5;
    border-radius: 4px;
    padding: 10px;
    margin-bottom: 10px;
}}

.tool-call .tool-name {{
    font-weight: bold;
    color: #4caf50;
    margin-bottom: 5px;
}}

.tool-call pre {{
    background: #263238;
    color: #aed581;
    padding: 10px;
    border-radius: 4px;
    overflow-x: auto;
    font-size: 0.85em;
    max-height: 200px;
    overflow-y: auto;
}}

table {{
    border-collapse: collapse;
    width: 100%;
    margin: 15px 0;
}}

th, td {{
    border: 1px solid #e0e0e0;
    padding: 12px;
    text-align: left;
}}

th {{
    background: #f5f5f5;
    font-weight: 600;
    color: #667eea;
}}

tr:hover {{
    background: #f8f9fa;
}}

.positive {{
    color: #4caf50;
    font-weight: bold;
}}

.negative {{
    color: #f44336;
    font-weight: bold;
}}

.summary-box {{
    background: #e3f2fd;
    border-left: 4px solid #2196f3;
    padding: 15px;
    border-radius: 4px;
    margin-top: 15px;
}}

.mermaid {{
    background: white;
    padding: 20px;
    border-radius: 8px;
    overflow-x: auto;
}}

.warning-box {{
    background: #fff3cd;
    border-left: 4px solid #ffc107;
    padding: 12px;
    margin-bottom: 15px;
    border-radius: 4px;
}}

.warning-box strong {{
    color: #856404;
}}
</style>
</head>
<body>
<div class="container">
    <header>
        <h1>🔍 ClawSkillScope 评测报告</h1>
        <div class="subtitle">
            <strong>Skill:</strong> {skill.name}<br>
            <strong>描述:</strong> {skill.description}
        </div>
        <div>
            {"<span class='badge warning'>⚠️ 有警告</span>" if skill.warnings else "<span class='badge'>✅ 无警告</span>"}
            {"<span class='badge'>🛠️ 工具: " + ", ".join(skill.tools) + "</span>" if skill.tools else ""}
        </div>
        {"".join(f'<div class="warning-box"><strong>⚠️ {w}</strong></div>' for w in skill.warnings)}
    </header>

    <div class="grid">
        <div class="left-panel">
            <div class="card">
                <div class="score-display">
                    <div class="label">总分</div>
                    <div class="score">{report.total_score:.1f}</div>
                    <div class="label">/ 100</div>
                </div>
                <h3>📊 评分雷达图</h3>
                <canvas id="radarChart"></canvas>
                <div style="margin-top: 20px;">
                    <h4 style="margin-bottom: 10px;">维度详情</h4>
                    {"".join(f'''
                    <div style="margin-bottom: 10px;">
                        <strong>{d.name}</strong>: {d.score:.0f}/100
                        <div style="background: #e0e0e0; border-radius: 4px; height: 8px; margin-top: 5px;">
                            <div style="background: #667eea; height: 100%; border-radius: 4px; width: {d.score}%;"></div>
                        </div>
                        <small style="color: #666;">{d.details}</small>
                    </div>
                    ''' for d in report.dimensions)}
                </div>
            </div>

            <div class="card">
                <h3>💡 改进建议</h3>
                {f'''
                <ul class="suggestion-list">
                    {"".join(f'<li>{s}</li>' for s in report.overall_suggestions)}
                </ul>
                ''' if report.overall_suggestions else '<p style="color: #4caf50;">✅ 暂无改进建议</p>'}
            </div>
        </div>

        <div class="right-panel">
            {f'''
            <div class="card">
                <h3>🔗 推理链时间线</h3>
                <div class="timeline" id="timeline">
                    {"".join(f'''
                    <div class="timeline-step {"skill-injected" if step.skill_injected else ""}" onclick="this.classList.toggle('expanded')">
                        <div class="step-header">
                            <span class="step-type {"skill-injected" if step.skill_injected else ""}">
                                Step {i + 1}: {step.step_type.upper()}
                                {"🎯 Skill 注入" if step.skill_injected else ""}
                            </span>
                            <div class="step-meta">
                                <span>⏱️ {step.duration_ms:.0f}ms</span>
                                <span>📝 {step.token_count} tokens</span>
                            </div>
                        </div>
                        <div class="step-content">
                            {step.content[:150] + "..." if len(step.content) > 150 else step.content}
                        </div>
                        {f'''
                        <div class="step-details">
                            <h4 style="margin-bottom: 10px;">工具调用</h4>
                            {"".join(f'''
                            <div class="tool-call">
                                <div class="tool-name">🔧 {tc.tool_name}</div>
                                <div style="margin-bottom: 5px;"><strong>参数:</strong></div>
                                <pre>{json.dumps(tc.arguments, ensure_ascii=False, indent=2)}</pre>
                                {f'<div style="margin-top: 5px;"><strong>结果:</strong></div><pre>{tc.result[:500]}</pre>' if tc.result else ''}
                            </div>
                            ''' for tc in step.tool_calls)}
                        </div>
                        ''' if step.tool_calls else ''}
                    </div>
                    ''' for i, step in enumerate(trace.steps))}
                </div>
            </div>
            ''' if trace and trace.steps else '<div class="card"><p>暂无 trace 数据</p></div>'}

            {comp_table}

            {f'''
            <div class="card">
                <h3>📈 流程图</h3>
                <div class="mermaid">
                    {mermaid_code}
                </div>
            </div>
            ''' if mermaid_code else ''}
        </div>
    </div>
</div>

<script>
mermaid.initialize({{ 
    startOnLoad: true,
    theme: 'default',
    securityLevel: 'loose',
}});

const ctx = document.getElementById('radarChart').getContext('2d');
new Chart(ctx, {{
    type: 'radar',
    data: {{
        labels: {json.dumps(dim_names)},
        datasets: [{{
            label: '评分',
            data: {json.dumps(dim_scores)},
            backgroundColor: 'rgba(102, 126, 234, 0.2)',
            borderColor: 'rgba(102, 126, 234, 1)',
            pointBackgroundColor: 'rgba(102, 126, 234, 1)',
            pointBorderColor: '#fff',
            pointHoverBackgroundColor: '#fff',
            pointHoverBorderColor: 'rgba(102, 126, 234, 1)',
        }}]
    }},
    options: {{
        responsive: true,
        maintainAspectRatio: false,
        scales: {{
            r: {{
                beginAtZero: true,
                max: 100,
                min: 0,
                ticks: {{
                    stepSize: 20
                }}
            }}
        }},
        plugins: {{
            legend: {{
                display: false
            }}
        }}
    }}
}});
</script>
</body>
</html>"""
    return html
