from app.services.rate_limit import RateLimitService


async def test_shared_rate_limit_counter_and_window(session_factory):
    limiter = RateLimitService(session_factory)
    assert await limiter.hit("login", "192.0.2.10", 2, 60) == 1
    assert await limiter.hit("login", "192.0.2.10", 2, 60) == 2
    assert await limiter.hit("login", "192.0.2.10", 2, 60) == 3
    assert await limiter.hit("login", "192.0.2.11", 2, 60) == 1
    assert RateLimitService.hash_identity("192.0.2.10") != "192.0.2.10"
