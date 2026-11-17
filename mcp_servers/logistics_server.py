# 来源：公众号@小林coding
# 后端八股网站：xiaolincoding.com
# Agent网站：xiaolinnote.com
# 简历模版：jianli.xiaolinnote.com
"""物流 MCP Server(ch08 自建,mock 数据,不接真实系统、不建表)。
独立进程:uv run python mcp_servers/logistics_server.py
验收 6:MOCK_DELAY_SECONDS=12 起进程 → 每次工具调用慢 12 秒,客服侧看超时/重试/审计。
实装 mcp==1.28.1:FastMCP(name, host=, port=) + run(transport="streamable-http"),路径默认 /mcp。"""
import asyncio
import os
import random
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP("logistics",
              host="127.0.0.1", port=int(os.environ.get("PORT", "8101")))

_DELAY = float(os.environ.get("MOCK_DELAY_SECONDS", "0"))
_STATUS_CODES = ["PICKED_UP", "IN_TRANSIT", "DELIVERING", "DELIVERED"]  # 内部枚举码,client 侧翻人话
_CITIES = ["深圳", "广州", "杭州", "上海", "成都"]

# 与 DEMO_ORDER_SCENARIOS 100% 联动的剧本物流数据
_SCENARIO_LOGISTICS: dict[str, dict] = {
    "SF1001888999": {
        "tracking_no": "SF1001888999",
        "status_code": "IN_TRANSIT",
        "current_city": "杭州",
        "trace": [
            "2026-11-14 16:30 [深圳宝安揽投部] 顺丰速运已收取快件",
            "2026-11-15 03:15 [深圳华南转运中心] 快件已发车，下一站 杭州萧山分拨中心",
            "2026-11-16 08:40 [杭州萧山分拨中心] 快件已完成分拣，正发往 上海虹桥集散中心（预计明日送达）",
        ],
        "carrier_code": "SF-EXP-01",
    },
    "SF1002666888": {
        "tracking_no": "SF1002666888",
        "status_code": "DELIVERED",
        "current_city": "上海",
        "trace": [
            "2026-11-12 11:00 [广州白云集散中心] 快件已发出",
            "2026-11-13 08:20 [上海徐汇营业点] 派件员【张师傅 13800138000】正在派件",
            "2026-11-13 14:15 [上海] 已签收（丰巢智能柜代签收，签收未满7天）",
        ],
        "carrier_code": "SF-EXP-01",
    },
    "SF1003555777": {
        "tracking_no": "SF1003555777",
        "status_code": "DELIVERED",
        "current_city": "上海",
        "trace": [
            "2026-10-20 20:00 [深圳集散中心] 快件已发出",
            "2026-10-21 16:40 [上海] 本人已签收（签收已满26天）",
        ],
        "carrier_code": "SF-EXP-01",
    },
    "SF1004333111": {
        "tracking_no": "SF1004333111",
        "status_code": "DELIVERED",
        "current_city": "上海",
        "trace": [
            "2026-11-10 13:00 [杭州转运中心] 快件已发出",
            "2026-11-11 11:20 [上海] 已签收（后续已发起退货寄回，退货单号 SF-RET-9004）",
        ],
        "carrier_code": "SF-EXP-01",
    },
    "SF2002999000": {
        "tracking_no": "SF2002999000",
        "status_code": "DELIVERED",
        "current_city": "杭州",
        "trace": [
            "2026-11-12 12:00 [广州分拨中心] 已发出",
            "2026-11-13 15:30 [杭州] 已签收",
        ],
        "carrier_code": "SF-EXP-01",
    },
}


@mcp.tool()
async def query_logistics(
    tracking_no: Annotated[str, Field(description="物流单号(形如 SF 开头),需先用 query_order 查订单拿到该单号")],
) -> dict:
    """用物流单号(tracking_no)查询物流状态、当前位置和轨迹。用于用户询问物流/快递到哪了时。
    物流单号不是订单号,需先用 query_order 查订单拿到 tracking_no,再调用本工具。"""
    if _DELAY > 0:
        await asyncio.sleep(_DELAY)
    if tracking_no in _SCENARIO_LOGISTICS:
        return dict(_SCENARIO_LOGISTICS[tracking_no])
    rng = random.Random(f"logistics:{tracking_no}")      # 种子固定 → 同单号稳定
    code = rng.choice(_STATUS_CODES)
    city = rng.choice(_CITIES)
    return {
        "tracking_no": tracking_no,
        "status_code": code,                              # 内部枚举码,Server 侧不翻译,交 client 侧治理
        "current_city": city,
        "trace": [f"{city}分拨中心 已发出", f"内部状态码:{code}"],
        "carrier_code": "SF-EXP-01",                      # 内部承运商编码(回答用不上,client 侧应剔除)
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
