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

    def execute_stream(self, query: str, context_messages: list[dict] | None = None):
        messages = []
        if context_messages:
            messages.extend(context_messages)
        messages.append({"role": "user", "content": query})

        print(f"[MEMORY] execute_stream 收到 {len(messages)} 条消息（含历史{len(context_messages or [])}条+当前用户消息）")
        input_dict = {"messages": messages}

        seen_tools = False
        answering = False
        pending = ""

        for event in self.agent.stream(input_dict, stream_mode="messages", context={"report": False}):
            if isinstance(event, tuple):
                msg = event[0]
            else:
                msg = event

            # 工具调用 → 丢弃缓冲
            if isinstance(msg, AIMessageChunk) and msg.tool_calls:
                seen_tools = True
                pending = ""
                for tc in msg.tool_calls:
                    yield {"type": "tool", "tool": tc.get("name", "unknown"), "action": "start"}

            # 工具结果 → 清空缓冲，进入回答模式
            elif isinstance(msg, ToolMessage):
                pending = ""
                answering = True
                yield {"type": "tool", "tool": getattr(msg, "name", "unknown"), "action": "end"}

            # AI 文本 → 缓冲
            elif isinstance(msg, AIMessageChunk) and msg.content:
                pending += msg.content

        # 流结束，输出缓冲中的回答
        if pending.strip():
            yield {"type": "content", "data": pending}
