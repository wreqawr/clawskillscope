import os

from dotenv import load_dotenv
from openai import OpenAI


# noinspection PyUnresolvedReferences
class Agent:
    load_dotenv()
    _OPENAI_BASE_URL: str | None = os.getenv("OPENAI_BASE_URL")
    _API_KEY: str | None = os.getenv("API_KEY")
    _CLIENT = OpenAI(api_key=_API_KEY, base_url=_OPENAI_BASE_URL)

    def __init__(self, model: str, system_prompt="", history=None):
        if history is None:
            history = []
        history.append({"role": "system", "content": system_prompt})
        self.model = model
        self.history: list = history

    def invoke(self, query: str, stream=False):
        self.history.append({"role": "user", "content": query})
        response = self._CLIENT.chat.completions.create(
            model=self.model,
            messages=self.history,
            extra_body={"enable_thinking": False},
            stream=stream
        )

        if not stream:
            # 非流式：直接返回完整结果
            answer = response.choices[0].message.content
            self.history.append({"role": "assistant", "content": answer})
            return answer
        else:
            # 流式：返回生成器
            def generate():
                full_reply = ""
                for chunk in response:
                    if hasattr(chunk, "choices") and chunk.choices:
                        delta = chunk.choices[0].delta
                        if hasattr(delta, "content") and delta.content:
                            text = delta.content
                            full_reply += text
                            yield text

            return generate()

    def reset(self):
        self.history = []


if __name__ == "__main__":
    agent = Agent("qwen3.5-plus")
    result = agent.invoke("介绍一下skills", stream=True)
    if isinstance(result, str):
        print(result)
    else:
        for item in result:
            print(item, end="", flush=True)
    print()
