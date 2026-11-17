# 来源：公众号@小林coding
# 后端八股网站：xiaolincoding.com
# Agent网站：xiaolinnote.com
# 简历模版：jianli.xiaolinnote.com
from pathlib import Path
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


def _ensure_sqlite_dir(url: str) -> None:
    if url.startswith("sqlite"):
        parts = url.split("///", 1)
        if len(parts) == 2 and parts[1] and parts[1] != ":memory:":
            db_path = Path(parts[1].split("?", 1)[0])
            db_path.parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_dir(settings.database_url)
_engine_kwargs: dict = {"pool_pre_ping": True}
if not settings.database_url.startswith("sqlite"):
    _engine_kwargs["pool_recycle"] = 1800

engine = create_async_engine(settings.database_url, **_engine_kwargs)
async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, expire_on_commit=False
)


_SEED_FAQS = [
    ("退货政策", "支持 7 天无理由退货,商品需保持完好、不影响二次销售,具体以平台售后规则为准。", "售后"),
    ("如何申请退款", "在「我的订单」找到对应订单点击「申请退款」,按提示提交,审核通过后原路退回。", "售后"),
    ("换货流程", "收到商品 7 天内可申请换货,联系客服登记后将商品寄回,平台核验无误后补发新品。", "售后"),
    ("发货时效", "现货商品付款后 48 小时内发货,预售商品以商品详情页标注的发货时间为准。", "物流"),
    ("运费怎么算", "单笔订单满 99 元包邮,未满收取 10 元运费,偏远地区运费另计。", "物流"),
    ("发票如何开具", "在「我的订单」-「申请开票」提交抬头与税号,电子发票将于 3 个工作日内发送至邮箱。", "账务"),
]


async def init_db() -> None:
    """自动建表并幂等灌入基础演示数据(支持 SQLite 零容器启动与全新 MySQL 实例)。"""
    from app.db import models  # noqa: F401 确保所有 ORM 表注册进 Base.metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as s:
        faq_count = (await s.execute(select(func.count()).select_from(models.Faq))).scalar_one()
        if faq_count == 0:
            for q, a, cat in _SEED_FAQS:
                s.add(models.Faq(question=q, answer=a, category=cat))
            # 预设两条合成历史会话供知识挖掘演示
            c1 = models.Conversation(user_id="seed-u1", status="已结束")
            c2 = models.Conversation(user_id="seed-u2", status="已结束")
            s.add_all([c1, c2])
            await s.flush()
            s.add_all([
                models.Message(conversation_id=c1.id, role="user", content="你们发货一般多久啊"),
                models.Message(conversation_id=c1.id, role="assistant",
                               content="现货商品付款后 48 小时内发货,预售以商品详情页标注时间为准。"),
                models.Message(conversation_id=c2.id, role="user", content="满多少包邮"),
                models.Message(conversation_id=c2.id, role="assistant",
                               content="单笔订单满 99 元包邮,未满收取 10 元运费,偏远地区另计。"),
            ])
            # 预设两条飞轮待审数据供 /review 与 /topics 后台看板展示
            rq1 = models.ReviewQueue(
                normalized_question="智能猫砂盆 Pro 支持 5G Wi-Fi 连接吗？",
                ai_suggested_answer="智能猫砂盆 Pro (型号 MH-LP100) 仅支持 2.4GHz 频段 Wi-Fi，暂不支持 5GHz 频段。若家中路由器为双频合一，建议关闭双频合一或开启 2.4G 独立热点进行配网。",
                occurrence_count=3,
                review_status="待审",
            )
            rq2 = models.ReviewQueue(
                normalized_question="你们店铺有狗狗用的自动喂食器或牵引绳吗？",
                ai_suggested_answer="喵喵优选目前专注猫咪智能硬件与用品（猫砂盆、猫咪饮水机、猫爬架等），暂未上架犬类专用商品。小型犬（体重 ≤ 6kg）可参考使用自动喂食器 MH-FD30，但暂不售卖牵引绳。",
                occurrence_count=2,
                review_status="待审",
            )
            s.add_all([rq1, rq2])
            await s.flush()
            lcq1 = models.LowConfidenceQuestion(
                raw_question="猫砂盆Pro连不上我家5G无线网怎么办",
                source="retrieval_low_conf",
                reason="evidence_confidence=0.182",
                matched_review_id=rq1.id,
            )
            lcq2 = models.LowConfidenceQuestion(
                raw_question="你们卖狗狗吃的冻干和牵引绳吗？",
                source="retrieval_low_conf",
                reason="evidence_confidence=0.095",
                matched_review_id=rq2.id,
            )
            s.add_all([lcq1, lcq2])
            await s.flush()
            s.add_all([
                models.TopicClassification(question_id=lcq1.id, labels=["App联网与配网", "故障排查"]),
                models.TopicClassification(question_id=lcq2.id, labels=["适配与体型", "超纲品类咨询"]),
            ])
            await s.commit()
