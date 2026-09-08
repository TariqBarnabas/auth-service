import uuid
import pytest


@pytest.fixture
def unique_email():
    return f"test-{uuid.uuid4()}@example.com"


async def test_full_auth_flow(client, unique_email):
    password = "TestPassword123"

    response = await client.post("/auth/register", json={"email": unique_email, "password": password})
    assert response.status_code == 201

    response = await client.post("/auth/login", json={"email": unique_email, "password": password})
    assert response.status_code == 200
    tokens = response.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    response = await client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200
    assert response.json()["email"] == unique_email

    response = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    new_tokens = response.json()
    assert new_tokens["refresh_token"] != refresh_token

    response = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 401

    response = await client.post(
        "/auth/logout-all", headers={"Authorization": f"Bearer {new_tokens['access_token']}"}
    )
    assert response.status_code == 204

    response = await client.post("/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]})
    assert response.status_code == 401