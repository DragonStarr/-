import httpx

from operator_day.config import Settings
from operator_day.embeddings import EmbeddingService


async def test_embedding_service_uses_openai_compatible_endpoint() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/embeddings"
        body = request.read().decode("utf-8")
        assert "BAAI/bge-m3" in body
        assert request.headers["Authorization"] == "Bearer test-embedding-key"
        return httpx.Response(
            200,
            json={
                "model": "BAAI/bge-m3",
                "data": [{"embedding": [0.1, 0.2, 0.3]}],
            },
        )

    service = EmbeddingService(
        Settings(
            embedding_provider="bge-m3-http",
            embedding_model="BAAI/bge-m3",
            embedding_base_url="https://embeddings.example/v1",
            embedding_api_key="test-embedding-key",
        ),
        client_factory=lambda **kwargs: httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            **kwargs,
        ),
    )

    result = await service.embed("маржа товар остаток")

    assert result.model == "BAAI/bge-m3"
    assert result.provider == "bge-m3-http"
    assert result.vector == [0.1, 0.2, 0.3]
    assert result.used_fallback is False


async def test_embedding_service_falls_back_to_local_vector_when_remote_is_unavailable() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "temporarily unavailable"})

    service = EmbeddingService(
        Settings(
            embedding_provider="openai-compatible",
            embedding_model="BAAI/bge-m3",
            embedding_base_url="https://embeddings.example/v1",
            embedding_vector_size=24,
        ),
        client_factory=lambda **kwargs: httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            **kwargs,
        ),
    )

    result = await service.embed("поиск памяти")

    assert result.model == "BAAI/bge-m3:local-hash-fallback"
    assert result.provider == "local"
    assert len(result.vector) == 24
    assert result.used_fallback is True
