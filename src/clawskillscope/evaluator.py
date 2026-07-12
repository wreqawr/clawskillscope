"""静态评测引擎：5 维评分 + LLM Judge"""
import json
import re

from src.clawskillscope.models import SkillModel, ScoreDimension, ScoreReport


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

    unique_indents_count = 0
    if indent_counts:
        unique_indents = set(indent_counts)
        unique_indents_count = len(unique_indents)
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
        details=f"缩进种类数={unique_indents_count}",
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


# ---------- LLM Judge 功能 ----------

def _llm_evaluate_description(skill: SkillModel) -> ScoreDimension:
    """使用 LLM 评估描述清晰度"""
    from src.clawskillscope.llm import Agent

    prompt = f"""请作为 Skill 质量评估专家，对以下 Skill 的描述清晰度进行评分（0-100分）。

评分标准：
- 90-100: 描述非常清晰完整，包含触发条件、功能说明、输出格式、使用边界
- 70-89: 描述较清晰，包含大部分必要信息，但缺少少量细节
- 50-69: 描述基本可理解，但缺少关键信息（如触发条件或使用边界）
- 0-49: 描述模糊或不完整，难以理解 Skill 的用途和使用方式

Skill 信息：
- 名称: {skill.name}
- 描述: {skill.description}
- 触发条件: {skill.trigger or '未指定'}
- 正文前200字: {skill.body[:200]}

请严格按照以下 JSON 格式返回评分结果（不要添加其他内容）：
{{
  "score": 85,
  "reason": "评分理由",
  "suggestions": ["建议1", "建议2"]
}}
"""

    try:
        agent = Agent("qwen3.5-plus",
                      system_prompt="你是一个专业的 Skill 质量评估专家，擅长评估 Skill 描述的清晰度和完整性。")
        response = agent.invoke(prompt)

        # 尝试解析 JSON 响应
        import re
        if response and isinstance(response, str):
            json_match = re.search(r'\{[^}]+}', response, re.DOTALL)
        else:
            json_match = None
        if json_match:
            result = json.loads(json_match.group())
            return ScoreDimension(
                name="描述清晰度(LLM)",
                score=float(result.get("score", 70)),
                weight=0.25,
                details=result.get("reason", "LLM 评估"),
                suggestions=result.get("suggestions", []),
            )
    except Exception as e:
        print(f"LLM 评估描述清晰度失败: {e}，使用规则评分")

    # 失败时回退到规则评分
    return _check_description(skill)


def _llm_evaluate_reusability(skill: SkillModel) -> ScoreDimension:
    """使用 LLM 评估可复用性"""
    from src.clawskillscope.llm import Agent

    prompt = f"""请作为 Skill 架构师，对以下 Skill 的可复用性进行评分（0-100分）。

评分标准：
- 90-100: 高度参数化，无硬编码，支持环境变量，可轻松适配不同场景
- 70-89: 较好复用性，少量硬编码但不影响主要功能
- 50-69: 有一定复用性，但存在较多硬编码或特定依赖
- 0-49: 高度耦合，难以在其他场景复用

Skill 信息：
- 名称: {skill.name}
- 依赖工具: {', '.join(skill.tools) if skill.tools else '无'}
- 正文内容: {skill.body[:500]}

请严格按照以下 JSON 格式返回评分结果（不要添加其他内容）：
{{
  "score": 75,
  "reason": "评分理由",
  "suggestions": ["建议1", "建议2"]
}}
"""

    try:
        agent = Agent("qwen3.5-plus",
                      system_prompt="你是一个专业的 Skill 架构师，擅长评估 Skill 的可复用性和模块化设计。")
        response = agent.invoke(prompt)

        # 尝试解析 JSON 响应
        import re
        if response and isinstance(response, str):
            json_match = re.search(r'\{[^}]+}', response, re.DOTALL)
        else:
            json_match = None
        if json_match:
            result = json.loads(json_match.group())
            return ScoreDimension(
                name="可复用性(LLM)",
                score=float(result.get("score", 70)),
                weight=0.2,
                details=result.get("reason", "LLM 评估"),
                suggestions=result.get("suggestions", []),
            )
    except Exception as e:
        print(f"LLM 评估可复用性失败: {e}，使用规则评分")

    # 失败时回退到规则评分
    return _check_reusability(skill)


def evaluate_skill_quality(answer_with: str, answer_without: str, prompt: str) -> float:
    """使用 LLM 评估有/无 Skill 时的回答质量（0-10分）"""
    from src.clawskillscope.llm import Agent

    eval_prompt = f"""请作为 AI 回答质量评估专家，对比以下两个回答的质量。

用户问题: {prompt}

【带 Skill 的回答】:
{answer_with[:1000]}

【不带 Skill 的回答】:
{answer_without[:1000]}

评估标准：
- 准确性：回答是否正确、无误导信息
- 完整性：是否全面回答了用户问题
- 实用性：回答是否有实际帮助
- 清晰度：表达是否清晰易懂

请只返回一个数字（0-10），表示带 Skill 的回答相比不带 Skill 的回答的质量提升程度：
- 10: 显著提升，回答质量完全不同
- 7-9: 明显提升，回答更好
- 4-6: 略有提升，回答稍好
- 1-3: 微小提升，回答几乎相同
- 0: 无提升或更差

只返回数字，不要其他内容。
"""

    try:
        agent = Agent("qwen3.5-plus", system_prompt="你是一个专业的 AI 回答质量评估专家。")
        response = agent.invoke(eval_prompt)

        # 提取数字
        import re
        if response and isinstance(response, str):
            number_match = re.search(r'(\d+(?:\.\d+)?)', response)
        else:
            number_match = None
        if number_match:
            return min(10.0, max(0.0, float(number_match.group(1))))
    except Exception as e:
        print(f"LLM 质量评估失败: {e}")

    return 5.0  # 默认中等评分


# ---------- 主评测函数 ----------

def evaluate(skill: SkillModel, use_llm: bool = False) -> ScoreReport:
    """
    对 Skill 进行静态评测。
    若 use_llm=True，则调用 LLM 对描述清晰度和可复用性进行补充评分（需配置 API）。
    """
    if use_llm:
        dimensions = [
            _check_structure(skill),
            _llm_evaluate_description(skill),
            _check_safety(skill),
            _check_norm(skill),
            _llm_evaluate_reusability(skill),
        ]
    else:
        dimensions = [
            _check_structure(skill),
            _check_description(skill),
            _check_safety(skill),
            _check_norm(skill),
            _check_reusability(skill),
        ]

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
