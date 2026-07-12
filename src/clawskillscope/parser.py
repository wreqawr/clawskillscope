"""SKILL.md 解析器"""
import re
from pathlib import Path

import yaml

from .models import SkillModel


def parse_skill(file_path: str | Path) -> SkillModel:
    """
    解析 OpenClaw 格式的 SKILL.md 文件。
    支持 YAML frontmatter（--- 包裹）或无 frontmatter 的纯 Markdown。
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Skill 文件不存在: {path}")

    raw_text = path.read_text(encoding="utf-8")
    warnings = []

    # 尝试提取 YAML frontmatter
    frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", raw_text, re.DOTALL)
    if frontmatter_match:
        yaml_str = frontmatter_match.group(1)
        try:
            frontmatter = yaml.safe_load(yaml_str) or {}
        except yaml.YAMLError as e:
            warnings.append(f"YAML 解析失败: {e}")
            frontmatter = {}
        body = raw_text[frontmatter_match.end():].strip()
    else:
        frontmatter = {}
        body = raw_text.strip()
        warnings.append("未找到 YAML frontmatter，将从正文推断元数据")

    # 从 frontmatter 或正文推断 name / description
    name = frontmatter.get("name", "")
    description = frontmatter.get("description", "")
    trigger = frontmatter.get("trigger")
    tools = frontmatter.get("tools", [])
    references = frontmatter.get("references", [])

    # 如果 name 为空，尝试从正文第一个标题提取
    if not name:
        title_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        if title_match:
            name = title_match.group(1).strip()
        else:
            name = path.stem
            warnings.append("未能提取 name，使用文件名作为默认名称")

    # 如果 description 为空，尝试从正文第一段提取
    if not description:
        # 按空行分割，取第一个非空段落作为描述
        paragraphs = re.split(r'\n\s*\n', body.strip())
        if paragraphs:
            description = paragraphs[0].strip()[:200]
        else:
            description = ""
            warnings.append("未能提取 description")

    return SkillModel(
        path=path,
        name=name,
        description=description,
        trigger=trigger,
        tools=tools if isinstance(tools, list) else [],
        references=references if isinstance(references, list) else [],
        body=body,
        raw_frontmatter=frontmatter,
        warnings=warnings,
    )
