"""任务运行器 + Trace 收集器（对接 OpenClaw 网关）"""
import asyncio
import logging
import subprocess
import time
from typing import Optional, Dict, Any

import httpx

from src.clawskillscope.models import TaskTrace, TraceStep, ToolCall

logger = logging.getLogger(__name__)


class OpenClawRunner:
    """管理 OpenClaw 网关的生命周期并收集 trace"""

    def __init__(self, port: int = 18789, timeout: int = 120):
        self.port = port
        self.timeout = timeout
        self.process: Optional[subprocess.Popen] = None
        self.base_url = f"http://127.0.0.1:{port}"

    async def start_gateway(self, skill_dir: Optional[str] = None):
        """启动 OpenClaw 网关"""
        cmd = [
            "openclaw", "gateway",
            "--port", str(self.port),
            "--log-level", "debug",
        ]
        if skill_dir:
            cmd.extend(["--skill-dir", skill_dir])

        logger.info(f"启动 OpenClaw 网关: {' '.join(cmd)}")

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # 等待网关就绪
        async with httpx.AsyncClient(timeout=5) as client:
            for attempt in range(30):
                try:
                    resp = await client.get(f"{self.base_url}/health")
                    if resp.status_code == 200:
                        logger.info("OpenClaw 网关已就绪")
                        return
                except (httpx.ConnectError, httpx.TimeoutException):
                    pass

                if attempt % 5 == 0:
                    logger.debug(f"等待网关就绪... (尝试 {attempt + 1}/30)")
                await asyncio.sleep(0.5)

        # 检查进程是否异常退出
        if self.process is not None and self.process.poll() is not None:
            stderr_output = ""
            if self.process.stderr is not None:
                stderr_output = self.process.stderr.read().decode('utf-8', errors='ignore')
            raise RuntimeError(f"OpenClaw 网关启动失败: {stderr_output[:500]}")

        raise RuntimeError("OpenClaw 网关启动超时")

    async def stop_gateway(self):
        """关闭网关"""
        if self.process:
            logger.info("关闭 OpenClaw 网关")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("网关未响应 terminate，强制 kill")
                self.process.kill()
            self.process = None

    async def send_message(self, prompt: str) -> Dict[str, Any]:
        """发送聊天请求并返回完整响应"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            logger.info(f"发送聊天请求到 {self.base_url}/chat/completions")
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def get_debug_trace(self) -> list:
        """从 /debug 端点获取当前 trace 日志"""
        async with httpx.AsyncClient(timeout=5) as client:
            try:
                resp = await client.get(f"{self.base_url}/debug")
                if resp.status_code == 200:
                    data = resp.json()
                    traces = data.get("traces", [])
                    logger.debug(f"获取到 {len(traces)} 条 trace")
                    return traces
            except Exception as e:
                logger.warning(f"获取 trace 失败: {e}")
                return []
        return []

    @staticmethod
    def _parse_trace_to_steps(traces: list) -> tuple:
        """解析 trace 数据为 TraceStep 列表"""
        steps = []
        total_tokens = 0
        tool_call_count = 0

        for t in traces:
            step = TraceStep(
                step_type=t.get("type", "unknown"),
                content=t.get("content", ""),
                duration_ms=t.get("duration_ms", 0),
                token_count=t.get("token_count", 0),
            )

            # 解析工具调用
            for tc in t.get("tool_calls", []):
                tool_call = ToolCall(
                    tool_name=tc.get("name", ""),
                    arguments=tc.get("arguments", {}),
                    result=tc.get("result", ""),
                    duration_ms=tc.get("duration_ms", 0),
                )
                step.tool_calls.append(tool_call)
                tool_call_count += 1

            total_tokens += step.token_count
            steps.append(step)

        return steps, total_tokens, tool_call_count

    async def run_task(self, prompt: str, skill_dir: Optional[str] = None) -> TaskTrace:
        """执行一次完整任务并返回 trace"""
        await self.start_gateway(skill_dir)

        try:
            # 发送消息
            start_time = time.time()
            try:
                response = await self.send_message(prompt)
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP 请求失败: {e}")
                return TaskTrace(
                    prompt=prompt,
                    error=f"HTTP 错误: {e.response.status_code} - {e.response.text}",
                )
            except Exception as e:
                logger.error(f"发送消息失败: {e}")
                return TaskTrace(
                    prompt=prompt,
                    error=f"请求失败: {str(e)}",
                )

            elapsed = (time.time() - start_time) * 1000

            # 收集 trace
            traces = await self.get_debug_trace()

            # 解析 trace 为 steps
            steps, total_tokens, tool_call_count = OpenClawRunner._parse_trace_to_steps(traces)

            logger.info(f"任务完成: {len(steps)} 步, {total_tokens} tokens, {tool_call_count} 次工具调用")

            return TaskTrace(
                prompt=prompt,
                steps=steps,
                total_tokens=total_tokens,
                total_duration_ms=elapsed,
                tool_call_count=tool_call_count,
            )

        finally:
            await self.stop_gateway()
