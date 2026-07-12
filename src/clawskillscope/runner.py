"""任务运行器 + Trace 收集器（对接 OpenClaw 网关）"""
import asyncio
import subprocess
import time
from typing import Optional

import httpx

from .models import TaskTrace, TraceStep, ToolCall


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

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # 等待网关就绪
        async with httpx.AsyncClient(timeout=5) as client:
            for _ in range(30):
                try:
                    resp = await client.get(f"{self.base_url}/health")
                    if resp.status_code == 200:
                        return
                except (httpx.ConnectError, httpx.TimeoutException):
                    pass
                await asyncio.sleep(0.5)
        raise RuntimeError("OpenClaw 网关启动超时")

    async def stop_gateway(self):
        """关闭网关"""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None

    async def send_message(self, prompt: str) -> dict:
        """发送聊天请求并返回完整响应"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": "deepseek-chat",  # 或其他模型名
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
                    return data.get("traces", [])
            except Exception:
                return []
        return []

    async def run_task(self, prompt: str, skill_dir: Optional[str] = None) -> TaskTrace:
        """执行一次完整任务并返回 trace"""
        await self.start_gateway(skill_dir)

        try:
            # 发送消息
            start_time = time.time()
            response = await self.send_message(prompt)
            elapsed = (time.time() - start_time) * 1000

            # 收集 trace
            traces = await self.get_debug_trace()

            # 解析 trace 为 steps（简化处理，实际需根据 OpenClaw trace 格式调整）
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

            return TaskTrace(
                prompt=prompt,
                steps=steps,
                total_tokens=total_tokens,
                total_duration_ms=elapsed,
                tool_call_count=tool_call_count,
            )

        finally:
            await self.stop_gateway()