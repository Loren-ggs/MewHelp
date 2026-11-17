# 来源：公众号@小林coding
# 后端八股网站：xiaolincoding.com
# Agent网站：xiaolinnote.com
# 简历模版：jianli.xiaolinnote.com
from collections import deque
from collections.abc import AsyncIterator
import json
import logging
import sys
import time

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.graph import runtime
from app.schemas.chat import ChatRequest

logger = logging.getLogger(__name__)
router = APIRouter()

_ip_minute_hits: dict[str, deque[float]] = {}
_daily_hits: deque[float] = deque()


def _check_rate_limit(req: Request) -> str | None:
    """公网演示防刷限流:单 IP 每分钟上限 + 全局每日上限(单测与评测脚本环境下自动豁免)。"""
    if "pytest" in sys.modules:
        return None
    now = time.time()
    if settings.rate_limit_per_day > 0:
        while _daily_hits and now - _daily_hits[0] > 86400:
            _daily_hits.popleft()
        if len(_daily_hits) >= settings.rate_limit_per_day:
            return "演示站点今日公共体验额度已达上限，请明日再试或克隆仓库本地运行~"

    if settings.rate_limit_per_minute > 0:
        xff = req.headers.get("x-forwarded-for", "")
        ip = xff.split(",")[0].strip() if xff else (req.client.host if req.client else "unknown")
        q = _ip_minute_hits.setdefault(ip, deque())
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= settings.rate_limit_per_minute:
            return "提问太频繁啦，请休息一下稍后再试~"
        q.append(now)

    if settings.rate_limit_per_day > 0:
        _daily_hits.append(now)
    return None


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _sse_error(message: str) -> AsyncIterator[str]:
    yield "event: error\n"
    yield _sse({"message": message})


@router.post("/api/chat")
async def chat(req: ChatRequest, request: Request):
    limit_msg = _check_rate_limit(request)

    async def event_stream() -> AsyncIterator[str]:
        if limit_msg:
            for f in _sse_error(limit_msg):
                yield f
            return
        try:
            async for ev in runtime.stream_turn(req.user_id, req.message, req.conversation_id):
                if ev["type"] == "tool":
                    yield _sse({"event": "tool", "name": ev["name"]})
                elif ev["type"] == "delta":
                    yield _sse({"delta": ev["text"]})
                elif ev["type"] == "citations":
                    yield _sse({"event": "citations", "items": ev["items"]})
                elif ev["type"] == "interrupt":
                    # ch08:负载透传(select_order 带 orders / confirm_ticket 带 preview),前端按 kind 分发
                    yield _sse({"event": "interrupt",
                                **{k: v for k, v in ev.items() if k != "type"}})
                elif ev["type"] == "actions":
                    yield _sse({"event": "actions", "items": ev["items"]})
                elif ev["type"] == "done":
                    yield _sse({"event": "done", "conversation_id": ev["conversation_id"]})
        except runtime.ConversationNotFound:
            for f in _sse_error("会话不存在"):
                yield f
            return
        except SQLAlchemyError:
            logger.exception("数据库错误 user_id=%s", req.user_id)
            for f in _sse_error("数据库暂时不可用,请稍后重试"):
                yield f
            return
        except Exception:
            logger.exception("图编排失败 user_id=%s", req.user_id)
            for f in _sse_error("上游模型暂时不可用,请稍后重试"):
                yield f
            return
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
