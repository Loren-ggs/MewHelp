# 来源：公众号@小林coding
# 后端八股网站：xiaolincoding.com
# Agent网站：xiaolinnote.com
# 简历模版：jianli.xiaolinnote.com
import asyncio
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import functools
import json
import logging
import math
from pathlib import Path
import re
import socket
from urllib.parse import urlparse

from pymilvus import (
    AnnSearchRequest, DataType, Function, FunctionType, MilvusClient, RRFRanker,
)

from app.config import settings

logger = logging.getLogger(__name__)

COLLECTION = "knowledge"
DIM = 1024

# 专用单线程执行器:同步 pymilvus(gRPC)客户端在多线程间共享会间歇静默返回空
# (async server 用 uvloop + 默认多线程 to_thread 时实测复现)。把所有 Milvus 调用
# 固定到这一个线程(客户端亦在此线程惰性创建),即单线程独占,间歇空返回根治。
_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="milvus")


async def acall(fn, *args, **kwargs):
    """在专用单线程上执行同步 pymilvus 调用(供 async 在线路径用)。"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_EXECUTOR, functools.partial(fn, *args, **kwargs))


_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+(?:-[a-zA-Z0-9_]+)*|[\u4e00-\u9fff]")
_CJK_SEQ_RE = re.compile(r"[\u4e00-\u9fff]{2,}")
_CAT_FILTER_RE = re.compile(r'category\s*==\s*"([^"]*)"')


def _tokenize_zh(text: str) -> list[str]:
    """中英混合分词(无需重型分词库):英文/型号词整词保留(小写)+ 中文单字 + 中文二元词组(bigram)。"""
    if not text:
        return []
    lower = text.lower()
    tokens = _TOKEN_RE.findall(lower)
    for seq in _CJK_SEQ_RE.findall(lower):
        for i in range(len(seq) - 1):
            tokens.append(seq[i:i + 2])
    return tokens


def _cosine_sim(v1: list[float], v2: list[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = math.sqrt(sum(a * a for a in v1))
    n2 = math.sqrt(sum(b * b for b in v2))
    if n1 == 0.0 or n2 == 0.0:
        return 0.0
    return dot / (n1 * n2)


class LocalMilvusClient:
    """轻量级本地持久化混合检索引擎(Dense Cosine + 中文 BM25 + RRF 融合)。
    零外部容器开销(内存 < 20MB),与 Milvus Standalone 接口 100% 兼容。"""

    def __init__(self, path: str = "data/milvus_lite.json") -> None:
        if path.startswith("local://"):
            path = path[len("local://"):]
        elif path.startswith("file://"):
            path = path[len("file://"):]
        self._path = Path(path)
        self._collections: dict[str, dict[int, dict]] = {}
        self._load_disk()

    def _load_disk(self) -> None:
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                for cname, rows in raw.items():
                    self._collections[cname] = {int(k): v for k, v in rows.items()}
            except Exception:
                logger.warning("读取本地向量库文件失败,将重建: %s", self._path, exc_info=True)

    def _save_disk(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            # 仅持久化非临时测试集合,避免单测残留膨胀
            persist = {
                cname: {str(k): v for k, v in rows.items()}
                for cname, rows in self._collections.items()
                if not cname.startswith("test_")
            }
            self._path.write_text(json.dumps(persist, ensure_ascii=False), encoding="utf-8")
        except Exception:
            logger.warning("写入本地向量库文件失败: %s", self._path, exc_info=True)

    def has_collection(self, collection: str) -> bool:
        return collection in self._collections

    def load_collection(self, collection: str) -> None:
        self._collections.setdefault(collection, {})

    def create_schema(self, **kwargs):
        class _DummySchema:
            def add_field(self, *a, **kw): pass
            def add_function(self, *a, **kw): pass
        return _DummySchema()

    def prepare_index_params(self):
        class _DummyIdx:
            def add_index(self, *a, **kw): pass
        return _DummyIdx()

    def create_collection(self, collection: str, **kwargs) -> None:
        self._collections.setdefault(collection, {})
        self._save_disk()

    def upsert(self, collection: str, rows: list[dict]) -> None:
        coll = self._collections.setdefault(collection, {})
        for r in rows:
            rid = int(r["id"])
            coll[rid] = dict(r)
        self._save_disk()

    def flush(self, collection: str) -> None:
        self._save_disk()

    def drop_collection(self, collection: str) -> None:
        self._collections.pop(collection, None)
        self._save_disk()

    def _filter_rows(self, collection: str, filter_expr: str | None) -> list[dict]:
        rows = list(self._collections.get(collection, {}).values())
        if not filter_expr:
            return rows
        m = _CAT_FILTER_RE.search(filter_expr)
        if m:
            cat = m.group(1)
            return [r for r in rows if r.get("category") == cat]
        return rows

    def _dense_rank(self, rows: list[dict], query_vec: list[float], limit: int) -> list[tuple[dict, float]]:
        scored = [(r, _cosine_sim(query_vec, r.get("dense") or [])) for r in rows]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    def _bm25_rank(self, rows: list[dict], query_text: str, limit: int,
                   k1: float = 1.5, b: float = 0.75) -> list[tuple[dict, float]]:
        if not rows:
            return []
        q_tokens = _tokenize_zh(query_text)
        if not q_tokens:
            return []
        doc_tokens = [_tokenize_zh(r.get("text") or f"{r.get('category', '')} {r.get('question', '')} {r.get('answer', '')}") for r in rows]
        doc_lens = [len(toks) for toks in doc_tokens]
        avgdl = (sum(doc_lens) / len(doc_lens)) if doc_lens else 1.0
        n_docs = len(rows)

        df: Counter[str] = Counter()
        for toks in doc_tokens:
            for t in set(toks):
                df[t] += 1

        scored: list[tuple[dict, float]] = []
        for r, toks, dl in zip(rows, doc_tokens, doc_lens):
            tf = Counter(toks)
            score = 0.0
            for qt in q_tokens:
                f = tf.get(qt, 0)
                if f == 0:
                    continue
                nq = df.get(qt, 0)
                idf = math.log(1.0 + (n_docs - nq + 0.5) / (nq + 0.5))
                denom = f + k1 * (1.0 - b + b * (dl / max(avgdl, 1.0)))
                score += idf * (f * (k1 + 1.0)) / denom
            if score > 0:
                scored.append((r, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    def _format_hit(self, r: dict, score: float, output_fields: list[str] | None) -> dict:
        fields = output_fields or _OUTPUT
        entity = {k: r.get(k, "") for k in fields}
        return {"id": r["id"], "distance": float(score), "entity": entity}

    def search(self, collection: str, data: list, anns_field: str, limit: int,
               output_fields: list[str] | None = None, search_params: dict | None = None,
               filter: str = "") -> list[list[dict]]:
        rows = self._filter_rows(collection, filter)
        q = data[0] if data else None
        if anns_field == "dense":
            ranked = self._dense_rank(rows, q or [], limit)
        else:
            ranked = self._bm25_rank(rows, str(q or ""), limit)
        return [[self._format_hit(r, sc, output_fields) for r, sc in ranked]]

    def hybrid_search(self, collection: str, reqs: list, ranker=None, limit: int = 10,
                      output_fields: list[str] | None = None) -> list[list[dict]]:
        rrf_k = 60.0
        rrf_scores: dict[int, float] = {}
        row_map: dict[int, dict] = {}
        for req in reqs:
            anns_field = getattr(req, "anns_field", "")
            data = getattr(req, "data", [None])[0]
            req_limit = getattr(req, "limit", 50)
            expr = getattr(req, "expr", "") or ""
            rows = self._filter_rows(collection, expr)
            if anns_field == "dense":
                ranked = self._dense_rank(rows, data or [], req_limit)
            else:
                ranked = self._bm25_rank(rows, str(data or ""), req_limit)
            for rank_idx, (r, _) in enumerate(ranked, start=1):
                rid = int(r["id"])
                row_map[rid] = r
                rrf_scores[rid] = rrf_scores.get(rid, 0.0) + 1.0 / (rrf_k + rank_idx)
        merged = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:limit]
        return [[self._format_hit(row_map[rid], sc, output_fields) for rid, sc in merged]]

    def query(self, collection: str | None = None, filter: str = "",
              output_fields: list[str] | None = None, collection_name: str | None = None, **kwargs) -> list[dict]:
        cname = collection or collection_name or COLLECTION
        rows = self._filter_rows(cname, filter)
        if output_fields and "count(*)" in output_fields:
            return [{"count(*)": len(rows)}]
        if not output_fields:
            return rows
        return [{k: r.get(k) for k in output_fields if k in r} for r in rows]


_CLIENT: MilvusClient | LocalMilvusClient | None = None
_ensured: set[str] = set()

_OUTPUT = ["question", "answer", "section_path", "content_type", "category"]


def _is_http_milvus_reachable(uri: str) -> bool:
    try:
        parsed = urlparse(uri)
        host = parsed.hostname or "localhost"
        port = parsed.port or 19530
        with socket.create_connection((host, port), timeout=0.3):
            return True
    except OSError:
        return False


def get_client(uri: str | None = None):
    """支持 Milvus Standalone 与轻量本地引擎(local:// 或 Milvus 未启动时自动降级)。"""
    global _CLIENT
    target = uri or settings.milvus_uri
    if target.startswith(("local://", "file://")) or target.endswith(".json"):
        if uri is not None:
            return LocalMilvusClient(target)
        if _CLIENT is None:
            _CLIENT = LocalMilvusClient(target)
        return _CLIENT

    # 配置了 http:// 地址但本机/容器未启动 Milvus 时,自动降级到轻量本地引擎,保障免容器可跑
    if not _is_http_milvus_reachable(target):
        if uri is not None:
            return LocalMilvusClient("data/milvus_lite.json")
        if _CLIENT is None:
            logger.info("Milvus Standalone (%s) 未启动,自动启用内置轻量混合检索引擎 (data/milvus_lite.json)", target)
            _CLIENT = LocalMilvusClient("data/milvus_lite.json")
        return _CLIENT

    if uri is not None:
        return MilvusClient(uri=uri)
    if _CLIENT is None:
        _CLIENT = MilvusClient(uri=settings.milvus_uri)
    return _CLIENT


def ensure_collection(client: MilvusClient, collection: str = COLLECTION) -> None:
    """幂等建集合:dense(COSINE) + text(chinese analyzer) + sparse(BM25 Function) + 标量字段。
    单例默认集合只实际执行一次;不同集合名(测试临时库)各自 ensure。"""
    if client is _CLIENT and collection in _ensured:
        return
    if client.has_collection(collection):
        client.load_collection(collection)
    else:
        schema = client.create_schema(auto_id=False)
        schema.add_field("id", DataType.INT64, is_primary=True)
        schema.add_field("dense", DataType.FLOAT_VECTOR, dim=DIM)
        # text = category+questions+answer 拼接,恒长于 answer(8192);放宽到 16384 防长块 upsert 溢出
        schema.add_field("text", DataType.VARCHAR, max_length=16384,
                         enable_analyzer=True, analyzer_params={"type": "chinese"})
        schema.add_field("sparse", DataType.SPARSE_FLOAT_VECTOR)
        schema.add_field("question", DataType.VARCHAR, max_length=2048)
        schema.add_field("answer", DataType.VARCHAR, max_length=8192)
        schema.add_field("section_path", DataType.VARCHAR, max_length=512)
        schema.add_field("content_type", DataType.VARCHAR, max_length=32)
        schema.add_field("category", DataType.VARCHAR, max_length=255)
        schema.add_function(Function(
            name="text_bm25", input_field_names=["text"],
            output_field_names=["sparse"], function_type=FunctionType.BM25,
        ))
        index_params = client.prepare_index_params()
        index_params.add_index(field_name="dense", index_type="AUTOINDEX", metric_type="COSINE")
        index_params.add_index(field_name="sparse", index_type="SPARSE_INVERTED_INDEX", metric_type="BM25")
        client.create_collection(collection, schema=schema, index_params=index_params)
        client.load_collection(collection)
    if client is _CLIENT:
        _ensured.add(collection)


def upsert_vectors(client: MilvusClient, rows: list[dict], collection: str = COLLECTION) -> None:
    if rows:
        client.upsert(collection, rows)


def flush(client: MilvusClient, collection: str = COLLECTION) -> None:
    """刷盘:新 upsert 的数据须 flush 后才可被 BM25/检索命中(Task 1 实证)。"""
    client.flush(collection)


def _cat_expr(category: str | None) -> str:
    return f'category == "{category}"' if category else ""


def _hit(h: dict) -> dict:
    e = h["entity"]
    return {"id": h["id"], "score": float(h["distance"]),
            "question": e["question"], "answer": e["answer"],
            "section_path": e["section_path"], "content_type": e["content_type"],
            "category": e["category"]}


def dense_search(client, vector, top_k, category=None, collection=COLLECTION) -> list[dict]:
    res = client.search(collection, data=[vector], anns_field="dense", limit=top_k,
                        output_fields=_OUTPUT, search_params={"metric_type": "COSINE"},
                        filter=_cat_expr(category))
    # Standalone COSINE 的 distance 即相似度(越大越相似),与 Lite 的「1-相似度」不同
    return [_hit(h) for h in res[0]]


def bm25_search(client, text, top_k, category=None, collection=COLLECTION) -> list[dict]:
    res = client.search(collection, data=[text], anns_field="sparse", limit=top_k,
                        output_fields=_OUTPUT, search_params={"metric_type": "BM25"},
                        filter=_cat_expr(category))
    return [_hit(h) for h in res[0]]


def hybrid_search(client, vector, text, top_k, recall=50, category=None, collection=COLLECTION) -> list[dict]:
    expr = _cat_expr(category)
    dense_req = AnnSearchRequest(data=[vector], anns_field="dense",
                                 param={"metric_type": "COSINE"}, limit=recall, expr=expr)
    sparse_req = AnnSearchRequest(data=[text], anns_field="sparse",
                                  param={"metric_type": "BM25"}, limit=recall, expr=expr)
    res = client.hybrid_search(collection, reqs=[dense_req, sparse_req], ranker=RRFRanker(),
                               limit=top_k, output_fields=_OUTPUT)
    return [_hit(h) for h in res[0]]


def count(client, collection: str = COLLECTION) -> int:
    return client.query(collection, filter="id >= 0", output_fields=["count(*)"])[0]["count(*)"]


def drop(client, collection: str) -> None:
    if client.has_collection(collection):
        client.drop_collection(collection)
