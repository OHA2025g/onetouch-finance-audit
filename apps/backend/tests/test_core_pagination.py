from app.core.pagination import clamp_limit, PaginationParams


def test_clamp_limit_respects_cap() -> None:
    assert clamp_limit(10, default=50, max_limit=200) == 10
    assert clamp_limit(9999, default=50, max_limit=200) == 200
    assert clamp_limit(0, min_limit=1) == 1


def test_pagination_params_mongo() -> None:
    p = PaginationParams(limit=20, offset=40)
    assert p.mongo() == {"limit": 20, "skip": 40}
