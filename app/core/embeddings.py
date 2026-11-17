# 来源：公众号@小林coding
# 后端八股网站：xiaolincoding.com
# Agent网站：xiaolinnote.com
# 简历模版：jianli.xiaolinnote.com
import asyncio

from openai import AsyncOpenAI, BadRequestError

from app.config import settings

_CLIENT: AsyncOpenAI | None = None


def _client() -> AsyncOpenAI:
    """直连嵌入上游(硅基流动的 bge-m3,OpenAI 兼容)。
    进程内单例:复用同一 httpx 连接池,避免每次 embed 新建客户端累积连接/fd。"""
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = AsyncOpenAI(base_url=settings.embed_base_url, api_key=settings.embed_api_key)
    return _CLIENT


async def embed_texts(texts: list[str]) -> list[list[float]]:
    for attempt in range(3):
        try:
            resp = await _client().embeddings.create(model=settings.embed_model, input=texts)
            return [d.embedding for d in resp.data]
        except BadRequestError as exc:
            # 上游偶发将同一合法输入报成 20015;只重试这一种错误,持续失败仍抛出。
            if exc.code != 20015 or attempt == 2:
                raise
            await asyncio.sleep(0.5 * (attempt + 1))


async def embed_query(text: str) -> list[float]:
    return (await embed_texts([text]))[0]
