"""Skill 命中归因模块"""
from src.clawskillscope.models import SkillModel, TaskTrace


def attribute(trace: TaskTrace, skill: SkillModel) -> TaskTrace:
    """
    在 trace 的每一步中标注是否受 skill 影响。
    检测 system prompt 中是否包含 skill 名称或描述的关键片段。
    """
    # 构建检测关键词（取 name 和 description 的前 20 个字符）
    keywords = [skill.name.lower()]
    if skill.description:
        keywords.append(skill.description.lower()[:30])

    for step in trace.steps:
        if step.step_type == "system":
            content_lower = step.content.lower()
            for kw in keywords:
                if kw and kw in content_lower:
                    step.skill_injected = True
                    step.injected_skill_name = skill.name
                    break

    return trace
