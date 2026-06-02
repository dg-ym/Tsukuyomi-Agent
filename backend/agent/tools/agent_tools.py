import json
import datetime
from utils.logger_handler import logger
from langchain_core.tools import tool
import urllib.request
import urllib.error

from rag.rag_service import RagSummarizeService
from utils.context_vars import current_user_id

# 联网搜索 (Bing + curl_cffi TLS指纹模拟)
from bs4 import BeautifulSoup

rag = RagSummarizeService()
external_data = {}


@tool(description="从当前用户的知识库中检索参考资料。只有模型自身知识无法回答时调用")
def rag_summarize(query: str) -> str:
    user_id = current_user_id.get()
    if user_id is None:
        return "用户未登录，无法检索知识库"
    return rag.rag_summarize(query, user_id=user_id)


@tool(description="获取指定城市的实时天气数据")
def get_weather(city: str) -> str:
    """调用 wttr.in 免费天气 API"""
    try:
        url = f"https://wttr.in/{urllib.request.quote(city)}?format=j1&lang=zh"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        if "current_condition" not in data:
            return f"未能获取{city}的实时天气数据"

        current = data["current_condition"][0]
        weather_desc = current["weatherDesc"][0]["value"]
        temp = current["temp_C"]
        humidity = current["humidity"]
        wind = current["winddir16Point"]
        wind_speed = current["windspeedKmph"]
        feels_like = current.get("FeelsLikeC", temp)
        obs_time = current.get("observation_time", "未知")

        return (
            f"城市: {city} | 观测时间: {obs_time}\n"
            f"天气: {weather_desc} | 温度: {temp}°C (体感{feels_like}°C)\n"
            f"湿度: {humidity}% | 风向: {wind} | 风速: {wind_speed}km/h"
        )
    except Exception as e:
        logger.warning(f"[get_weather] 获取{city}天气失败: {e}")
        return f"未能获取{city}的实时天气数据（API暂时不可用）"


@tool(description="获取当前登录用户的ID")
def get_user_id() -> str:
    user_id = current_user_id.get()
    if user_id is None:
        return "未登录"
    return str(user_id)


@tool(description="获取当前日期，格式YYYY-MM-DD")
def get_current_month() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d")


@tool(description="获取当前用户所在城市（基于IP定位）")
def get_user_location() -> str:
    """通过 ip-api.com 获取IP所在城市，含完整地域信息做校验"""
    try:
        url = "http://ip-api.com/json/?fields=city,regionName,country"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            city = data.get("city", "")
            region = data.get("regionName", "")
            country = data.get("country", "")
            if city and region:
                return f"{city}, {region}, {country}"
            if city:
                return f"{city}, {country}"
            return f"{region}, {country}" if region else "位置信息不完整"
    except Exception as e:
        logger.warning(f"[get_user_location] IP定位失败: {e}")
        return "无法获取城市位置，请询问用户所在城市"


# ==================== 外部数据工具 ====================

@tool(description="获取当前用户的对话使用统计数据（会话数、消息数、知识库文档数）")
def fetch_external_data() -> str:
    """查询当前用户的真实使用数据"""
    import asyncio
    from models import AsyncSessionFactory
    from respository.chat_history_repo import SessionRepository, MessageRepository
    from models.user_file import UserDocument
    from sqlalchemy import select, func

    async def _query():
        uid = current_user_id.get()
        if not uid:
            return "用户未登录"

        db = AsyncSessionFactory()
        try:
            session_repo = SessionRepository(db)
            sessions = await session_repo.get_by_user_id(int(uid))
            session_count = len(sessions)

            total_messages = 0
            for sess in sessions[:10]:
                msg_repo = MessageRepository(db)
                msgs = await msg_repo.get_by_session_id(sess.id)
                total_messages += len(msgs)

            result = await db.scalar(
                select(func.count()).select_from(UserDocument).where(UserDocument.user_id == int(uid))
            )
            doc_count = result or 0

            return (
                f"用户使用统计：\n"
                f"- 会话总数: {session_count}\n"
                f"- 消息总数: {total_messages}\n"
                f"- 知识库文档: {doc_count}\n"
                f"- 最近会话: {', '.join(s.title[:15] for s in sessions[:5]) if sessions else '无'}"
            )
        except Exception as e:
            logger.warning(f"[fetch_external_data] 查询失败: {e}")
            return "暂时无法获取使用数据"
        finally:
            await db.close()

    return asyncio.run(_query())


@tool(description="联网搜索最新信息。当模型自身知识和知识库都无法回答时调用")
def web_search(query: str) -> str:
    """使用 Bing 搜索，提取核心关键词搜索"""
    import time, re
    from curl_cffi import requests as curl_requests

    # 提取最长中文词作为核心搜索词
    keywords = re.findall(r'[\u4e00-\u9fff]{2,}', query)
    core = max(keywords, key=len) if keywords else query
    logger.info(f"[web_search] query='{query}' -> core='{core}'")

    url = f"https://cn.bing.com/search?q={urllib.request.quote(core)}&setlang=zh-cn"

    for attempt in range(2):
        try:
            resp = curl_requests.get(url, impersonate="chrome120", timeout=15)
            if resp.status_code != 200:
                if attempt < 1:
                    time.sleep(1)
                    continue
                return "搜索服务暂不可用"

            soup = BeautifulSoup(resp.text, "html.parser")
            results = []
            seen = set()

            for item in soup.select("li.b_algo"):
                title_el = item.select_one("h2 a")
                snippet_el = item.select_one(".b_caption p, .b_lineclamp2, p")
                if title_el and snippet_el:
                    title = title_el.get_text(strip=True)
                    href = title_el.get("href", "")
                    body = snippet_el.get_text(strip=True)
                    if len(body) >= 10 and title not in seen:
                        seen.add(title)
                        results.append({"title": title, "body": body, "href": href})

            logger.info(f"[web_search] '{core}' -> {len(results)} 条")

            if not results:
                return "未搜索到相关信息"

            return "\n\n".join(
                f"### {r['title']}\n{r['body']}\n\n> 来源: {r['href']}"
                for r in results[:8]
            )

        except Exception as e:
            logger.error(f"[web_search] '{core}' attempt {attempt+1}: {e}")
            if attempt < 1:
                time.sleep(1)
            else:
                return "联网搜索暂时不可用，请稍后重试"


@tool(description="无入参，调用后触发报告生成模式。仅当用户明确要求生成个人使用报告时调用")
def fill_context_for_report() -> str:
    return "已切换到报告生成模式"
