"""LLM 调用封装模块"""
import logging
import os
import time
from functools import wraps
from typing import Generator, Optional, List, Dict, Any, cast

from dotenv import load_dotenv
from httpx import Timeout
from openai import OpenAI, APIError, AuthenticationError, RateLimitError

# 加载环境变量（模块级执行一次）
load_dotenv()

# 配置日志
logger = logging.getLogger(__name__)


def monitor_api_call(func):
    """监控 API 调用耗时的装饰器"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            if elapsed > 2.0:
                logger.warning(f"API 请求耗时: {elapsed:.2f}s")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"API 请求失败 (耗时 {elapsed:.2f}s): {e}")
            raise

    return wrapper


def monitor_streaming_ttft(func):
    """监控流式响应首帧延迟 (TTFT) 的装饰器"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        generator = func(*args, **kwargs)
        first_token_time = None
        start_time = time.time()

        for chunk in generator:
            if first_token_time is None:
                first_token_time = time.time() - start_time
                logger.info(f"首帧延迟 (TTFT): {first_token_time:.3f}s")
            yield chunk

        total_time = time.time() - start_time
        logger.info(f"流式响应总耗时: {total_time:.2f}s")

    return wrapper


class Agent:
    """LLM Agent 封装类，支持对话历史和流式响应"""

    def __init__(
            self,
            model: str,
            system_prompt: str = "",
            api_key: Optional[str] = None,
            base_url: Optional[str] = None,
            history: Optional[List[Dict[str, str]]] = None,
            enable_thinking: bool = False,
    ):
        """
        初始化 Agent
        
        Args:
            model: 模型名称
            system_prompt: 系统提示词
            api_key: API 密钥（默认从环境变量读取）
            base_url: API 基础 URL（默认从环境变量读取）
            history: 初始对话历史
            enable_thinking: 是否启用思考模式（仅部分模型支持）
        """
        # 实例级配置，更灵活
        self.model = model
        self.enable_thinking = enable_thinking
        self._system_prompt = system_prompt

        # 初始化客户端（支持自定义配置）
        # 优化：设置连接超时和读取超时，启用连接池复用
        self._client = OpenAI(
            api_key=api_key or os.getenv("API_KEY"),
            base_url=base_url or os.getenv("OPENAI_BASE_URL"),
            timeout=Timeout(
                connect=5.0,  # 连接超时（秒）- 快速失败
                read=60.0,  # 读取超时（秒）- 流式响应需要更长时间
                write=10.0,  # 写入超时（秒）
                pool=5.0,  # 连接池超时（秒）
            ),
        )

        # 初始化对话历史
        self.history: List[Dict[str, str]] = history.copy() if history else []
        if system_prompt:
            self.history.append({"role": "system", "content": system_prompt})

    @monitor_api_call
    def invoke(
            self,
            query: str,
            stream: bool = False,
            temperature: float = 0.7,
            max_tokens: Optional[int] = None,
    ) -> Optional[str] | Generator[str, None, None]:
        """
        发送消息并获取回复
        
        Args:
            query: 用户输入
            stream: 是否使用流式响应
            temperature: 温度参数（0-1）
            max_tokens: 最大 token 数
            
        Returns:
            非流式模式返回完整回答，流式模式返回生成器
        """
        self.history.append({"role": "user", "content": query})

        # 构建请求参数
        request_params: Dict[str, Any] = {
            "model": self.model,
            "messages": self.history,
            "stream": stream,
            "temperature": temperature,
            "extra_body": {"enable_thinking": self.enable_thinking},
        }

        if max_tokens is not None:
            request_params["max_tokens"] = max_tokens

        try:
            response = self._client.chat.completions.create(**request_params)
        except AuthenticationError as e:
            raise AuthenticationError(message=f"API 认证失败: {e}", response=e.response, body=e.body) from e
        except RateLimitError as e:
            raise RateLimitError(message=f"请求频率超限: {e}", response=e.response, body=e.body) from e
        except APIError as e:
            raise APIError(message=f"API 调用失败: {e}", request=e.request, body=e.body) from e

        if not stream:
            # 非流式：直接返回完整结果
            from openai.types.chat import ChatCompletion
            chat_response = cast(ChatCompletion, response)
            answer = chat_response.choices[0].message.content
            if answer is not None:
                self.history.append({"role": "assistant", "content": answer})
            return answer
        else:
            # 流式：返回生成器
            return self._stream_response(response)

    @monitor_streaming_ttft
    def _stream_response(self, response) -> Generator[str, None, None]:
        """处理流式响应并保存到历史"""
        full_reply = ""
        try:
            for chunk in response:
                if hasattr(chunk, "choices") and chunk.choices:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, "content") and delta.content:
                        full_reply += delta.content
                        yield delta.content
        finally:
            # 无论是否异常，都保存已生成的回复到历史
            if full_reply:
                self.history.append({"role": "assistant", "content": full_reply})

    def reset(self):
        """重置对话历史，保留 system_prompt"""
        self.history = []
        if self._system_prompt:
            self.history.append({"role": "system", "content": self._system_prompt})

    def get_history(self) -> List[Dict[str, str]]:
        """获取当前对话历史（不包含 system_prompt）"""
        return [msg for msg in self.history if msg["role"] != "system"]

    def get_token_count(self) -> int:
        """估算当前历史的 token 数量（粗略估算）"""
        total_chars = sum(len(msg.get("content", "")) for msg in self.history)
        # 粗略估算：英文约 4 字符/token，中文约 1.5 字符/token
        return int(total_chars / 2.5)

    @staticmethod
    def print_response(response: str | None | Generator[str, None, None]):
        """打印流式响应"""
        if isinstance(response, str):
            print(response)
        elif response is not None:
            for chunk in response:
                print(chunk, end="", flush=True)


if __name__ == "__main__":
    # 示例 1: 非流式调用
    print("=" * 60)
    print("示例 1: 非流式调用")
    print("=" * 60)
    agent = Agent(
        "qwen3.5-plus",
        system_prompt="你是一个专业的 AI 助手。",
    )
    result = agent.invoke("用一句话介绍 Python")
    agent.print_response(result)
    print()

    # 示例 2: 流式调用
    print("=" * 60)
    print("示例 2: 流式调用")
    print("=" * 60)
    agent2 = Agent("qwen3.5-plus")
    result = agent2.invoke("介绍一下 OpenAI", stream=True)
    agent2.print_response(result)
    print()

    # 示例 3: 多轮对话
    print("=" * 60)
    print("示例 3: 多轮对话")
    print("=" * 60)
    agent3 = Agent("qwen3.5-plus", system_prompt="你是一个代码审查专家。")
    print("第一轮:", end="")
    agent3.print_response(
        agent3.invoke("Python 中列表和元组有什么区别？", stream=True, temperature=0.7, max_tokens=1024))
    print()
    print("第二轮:", end="")
    agent3.print_response(agent3.invoke("能举个例子吗？", stream=True, temperature=0.7, max_tokens=1024))
    print()
    print(f"对话历史条数: {len(agent3.history)}")
