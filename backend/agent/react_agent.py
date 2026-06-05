import asyncio
import contextvars
from langchain.agents import create_agent
from langchain_core.messages import AIMessageChunk, ToolMessage
from models.factory import chat_model
from utils.prompt_loader import load_system_prompts
from agent.tools.agent_tools import (rag_summarize, get_weather, get_user_location, get_user_id,
                                     get_current_month, fetch_external_data, fill_context_for_report, web_search)
from agent.tools.middleware import monitor_tool, log_before_model, report_prompt_switch


class ReactAgent:
    def __init__(self):
        self.agent = create_agent(
            model=chat_model,
            system_prompt=load_system_prompts(),
            tools=[rag_summarize, get_weather, get_user_location, get_user_id,
                   get_current_month, fetch_external_data, fill_context_for_report, web_search],
            middleware=[monitor_tool, log_before_model, report_prompt_switch],
        )

    def _execute_stream_sync(self, query: str, context_messages: list[dict] | None = None):
        """同步版本：在独立线程中运行，内部工具调用（如 web_search）会阻塞该线程但不影响事件循环"""
        messages = []
        if context_messages:
            messages.extend(context_messages)
        messages.append({"role": "user", "content": query})

        print(f"[MEMORY] execute_stream 收到 {len(messages)} 条消息（含历史{len(context_messages or [])}条+当前用户消息）")
        input_dict = {"messages": messages}

        answering = False   # 工具调用完成后，尝试流式输出
        seen_tools = False  # 是否使用了工具
        pending = ""        # 工具调用前的思考缓冲
        has_content = False

        for event in self.agent.stream(input_dict, stream_mode="messages", context={"report": False}):
            if isinstance(event, tuple):
                msg = event[0]
            else:
                msg = event

            # 工具调用 → 如果之前已经在流式输出临时答案，通知前端清除
            if isinstance(msg, AIMessageChunk) and msg.tool_calls:
                if answering:
                    # 正在流式输出但出现了新工具 → 之前的是过渡文本
                    yield {"type": "clear"}
                    has_content = False
                seen_tools = True
                answering = False
                pending = ""
                for tc in msg.tool_calls:
                    yield {"type": "tool", "tool": tc.get("name", "unknown"), "action": "start"}

            # 工具执行完毕 → 开始尝试流式（后面可能是最终回答，也可能是过渡）
            elif isinstance(msg, ToolMessage):
                pending = ""
                answering = True
                yield {"type": "tool", "tool": getattr(msg, "name", "unknown"), "action": "end"}

            # AI 文本
            elif isinstance(msg, AIMessageChunk) and msg.content:
                if answering:
                    # 工具后 → 试流式输出（如果后面又来 tool_calls 会 clear）
                    yield {"type": "content", "data": msg.content}
                    has_content = True
                else:
                    # 工具前的思考 → 缓冲（如果后面有 tool_calls 就丢，没有就是直接回答）
                    pending += msg.content

        # 流结束：如果没用到工具但有缓冲 → 直接回答
        if not seen_tools and pending.strip():
            yield {"type": "content", "data": pending}
            has_content = True

        # 无任何内容 → 模型调用失败
        if not has_content:
            yield {"type": "error", "data": "模型暂时无法响应，请稍后重试"}

    async def execute_stream(self, query: str, context_messages: list[dict] | None = None,
                             timeout: int = 120):
        """
        异步版本：将同步 blocking 的 agent 执行丢到线程池，
        通过 asyncio.Queue 将事件流回事件循环，保证高并发下不阻塞其他请求。

        Agent 对 user_id 透明 — 由 contextvars 在请求层注入，run_in_executor 传播到工作线程。
        timeout: 整体执行超时（秒），默认 120 秒，防止 LLM API 挂死
        """
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue(maxsize=50)
        ctx = contextvars.copy_context()  # 捕获当前上下文（含 current_user_id）

        def _worker():
            try:
                for event in self._execute_stream_sync(query, context_messages):
                    loop.call_soon_threadsafe(queue.put_nowait, event)
                loop.call_soon_threadsafe(queue.put_nowait, None)  # 结束信号
            except Exception as e:
                loop.call_soon_threadsafe(queue.put_nowait, e)

        # 在捕获的上下文中执行 worker，确保 current_user_id 在线程池中可用
        loop.run_in_executor(None, lambda: ctx.run(_worker))

        start = loop.time()
        while True:
            remaining = timeout - (loop.time() - start)
            if remaining <= 0:
                raise asyncio.TimeoutError(f"Agent 执行超时（{timeout}秒），请稍后重试")

            try:
                item = await asyncio.wait_for(queue.get(), timeout=remaining)
            except asyncio.TimeoutError:
                raise asyncio.TimeoutError(f"Agent 执行超时（{timeout}秒），请稍后重试")

            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            yield item
