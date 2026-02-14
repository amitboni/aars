"""Tests for the auth flow: register, login, token refresh, protected endpoints, RBAC."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from config.database import sync_engine


@pytest.fixture
async def registered_user(client: AsyncClient, test_tenant: dict) -> dict:
    """Register a test user and return the response data."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"user-{uuid.uuid4().hex[:8]}@test.com",
            "full_name": "Test User",
            "password": "testpass123",
            "tenant_id": str(test_tenant["id"]),
            "roles": ["tenant_admin"],
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    data["password"] = "testpass123"
    data["tenant_id"] = str(test_tenant["id"])
    return data


class TestRegister:
    async def test_register_success(self, client: AsyncClient, test_tenant: dict):
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"new-{uuid.uuid4().hex[:8]}@test.com",
                "full_name": "New User",
                "password": "securepass1",
                "tenant_id": str(test_tenant["id"]),
                "roles": ["adm"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["full_name"] == "New User"
        assert data["user"]["roles"] == ["adm"]
        assert data["user"]["is_active"] is True

    async def test_register_duplicate_email(self, client: AsyncClient, test_tenant: dict):
        email = f"dup-{uuid.uuid4().hex[:8]}@test.com"
        payload = {
            "email": email,
            "full_name": "First User",
            "password": "password123",
            "tenant_id": str(test_tenant["id"]),
            "roles": ["adm"],
        }
        resp1 = await client.post("/api/v1/auth/register", json=payload)
        assert resp1.status_code == 201

        resp2 = await client.post("/api/v1/auth/register", json=payload)
        assert resp2.status_code == 409
        assert resp2.json()["error"]["code"] == "CONFLICT"

    async def test_register_short_password(self, client: AsyncClient, test_tenant: dict):
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "short@test.com",
                "full_name": "Short Pass",
                "password": "short",
                "tenant_id": str(test_tenant["id"]),
                "roles": ["adm"],
            },
        )
        assert resp.status_code == 422


class TestLogin:
    async def test_login_success(self, client: AsyncClient, registered_user: dict):
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": registered_user["user"]["email"],
                "password": registered_user["password"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == registered_user["user"]["email"]

    async def test_login_wrong_password(self, client: AsyncClient, registered_user: dict):
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": registered_user["user"]["email"],
                "password": "wrongpassword",
            },
        )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "AUTHENTICATION_ERROR"

    async def test_login_nonexistent_email(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": f"nonexistent-{uuid.uuid4().hex[:8]}@test.com",
                "password": "password123",
            },
        )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "AUTHENTICATION_ERROR"


class TestTokenRefresh:
    async def test_refresh_success(self, client: AsyncClient, registered_user: dict):
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": registered_user["refresh_token"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["access_token"] != registered_user["access_token"]

    async def test_refresh_with_access_token_fails(self, client: AsyncClient, registered_user: dict):
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": registered_user["access_token"]},
        )
        assert resp.status_code == 401

    async def test_refresh_with_invalid_token(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.token.here"},
        )
        assert resp.status_code == 401


class TestProtectedEndpoints:
    async def test_me_with_valid_token(self, client: AsyncClient, registered_user: dict):
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {registered_user['access_token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == registered_user["user"]["id"]
        assert data["email"] == registered_user["user"]["email"]

    async def test_me_without_token(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 422

    async def test_me_with_invalid_token(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401


class TestRBAC:
    async def test_tenant_admin_can_get_tenant(self, client: AsyncClient, registered_user: dict):
        resp = await client.get(
            f"/api/v1/tenants/{registered_user['tenant_id']}",
            headers={"Authorization": f"Bearer {registered_user['access_token']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == registered_user["tenant_id"]

    async def test_adm_cannot_create_tenant(self, client: AsyncClient, test_tenant: dict):
        reg_resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"adm-{uuid.uuid4().hex[:8]}@test.com",
                "full_name": "ADM User",
                "password": "password123",
                "tenant_id": str(test_tenant["id"]),
                "roles": ["adm"],
            },
        )
        adm_token = reg_resp.json()["access_token"]

        resp = await client.post(
            "/api/v1/tenants",
            json={"name": "New Tenant", "slug": f"new-{uuid.uuid4().hex[:8]}"},
            headers={"Authorization": f"Bearer {adm_token}"},
        )
        assert resp.status_code == 403

    async def test_adm_cannot_list_users(self, client: AsyncClient, test_tenant: dict):
        reg_resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"adm2-{uuid.uuid4().hex[:8]}@test.com",
                "full_name": "ADM User 2",
                "password": "password123",
                "tenant_id": str(test_tenant["id"]),
                "roles": ["adm"],
            },
        )
        adm_token = reg_resp.json()["access_token"]

        resp = await client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {adm_token}"},
        )
        assert resp.status_code == 403

    async def test_tenant_admin_can_list_users(self, client: AsyncClient, registered_user: dict):
        resp = await client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {registered_user['access_token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert isinstance(data["data"], list)
        assert len(data["data"]) >= 1


class TestTenantIsolation:
    async def test_users_isolated_between_tenants(self, client: AsyncClient):
        """Create users in two tenants. Verify they don't see each other."""
        t1_id, t2_id = uuid.uuid4(), uuid.uuid4()

        # Create two tenants using sync engine
        with sync_engine.begin() as conn:
            for tid, slug in [(t1_id, f"iso-a-{t1_id.hex[:6]}"), (t2_id, f"iso-b-{t2_id.hex[:6]}")]:
                conn.execute(
                    text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
                    {"id": str(tid), "name": f"Tenant {slug}", "slug": slug},
                )

        try:
            # Register user in tenant A
            resp_a = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"a-{uuid.uuid4().hex[:8]}@test.com",
                    "full_name": "User A",
                    "password": "password123",
                    "tenant_id": str(t1_id),
                    "roles": ["tenant_admin"],
                },
            )
            assert resp_a.status_code == 201
            token_a = resp_a.json()["access_token"]

            # Register user in tenant B
            resp_b = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"b-{uuid.uuid4().hex[:8]}@test.com",
                    "full_name": "User B",
                    "password": "password123",
                    "tenant_id": str(t2_id),
                    "roles": ["tenant_admin"],
                },
            )
            assert resp_b.status_code == 201
            token_b = resp_b.json()["access_token"]

            # User A lists users - should only see tenant A's users
            users_a = await client.get(
                "/api/v1/users",
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert users_a.status_code == 200
            for u in users_a.json()["data"]:
                assert u["tenant_id"] == str(t1_id)

            # User B lists users - should only see tenant B's users
            users_b = await client.get(
                "/api/v1/users",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert users_b.status_code == 200
            for u in users_b.json()["data"]:
                assert u["tenant_id"] == str(t2_id)

        finally:
            with sync_engine.begin() as conn:
                conn.execute(text("DELETE FROM users WHERE tenant_id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM tenants WHERE id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})
