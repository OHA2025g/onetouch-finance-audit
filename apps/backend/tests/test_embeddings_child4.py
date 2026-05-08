from app.embeddings.providers import HashEmbeddingProvider, cosine


def test_hash_embedding_is_deterministic() -> None:
    import asyncio

    p = HashEmbeddingProvider()
    a = asyncio.run(p.embed(["hello"]))[0]
    b = asyncio.run(p.embed(["hello"]))[0]
    c = asyncio.run(p.embed(["world"]))[0]
    assert a == b
    assert len(a) == p.dim
    assert cosine(a, a) > cosine(a, c)

