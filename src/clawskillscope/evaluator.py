"""静态评测引擎：5 维评分 + LLM Judge"""
import re

from .models import SkillModel, ScoreDimension, ScoreReport


# ---------- 规则评分函数 ----------

def _check_structure(skill: SkillModel) -> ScoreDimension:
    """结构完整性评分（20%）"""
    score = 80.0
    suggestions = []

    # 检查 frontmatter 是否存在
    if not skill.raw_frontmatter:
        score -= 20
        suggestions.append("缺少 YAML frontmatter，建议添加 name/description 字段")

    # 检查 name 是否合理
    if len(skill.name) < 2:
        score -= 10
        suggestions.append("name 过短，应至少 2 个字符")

    # 检查 body 是否有章节划分（二级标题）
    sections = re.findall(r"^##\s+", skill.body, re.MULTILINE)
    if len(sections) < 2:
        score -= 15
        suggestions.append("正文缺少章节划分（建议使用 ## 二级标题）")

    # 检查 tools 字段
    if not skill.tools:
        score -= 10
        suggestions.append("未声明依赖的工具（tools 字段）")

    # 检查 references
    if not skill.references:
        score -= 5
        suggestions.append("未引用任何参考文件（references 字段）")

    score = max(0.0, min(100.0, score))
    return ScoreDimension(
        name="结构完整性",
        score=score,
        weight=0.2,
        details=f"frontmatter={'有' if skill.raw_frontmatter else '无'}，正文章节数={len(sections)}，工具数={len(skill.tools)}",
        suggestions=suggestions,
    )


def _check_description(skill: SkillModel) -> ScoreDimension:
    """描述清晰度评分（25%）"""
    score = 70.0
    suggestions = []

    desc = skill.description.lower()

    # 长度检查
    if len(skill.description) < 20:
        score -= 20
        suggestions.append("description 过短，建议至少 20 个字符描述技能用途")

    # 是否包含触发条件关键词
    trigger_keywords = ["当用户", "when", "如果", "if", "触发", "trigger"]
    if not any(kw in desc for kw in trigger_keywords):
        score -= 15
        suggestions.append("description 中未包含触发条件描述（如'当用户请求...时'）")

    # 是否包含目标/输出描述
    goal_keywords = ["返回", "生成", "输出", "提供", "分析", "审查", "review", "generate", "return"]
    if not any(kw in desc for kw in goal_keywords):
        score -= 10
        suggestions.append("description 中未明确技能的输出或目标")

    # 是否包含限制/边界
    limit_keywords = ["仅", "只", "only", "限于", "不超过"]
    if not any(kw in desc for kw in limit_keywords):
        score -= 5
        suggestions.append("建议在 description 中说明使用边界（如'仅适用于 Python 代码'）")

    score = max(0.0, min(100.0, score))
    return ScoreDimension(
        name="描述清晰度",
        score=score,
        weight=0.25,
        details=f"描述长度={len(skill.description)}字符",
        suggestions=suggestions,
    )


def _check_safety(skill: SkillModel) -> ScoreDimension:
    """安全性评分（15%）"""
    score = 90.0
    suggestions = []

    body_lower = skill.body.lower()

    # 危险命令检测
    dangerous_patterns = [
        r"\brm\s+-rf\b", r"\bdd\b", r"\b>:?\s*/dev/", r"\bmkfs\b",
        r"\bchmod\s+777\b", r"\bcurl\s+.*\|.*sh\b", r"\bwget\s+.*\|.*sh\b",
    ]
    for pat in dangerous_patterns:
        if re.search(pat, body_lower):
            score -= 20
            suggestions.append(f"检测到危险命令模式: {pat}，请确认是否必要或添加安全警告")

    # 是否包含权限限制说明
    if "权限" not in body_lower and "permission" not in body_lower:
        score -= 5
        suggestions.append("建议在 skill 中说明所需权限或安全注意事项")

    score = max(0.0, min(100.0, score))
    return ScoreDimension(
        name="安全性",
        score=score,
        weight=0.15,
        details=f"危险模式命中数={len([p for p in dangerous_patterns if re.search(p, body_lower)])}",
        suggestions=suggestions,
    )


def _check_norm(skill: SkillModel) -> ScoreDimension:
    """规范性评分（20%）"""
    global unique_indents
    score = 80.0
    suggestions = []

    # 命名规范：name 是否驼峰或蛇形
    if not re.match(r"^[a-z][a-z0-9_-]*$", skill.name, re.IGNORECASE):
        score -= 10
        suggestions.append("name 建议使用小写字母、数字、下划线或连字符")

    # 检查正文缩进一致性（代码块内）
    lines = skill.body.split("\n")
    indent_counts = []
    for line in lines:
        stripped = line.lstrip()
        if stripped and not line.startswith("```"):
            indent = len(line) - len(stripped)
            indent_counts.append(indent)
    if indent_counts:
        unique_indents = set(indent_counts)
        if len(unique_indents) > 3:
            score -= 10
            suggestions.append("缩进风格不一致，建议统一缩进")

    # 检查是否有示例
    if "示例" not in skill.body and "example" not in skill.body.lower():
        score -= 10
        suggestions.append("建议在正文中添加使用示例")

    score = max(0.0, min(100.0, score))
    return ScoreDimension(
        name="规范性",
        score=score,
        weight=0.2,
        details=f"缩进种类数={len(unique_indents) if indent_counts else 0}",
        suggestions=suggestions,
    )


def _check_reusability(skill: SkillModel) -> ScoreDimension:
    """可复用性评分（20%）"""
    score = 70.0
    suggestions = []

    body = skill.body

    # 是否硬编码路径
    hardcoded_paths = re.findall(r"/[\w/]+\.\w{1,5}", body)
    if hardcoded_paths:
        score -= 15
        suggestions.append(f"检测到硬编码路径: {hardcoded_paths[:3]}，建议使用变量或配置")

    # 是否包含环境变量引用
    if "${" not in body and "$ENV{" not in body:
        score -= 10
        suggestions.append("建议支持环境变量配置以提高可移植性")

    # 是否参数化
    if "{{" not in body and "{input}" not in body.lower():
        score -= 10
        suggestions.append("建议使用模板变量（如 {{variable}}）实现参数化")

    # 是否依赖特定工具
    if not skill.tools:
        score -= 5
        suggestions.append("未声明依赖工具，可能影响复用")

    score = max(0.0, min(100.0, score))
    return ScoreDimension(
        name="可复用性",
        score=score,
        weight=0.2,
        details=f"硬编码路径数={len(hardcoded_paths)}，使用变量={'是' if '${' in body else '否'}",
        suggestions=suggestions,
    )


# ---------- 主评测函数 ----------

def evaluate(skill: SkillModel, use_llm: bool = False) -> ScoreReport:
    """
    对 Skill 进行静态评测。
    若 use_llm=True，则调用 LLM 对描述清晰度和可复用性进行补充评分（需配置 API）。
    """
    dimensions = [
        _check_structure(skill),
        _check_description(skill),
        _check_safety(skill),
        _check_norm(skill),
        _check_reusability(skill),
    ]

    # 可选：LLM Judge 补充评分（此处留接口，后续实现）
    if use_llm:
        pass  # TODO: 调用 LLM API 修正评分

    report = ScoreReport(
        skill_name=skill.name,
        dimensions=dimensions,
    )
    report.compute_total()

    # 收集所有建议
    all_suggestions = []
    for dim in dimensions:
        all_suggestions.extend(dim.suggestions)
    report.overall_suggestions = all_suggestions[:5]  # 最多5条

    return report
