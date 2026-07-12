"""测试演示脚本"""
from pathlib import Path
from src.clawskillscope.parser import parse_skill
from src.clawskillscope.evaluator import evaluate
from src.clawskillscope.reporter import generate_markdown
from src.clawskillscope.visualizer import render_html


def test_static_evaluation():
    """测试静态评测功能"""
    print("=" * 60)
    print("测试 1: 静态评测（规则评分）")
    print("=" * 60)
    
    skill = parse_skill("examples/skills/SKILL.md")
    print(f"✅ Skill 解析成功: {skill.name}")
    print(f"   描述: {skill.description}")
    print(f"   工具: {skill.tools}")
    print()
    
    report = evaluate(skill, use_llm=False)
    print(f"📊 静态评分: {report.total_score:.1f}/100")
    print()
    print("维度评分:")
    for dim in report.dimensions:
        print(f"  - {dim.name}: {dim.score:.0f}/100")
        if dim.suggestions:
            for s in dim.suggestions:
                print(f"    💡 {s}")
    print()


def test_llm_evaluation():
    """测试 LLM Judge 功能"""
    print("=" * 60)
    print("测试 2: LLM Judge 评分")
    print("=" * 60)
    
    skill = parse_skill("examples/skills/SKILL.md")
    report = evaluate(skill, use_llm=True)
    
    print(f"📊 LLM 评分: {report.total_score:.1f}/100")
    print()
    print("维度评分:")
    for dim in report.dimensions:
        print(f"  - {dim.name}: {dim.score:.0f}/100")
        if dim.details:
            print(f"    📝 {dim.details[:100]}...")
    print()
    
    if report.overall_suggestions:
        print("💡 改进建议:")
        for i, s in enumerate(report.overall_suggestions, 1):
            print(f"  {i}. {s}")
        print()


def test_report_generation():
    """测试报告生成功能"""
    print("=" * 60)
    print("测试 3: 报告生成")
    print("=" * 60)
    
    skill = parse_skill("examples/skills/SKILL.md")
    report = evaluate(skill, use_llm=True)
    
    # 生成 Markdown 报告
    md_content = generate_markdown(skill, report)
    md_path = Path("test_report.md")
    md_path.write_text(md_content, encoding="utf-8")
    print(f"✅ Markdown 报告已生成: {md_path}")
    
    # 生成 HTML 报告
    html_content = render_html(skill, report)
    html_path = Path("test_report.html")
    html_path.write_text(html_content, encoding="utf-8")
    print(f"✅ HTML 报告已生成: {html_path}")
    print()


if __name__ == "__main__":
    print("\n🚀 ClawSkillScope 功能测试\n")
    
    # 测试 1: 静态评测
    test_static_evaluation()
    
    # 测试 2: LLM Judge
    test_llm_evaluation()
    
    # 测试 3: 报告生成
    test_report_generation()
    
    print("=" * 60)
    print("✅ 所有测试完成！")
    print("=" * 60)