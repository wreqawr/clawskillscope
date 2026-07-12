---
name: code-review
description: 当用户请求代码审查时，分析代码质量、安全性和最佳实践。仅适用于 Python 和 JavaScript。
trigger: 用户请求代码审查或包含 "review" 关键词
tools:
  - code_analyzer
  - security_scanner
references:
  - style-guide.md
---

## 概述
本 Skill 用于自动审查代码，提供质量评分和改进建议。

## 使用方法
1. 用户提供代码片段或文件路径
2. Skill 调用 code_analyzer 进行静态分析
3. 调用 security_scanner 检查安全漏洞
4. 返回综合报告

## 注意事项
- 仅处理单个文件，不支持多文件审查
- 不修改用户代码