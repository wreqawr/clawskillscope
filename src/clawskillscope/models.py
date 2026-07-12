from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SkillModel(BaseModel):
    """解析后的 Skill 数据结构"""
    path: Path  # SKILL.md 文件路径
    name: str  # 技能名称
    description: str  # 技能描述
    trigger: Optional[str] = None  # 触发条件（可选）
    tools: List[str] = Field(default_factory=list)  # 依赖的工具列表
    references: List[str] = Field(default_factory=list)  # 参考文件列表
    body: str = ""  # 正文内容（不含 frontmatter）
    raw_frontmatter: Dict[str, Any] = Field(default_factory=dict)  # 原始 frontmatter 字典
    warnings: List[str] = Field(default_factory=list)  # 解析过程中的警告


class ScoreDimension(BaseModel):
    """单个维度的评分"""
    name: str  # 维度名称（如"结构完整性"）
    score: float = 0.0  # 0-100
    weight: float = 0.2  # 权重（总和应为1）
    details: str = ""  # 评分依据说明
    suggestions: List[str] = Field(default_factory=list)  # 改进建议


class ScoreReport(BaseModel):
    """静态评测报告"""
    skill_name: str
    dimensions: List[ScoreDimension] = Field(default_factory=list)
    total_score: float = 0.0  # 加权总分
    overall_suggestions: List[str] = Field(default_factory=list)

    def compute_total(self):
        """计算加权总分"""
        self.total_score = sum(d.score * d.weight for d in self.dimensions)


class ToolCall(BaseModel):
    """单次工具调用记录"""
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    result: str = ""
    duration_ms: float = 0.0


class TraceStep(BaseModel):
    """推理链中的一步"""
    step_type: str  # user / assistant / tool / system
    content: str = ""
    tool_calls: List[ToolCall] = Field(default_factory=list)
    duration_ms: float = 0.0
    token_count: int = 0
    skill_injected: bool = False  # 此步是否受 skill 影响
    injected_skill_name: str = ""  # 注入的 skill 名称（若有）


class TaskTrace(BaseModel):
    """一次任务的完整 trace"""
    prompt: str
    steps: List[TraceStep] = Field(default_factory=list)
    total_tokens: int = 0
    total_duration_ms: float = 0.0
    tool_call_count: int = 0
    error: Optional[str] = None


class ComparisonReport(BaseModel):
    """对照实验结果"""
    with_skill: TaskTrace
    without_skill: TaskTrace
    token_diff: int = 0
    duration_diff_ms: float = 0.0
    quality_score_with: float = 0.0  # LLM 评分（0-10）
    quality_score_without: float = 0.0
    summary: str = ""
