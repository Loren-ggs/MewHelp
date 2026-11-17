# 来源：公众号@小林coding
# 后端八股网站：xiaolincoding.com
# Agent网站：xiaolinnote.com
# 简历模版：jianli.xiaolinnote.com
"""剧本级模拟业务数据源(与 data/kb/product-specs.md 100% 对齐,同时向下兼容随机种子兜底)。"""
import random

# 6 款主打商品 + 配套耗材/周边(与知识库规格手册完全对齐)
PRODUCT_CATALOG: list[dict] = [
    {
        "product_id": "MH-LP100",
        "product_name": "智能猫砂盆 Pro",
        "model": "MH-LP100",
        "price": 1299,
        "stock": 42,
        "spec": "标准装 (9L猫砂仓 / App远程智联 / 适用1.5-8kg)",
        "category": "智能清洁",
        "warranty": "12个月整机质保",
        "highlight": "自动感应清理、活性炭除臭、App远程监控与猫咪如厕健康记录",
        "keywords": ["猫砂盆 pro", "mh-lp100", "lp100", "猫砂盆pro", "智能猫砂盆"],
    },
    {
        "product_id": "MH-LP50",
        "product_name": "智能猫砂盆 Lite",
        "model": "MH-LP50",
        "price": 699,
        "stock": 85,
        "spec": "标准装 (6L猫砂仓 / 物理除臭 / 无App联网)",
        "category": "智能清洁",
        "warranty": "12个月整机质保",
        "highlight": "高性价比入门款，自动感应清理、物理除臭盖板，适合单猫家庭",
        "keywords": ["猫砂盆 lite", "mh-lp50", "lp50", "猫砂盆lite", "入门猫砂盆"],
    },
    {
        "product_id": "MH-W40",
        "product_name": "自动饮水机 Plus",
        "model": "MH-W40",
        "price": 249,
        "stock": 120,
        "spec": "标准装 (4L水箱 / UV紫外杀菌 / 五重过滤)",
        "category": "智能饮水",
        "warranty": "12个月整机质保",
        "highlight": "UV紫外杀菌 + 五重过滤棉 + 静音变频水泵，支持缺水断电保护",
        "keywords": ["饮水机 plus", "mh-w40", "w40", "自动饮水机", "饮水机"],
    },
    {
        "product_id": "MH-FD30",
        "product_name": "自动喂食器 摄像头版",
        "model": "MH-FD30",
        "price": 499,
        "stock": 36,
        "spec": "标准装 (6L粮桶 / 1080P夜视摄像头 / 双供电)",
        "category": "智能喂养",
        "warranty": "12个月整机质保",
        "highlight": "1080P视频看护、双向语音、App远程投喂，断电内置电池续航48小时",
        "keywords": ["喂食器", "mh-fd30", "fd30", "自动喂食器", "摄像头喂食器"],
    },
    {
        "product_id": "MH-CAM1",
        "product_name": "全景看护摄像头",
        "model": "MH-CAM1",
        "price": 199,
        "stock": 64,
        "spec": "标准装 (2K超清云台 / 355°旋转 / 逗猫激光)",
        "category": "智能看护",
        "warranty": "12个月整机质保",
        "highlight": "独立全景看护摄像头，支持移动侦测、夜视、双向语音与远程逗猫激光",
        "keywords": ["摄像头", "mh-cam1", "cam1", "全景看护摄像头", "看护摄像头", "监控"],
    },
    {
        "product_id": "MH-HP20",
        "product_name": "大号三档加热垫",
        "model": "MH-HP20",
        "price": 129,
        "stock": 0,
        "spec": "大号装 (60×45cm / 30-38-45℃三档调温)",
        "category": "猫咪居家",
        "warranty": "12个月质保",
        "highlight": "三档可调温控、防抓咬电线套管、表面绒布可拆洗（当前热销暂时缺货）",
        "keywords": ["加热垫", "mh-hp20", "hp20", "保暖垫", "电热垫"],
    },
    {
        "product_id": "MH-LP200",
        "product_name": "智能猫砂盆 Max",
        "model": "MH-LP200",
        "price": 1699,
        "stock": 18,
        "spec": "家庭装 (12L超大滚筒 / 适用2-12kg缅因及多猫家庭)",
        "category": "智能清洁",
        "warranty": "12个月整机质保",
        "highlight": "12L超大容量、双重称重防夹、App多猫健康档案",
        "keywords": ["猫砂盆 max", "mh-lp200", "lp200", "大号猫砂盆"],
    },
    {
        "product_id": "MH-NEST20",
        "product_name": "四季保暖猫窝",
        "model": "MH-NEST20",
        "price": 159,
        "stock": 73,
        "spec": "标准装 (直径50cm / 可拆内垫 / 适用8kg内)",
        "category": "猫咪居家",
        "warranty": "12个月质保",
        "highlight": "外层亲肤短毛绒，内部垫芯可拆卸（外套可手洗，垫芯不可机洗）",
        "keywords": ["猫窝", "mh-nest20", "nest20", "保暖猫窝"],
    },
    {
        "product_id": "MH-FOOD05",
        "product_name": "全价无谷冻干猫粮 5kg",
        "model": "MH-FOOD05",
        "price": 198,
        "stock": 210,
        "spec": "家庭装 (5kg大袋 / 82%动物蛋白 + 冻干鸡肉粒)",
        "category": "猫咪主粮",
        "warranty": "保质期18个月（未拆封支持7天无理由）",
        "highlight": "鲜鸡肉单一肉源低敏配方，粗蛋白≥42%，全阶段成幼猫通用",
        "keywords": ["猫粮", "冻干猫粮", "全价猫粮", "mh-food05"],
    },
]

# 剧本级演示订单:覆盖「查物流」「7天内可退」「超7天保修期内」「退货处理中」四大核心客服场景
DEMO_ORDER_SCENARIOS: dict[str, dict] = {
    "1001": {
        "order_id": "1001",
        "status": "已发货",
        "amount": 1299,
        "created_at": "2026-11-14 14:20",
        "product": "智能猫砂盆 Pro (MH-LP100)",
        "tracking_no": "SF1001888999",
        "scene_tag": "运输中·查物流",
        "scene_desc": "已从杭州分拨中心发出，顺丰运输中",
    },
    "1002": {
        "order_id": "1002",
        "status": "已签收",
        "amount": 249,
        "created_at": "2026-11-13 09:30",
        "product": "自动饮水机 Plus (MH-W40)",
        "tracking_no": "SF1002666888",
        "scene_tag": "签收3天·可无理由退货",
        "scene_desc": "签收未满 7 天且包装完好，符合七天无理由退货条件",
    },
    "1003": {
        "order_id": "1003",
        "status": "已签收",
        "amount": 499,
        "created_at": "2026-10-20 19:15",
        "product": "自动喂食器 摄像头版 (MH-FD30)",
        "tracking_no": "SF1003555777",
        "scene_tag": "签收26天·超退货期但在保",
        "scene_desc": "已拆封使用超 7 天无理由期限，但在 12 个月整机保修期内",
    },
    "1004": {
        "order_id": "1004",
        "status": "已签收",
        "amount": 159,
        "created_at": "2026-11-10 11:05",
        "product": "四季保暖猫窝 (MH-NEST20)",
        "tracking_no": "SF1004333111",
        "scene_tag": "售后退货中·查退货进度",
        "scene_desc": "已提交退货并寄回，仓库正在核验退货包裹",
    },
    "2002": {
        "order_id": "2002",
        "status": "已签收",
        "amount": 198,
        "created_at": "2026-11-12 10:00",
        "product": "全价无谷冻干猫粮 5kg",
        "tracking_no": "SF2002999000",
        "scene_tag": "演示备用单",
        "scene_desc": "已签收，未拆封状态",
    },
}

# 课程与在线演示共用单号:每个访客账号名下默认拥有这几笔剧本订单,开箱即测
DEMO_ORDER_IDS = ("1001", "1002", "1003", "1004", "2002")


def lookup_product(product_name: str) -> dict:
    """按商品名称/型号/关键词匹配目录商品;保持调用方传入的 product_name 字段兼容单测。"""
    q = (product_name or "").strip().lower()
    matched = None
    if q:
        # 1. 精确匹配型号或商品名
        for item in PRODUCT_CATALOG:
            if q == item["model"].lower() or q == item["product_name"].lower():
                matched = item
                break
        # 2. 关键词或包含关系匹配
        if matched is None:
            for item in PRODUCT_CATALOG:
                if any(kw in q or q in kw for kw in item["keywords"]) or q in item["product_name"].lower():
                    matched = item
                    break
    if matched is not None:
        return {
            "product_name": product_name,
            "matched_title": f"{matched['product_name']} ({matched['model']})",
            "model": matched["model"],
            "price": matched["price"],
            "stock": matched["stock"],
            "stock_status": "现货充足" if matched["stock"] > 0 else "暂时缺货(预计下周补货)",
            "spec": matched["spec"],
            "warranty": matched["warranty"],
            "highlight": matched["highlight"],
        }
    rng = random.Random(f"product:{product_name}")
    return {
        "product_name": product_name,
        "price": rng.randint(20, 999),
        "stock": rng.randint(0, 500),
        "spec": rng.choice(["标准装", "家庭装", "试用装"]),
    }


def order_snapshot(order_id: str) -> dict:
    """订单快照:剧本订单返回精细编排数据,其余单号走稳定随机种子兜底。"""
    oid = str(order_id)
    if oid in DEMO_ORDER_SCENARIOS:
        s = DEMO_ORDER_SCENARIOS[oid]
        return {
            "order_id": s["order_id"],
            "status": s["status"],
            "amount": s["amount"],
            "created_at": s["created_at"],
            "product": s["product"],
            "tracking_no": s["tracking_no"],
        }
    rng = random.Random(f"order:{oid}")
    return {
        "order_id": oid,
        "status": rng.choice(["待付款", "已付款", "已发货", "已签收"]),
        "amount": rng.randint(50, 2000),
        "created_at": f"2026-07-{rng.randint(1, 12):02d} 10:00",
        "product": rng.choice(["智能猫砂盆", "猫粮 5kg", "猫爬架", "自动饮水机"]),
        "tracking_no": f"SF{rng.randint(10**11, 10**12 - 1)}",
    }


def owns_order(user_id: str, order_id: str) -> bool:
    """这一单是不是这个人的。归属判断只有这一处,工具和节点都调它,不各判各的。"""
    if not user_id or not order_id:
        return False
    return any(o["order_id"] == order_id for o in list_user_orders(user_id))


def list_user_orders(user_id: str) -> list[dict]:
    """按 user_id 稳定列出该用户的订单:5 笔剧本演示单 + 2 笔用户私有单(供越权单测校验)。"""
    rng = random.Random(f"user_orders:{user_id}")
    ids = list(DEMO_ORDER_IDS)
    for _ in range(rng.randint(2, 3)):
        oid = str(rng.randint(3000, 9999))
        if oid not in ids:
            ids.append(oid)
    out = []
    for oid in ids:
        s = order_snapshot(oid)
        item = {
            "order_id": oid,
            "product": s["product"],
            "status": s["status"],
            "amount": s["amount"],
        }
        if oid in DEMO_ORDER_SCENARIOS:
            item["scene_tag"] = DEMO_ORDER_SCENARIOS[oid]["scene_tag"]
            item["created_at"] = DEMO_ORDER_SCENARIOS[oid]["created_at"]
            item["tracking_no"] = DEMO_ORDER_SCENARIOS[oid]["tracking_no"]
        out.append(item)
    return out
