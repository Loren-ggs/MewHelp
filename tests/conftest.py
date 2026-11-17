# 来源：公众号@小林coding
# 后端八股网站：xiaolincoding.com
# Agent网站：xiaolinnote.com
# 简历模版：jianli.xiaolinnote.com
import pathlib

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings

_DDL_FILES = [
    pathlib.Path(__file__).resolve().parent.parent / "sql" / "ch02-ddl.sql",
    pathlib.Path(__file__).resolve().parent.parent / "sql" / "ch03-ddl.sql",
    # 挖知识加人工闸:给 qa_extraction_staging 的 status 补 approved/rejected 两个终态
    pathlib.Path(__file__).resolve().parent.parent / "sql" / "ch03-staging-review.sql",
    pathlib.Path(__file__).resolve().parent.parent / "sql" / "ch04-ddl.sql",
    pathlib.Path(__file__).resolve().parent.parent / "sql" / "ch07-ddl.sql",
    # 分层上下文:conversations 加层1 锚点 + 分段摘要表
    pathlib.Path(__file__).resolve().parent.parent / "sql" / "ch07-layers.sql",
    pathlib.Path(__file__).resolve().parent.parent / "sql" / "ch08-ddl.sql",
    pathlib.Path(__file__).resolve().parent.parent / "sql" / "ch09-ddl.sql",
    pathlib.Path(__file__).resolve().parent.parent / "sql" / "ch10-ddl.sql",
]
# 删除顺序:先子表后父表;knowledge_chunks 自引用 FK 靠 FOREIGN_KEY_CHECKS=0 兜
# ch09:low_confidence_questions 有 FK 指向 review_queue,排它前面
# ch10:topic_classifications 有 FK 指向 low_confidence_questions,必须排它前面先删
_TABLES = ["faith_cases", "topic_classifications", "low_confidence_questions", "review_queue", "eval_runs",
           "conversation_summaries",
           "messages", "tickets", "tool_audit_logs", "conversations", "faq",
           "qa_extraction_staging", "knowledge_chunks"]

_TEST_URL = settings.test_database_url
_DB_NAME = _TEST_URL.rsplit("/", 1)[1]
_SERVER_URL = _TEST_URL.rsplit("/", 1)[0]


def _split_sql(sql: str) -> list[str]:
    """按分号切语句,但跳过单引号字符串内的分号(ch09 起 COMMENT 文案里出现 ; 和 :)。"""
    stmts, buf, in_str = [], [], False
    for ch in sql:
        if ch == "'":
            in_str = not in_str   # DDL 注释文案无转义引号,简单开关够用
        if ch == ";" and not in_str:
            stmts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    stmts.append("".join(buf))
    return stmts


def _create_table_stmts() -> list[str]:
    # 先去掉整行注释(-- ...),否则注释里的分号会把语句切错
    stmts: list[str] = []
    for ddl in _DDL_FILES:
        raw = ddl.read_text(encoding="utf-8")
        sql = "\n".join(ln for ln in raw.splitlines() if not ln.lstrip().startswith("--"))
        # ch07 起有 ALTER TABLE(给既有表加列);文件列表顺序保证先 CREATE 后 ALTER
        for s in _split_sql(sql):
            s = s.strip()
            if not s:
                continue
            if s.upper().startswith(("CREATE TABLE", "ALTER TABLE")):
                stmts.append(s)
            elif "CREATE TABLE" in s.upper() or "ALTER TABLE" in s.upper():
                # 切分保险:语句含 CREATE/ALTER 却不以其开头 = 字符串内分号/引号切错,炸响别静默
                raise ValueError(f"DDL 切分异常({ddl.name}): {s[:80]!r}")
    return stmts


@pytest.fixture(autouse=True)
def _no_langfuse(monkeypatch):
    """ch09:测试一律关闭 Langfuse——.env 若配了三变量,graph 测试里的 tag_intent
    会把意图事件真发到本地 Langfuse(0-token 垃圾 trace 污染成本账,实测踩坑)。
    test_observability 里要开的用例自行 monkeypatch 覆盖,不受影响。"""
    monkeypatch.setattr("app.config.settings.langfuse_public_key", "")


@pytest_asyncio.fixture()
async def _test_engine():
    """function 级:确保测试库存在 + 重建全部 ORM 表。支持 SQLite(免容器)与 MySQL 双模式。"""
    from app.db import models  # noqa: F401
    from app.db.base import Base, _ensure_sqlite_dir

    use_sqlite = _TEST_URL.startswith("sqlite")
    if not use_sqlite:
        try:
            admin = create_async_engine(_SERVER_URL, isolation_level="AUTOCOMMIT")
            async with admin.connect() as conn:
                await conn.execute(
                    text(f"CREATE DATABASE IF NOT EXISTS {_DB_NAME} CHARACTER SET utf8mb4")
                )
            await admin.dispose()
        except Exception:
            use_sqlite = True

    if use_sqlite:
        from sqlalchemy import event
        sqlite_url = _TEST_URL if _TEST_URL.startswith("sqlite") else "sqlite+aiosqlite:///data/mewhelp_test.db"
        _ensure_sqlite_dir(sqlite_url)
        engine = create_async_engine(sqlite_url)

        @event.listens_for(engine.sync_engine, "before_cursor_execute", retval=True)
        def _rewrite_mysql_show_tables(conn, cursor, statement, parameters, context, executemany):
            if statement.strip().upper() == "SHOW TABLES":
                statement = "SELECT name FROM sqlite_master WHERE type='table'"
            return statement, parameters

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        yield engine
        await engine.dispose()
        return

    engine = create_async_engine(_TEST_URL, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for t in _TABLES:
            await conn.execute(text(f"DROP TABLE IF EXISTS {t}"))
        await conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        for stmt in _create_table_stmts():
            await conn.exec_driver_sql(stmt)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture()
async def db_session_factory(_test_engine, monkeypatch):
    """把 app.db.base.async_session 指向测试库,并返回该工厂供测试直接开 session。

    repository 内部通过 app.db.base.async_session(模块属性)访问,故 monkeypatch 生效;
    测试要自建 session 时用本 fixture 的返回值,勿在测试模块顶层 from-import async_session。
    """
    factory = async_sessionmaker(_test_engine, expire_on_commit=False)
    monkeypatch.setattr("app.db.base.async_session", factory)
    return factory


@pytest_asyncio.fixture()
async def db_clean():
    """占位:表由 _test_engine 每个测试重建,无需额外清理。保留以兼容测试签名。"""
    yield


@pytest.fixture()
def client():
    """返回 FastAPI TestClient 用于 API 测试(包含 actions 路由)。"""
    from app.api.actions import router as actions_router
    test_app = FastAPI()
    test_app.include_router(actions_router)
    return TestClient(test_app)
