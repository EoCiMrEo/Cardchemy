"""Cross-origin PDF range protocol without broadening browser access."""

import httpx
import pytest

from app.main import create_app
from tests.test_runtime import make_settings


@pytest.mark.asyncio
async def test_pdf_head_range_and_metadata_are_allowed_only_for_configured_origin():
    application = create_app(make_settings(cors_origins="https://cards.example.test"))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://test",
    ) as client:
        for method in ("HEAD", "GET"):
            response = await client.options("/health/live", headers={
                "Origin": "https://cards.example.test",
                "Access-Control-Request-Method": method,
                "Access-Control-Request-Headers": "Authorization,Range",
            })
            assert response.status_code == 200
            assert response.headers["access-control-allow-origin"] == "https://cards.example.test"
        denied = await client.options("/health/live", headers={
            "Origin": "https://other.example.test",
            "Access-Control-Request-Method": "HEAD",
            "Access-Control-Request-Headers": "Authorization,Range",
        })
        assert denied.status_code == 400
        assert "access-control-allow-origin" not in denied.headers
        response = await client.get("/health/live", headers={"Origin": "https://cards.example.test"})
        exposed = {value.strip().casefold() for value in response.headers["access-control-expose-headers"].split(",")}
        assert {"content-length", "content-range", "accept-ranges", "x-pdf-page-count"} <= exposed
