# 来源：公众号@小林coding
# 后端八股网站：xiaolincoding.com
# Agent网站：xiaolinnote.com
# 简历模版：jianli.xiaolinnote.com
from app.core import embeddings
import httpx
import pytest
from openai import BadRequestError


class _FakeEmb:
    def __init__(self, vec):
        self.embedding = vec


class _FakeResp:
    def __init__(self, vecs):
        self.data = [_FakeEmb(v) for v in vecs]


class _FakeEmbeddings:
    def __init__(self):
        self.calls = []

    async def create(self, model, input):
        self.calls.append((model, list(input)))
        return _FakeResp([[float(i), 0.0, 1.0] for i, _ in enumerate(input)])


class _FakeClient:
    def __init__(self):
        self.embeddings = _FakeEmbeddings()


async def test_embed_texts_passes_model_and_input(monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr(embeddings, "_client", lambda: fake)
    out = await embeddings.embed_texts(["a", "b"])
    assert out == [[0.0, 0.0, 1.0], [1.0, 0.0, 1.0]]
    assert fake.embeddings.calls == [("BAAI/bge-m3", ["a", "b"])]


async def test_embed_query_returns_single_vector(monkeypatch):
    monkeypatch.setattr(embeddings, "_client", lambda: _FakeClient())
    v = await embeddings.embed_query("邮费")
    assert v == [0.0, 0.0, 1.0]


async def test_embed_retries_upstream_20015_once(monkeypatch):
    fake = _FakeClient()
    original = fake.embeddings.create
    calls = 0

    async def flaky(model, input):
        nonlocal calls
        calls += 1
        if calls == 1:
            response = httpx.Response(400, request=httpx.Request("POST", "https://example.com/embeddings"),
                                      json={"code": 20015, "message": "The parameter is invalid."})
            raise BadRequestError("invalid", response=response, body=response.json())
        return await original(model, input)

    fake.embeddings.create = flaky
    monkeypatch.setattr(embeddings, "_client", lambda: fake)
    async def no_sleep(_):
        return None
    monkeypatch.setattr(embeddings.asyncio, "sleep", no_sleep)

    assert await embeddings.embed_query("运费怎么算") == [0.0, 0.0, 1.0]
    assert calls == 2


async def test_embed_does_not_retry_other_bad_requests(monkeypatch):
    fake = _FakeClient()
    calls = 0

    async def invalid(model, input):
        nonlocal calls
        calls += 1
        response = httpx.Response(400, request=httpx.Request("POST", "https://example.com/embeddings"),
                                  json={"code": 40001, "message": "invalid model"})
        raise BadRequestError("invalid", response=response, body=response.json())

    fake.embeddings.create = invalid
    monkeypatch.setattr(embeddings, "_client", lambda: fake)
    with pytest.raises(BadRequestError):
        await embeddings.embed_query("运费怎么算")
    assert calls == 1
