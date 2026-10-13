"""Smoke tests — verify the app boots and core infrastructure works."""
import pytest
from httpx import AsyncClient


async def test_health_endpoint(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "environment" in data
