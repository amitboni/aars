"""Tests for message template CRUD, versioning, approval workflow, preview, and tenant isolation."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from config.database import sync_engine


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
async def auth_token(client: AsyncClient, test_tenant: dict) -> str:
    """Register a tenant_admin user and return access token."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"tmpl-{uuid.uuid4().hex[:8]}@test.com",
            "full_name": "Template Test User",
            "password": "testpass123",
            "tenant_id": str(test_tenant["id"]),
            "roles": ["tenant_admin"],
        },
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


def _build_template_payload(name: str | None = None) -> dict:
    """Helper to build a valid template creation payload."""
    return {
        "name": name or f"test_template_{uuid.uuid4().hex[:8]}",
        "category": "UTILITY",
        "description": "A test template",
        "language_variants": {
            "hi": "{agent_name} ji, kaise hain aap?",
            "en": "Hi {agent_name}, how are you?",
        },
        "placeholders": [
            {"key": "agent_name", "description": "Agent's full name", "required": True},
        ],
        "buttons": [
            {"label": "Reply", "type": "quick_reply"},
        ],
    }


# ─── Template CRUD Tests ─────────────────────────────────────────────────────


class TestTemplateCreate:
    async def test_create_template_success(
        self, client: AsyncClient, auth_token: str, test_tenant: dict
    ):
        payload = _build_template_payload()
        resp = await client.post(
            "/api/v1/templates",
            json=payload,
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == payload["name"]
        assert data["category"] == "UTILITY"
        assert data["status"] == "draft"
        assert data["version"] == 1
        assert data["previous_version_id"] is None
        assert data["is_default"] is False
        assert data["tenant_id"] == str(test_tenant["id"])
        assert "hi" in data["language_variants"]
        assert "en" in data["language_variants"]
        assert len(data["placeholders"]) == 1
        assert len(data["buttons"]) == 1

    async def test_create_template_duplicate_name(
        self, client: AsyncClient, auth_token: str
    ):
        name = f"dup-tmpl-{uuid.uuid4().hex[:8]}"
        payload = _build_template_payload(name)
        headers = {"Authorization": f"Bearer {auth_token}"}

        resp1 = await client.post("/api/v1/templates", json=payload, headers=headers)
        assert resp1.status_code == 201

        resp2 = await client.post("/api/v1/templates", json=payload, headers=headers)
        assert resp2.status_code == 409
        assert resp2.json()["error"]["code"] == "CONFLICT"

    async def test_create_template_minimal(
        self, client: AsyncClient, auth_token: str
    ):
        payload = {
            "name": f"minimal-{uuid.uuid4().hex[:8]}",
            "category": "MARKETING",
        }
        resp = await client.post(
            "/api/v1/templates",
            json=payload,
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "draft"
        assert data["version"] == 1


class TestTemplateRead:
    async def test_get_template(self, client: AsyncClient, auth_token: str):
        headers = {"Authorization": f"Bearer {auth_token}"}
        payload = _build_template_payload()
        create_resp = await client.post("/api/v1/templates", json=payload, headers=headers)
        template_id = create_resp.json()["id"]

        get_resp = await client.get(f"/api/v1/templates/{template_id}", headers=headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == template_id
        assert get_resp.json()["name"] == payload["name"]

    async def test_get_nonexistent_template(self, client: AsyncClient, auth_token: str):
        fake_id = uuid.uuid4()
        resp = await client.get(
            f"/api/v1/templates/{fake_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 404

    async def test_list_templates(self, client: AsyncClient, auth_token: str):
        headers = {"Authorization": f"Bearer {auth_token}"}
        for _ in range(3):
            await client.post("/api/v1/templates", json=_build_template_payload(), headers=headers)

        resp = await client.get("/api/v1/templates", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) >= 3
        assert "next_cursor" in data
        assert "has_more" in data

    async def test_list_templates_filter_category(self, client: AsyncClient, auth_token: str):
        headers = {"Authorization": f"Bearer {auth_token}"}

        payload_utility = _build_template_payload()
        payload_utility["category"] = "UTILITY"
        await client.post("/api/v1/templates", json=payload_utility, headers=headers)

        payload_marketing = _build_template_payload()
        payload_marketing["category"] = "MARKETING"
        await client.post("/api/v1/templates", json=payload_marketing, headers=headers)

        resp = await client.get("/api/v1/templates?category=UTILITY", headers=headers)
        assert resp.status_code == 200
        for tmpl in resp.json()["data"]:
            assert tmpl["category"] == "UTILITY"

    async def test_list_templates_pagination(self, client: AsyncClient, auth_token: str):
        headers = {"Authorization": f"Bearer {auth_token}"}
        for _ in range(3):
            await client.post("/api/v1/templates", json=_build_template_payload(), headers=headers)

        resp = await client.get("/api/v1/templates?limit=2", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 2
        assert data["has_more"] is True
        assert data["next_cursor"] is not None

        # Fetch next page
        resp2 = await client.get(
            f"/api/v1/templates?limit=2&cursor={data['next_cursor']}",
            headers=headers,
        )
        assert resp2.status_code == 200
        assert len(resp2.json()["data"]) >= 1


class TestTemplateUpdate:
    async def test_update_template_creates_new_version(
        self, client: AsyncClient, auth_token: str
    ):
        headers = {"Authorization": f"Bearer {auth_token}"}
        create_resp = await client.post(
            "/api/v1/templates", json=_build_template_payload(), headers=headers
        )
        assert create_resp.status_code == 201
        original_id = create_resp.json()["id"]
        original_name = create_resp.json()["name"]

        # Update creates a new version (new row)
        resp = await client.put(
            f"/api/v1/templates/{original_id}",
            json={"description": "Updated description"},
            headers=headers,
        )
        assert resp.status_code == 201  # 201 because new version row created
        data = resp.json()
        assert data["id"] != original_id  # New UUID
        assert data["version"] == 2
        assert data["previous_version_id"] == original_id
        assert data["description"] == "Updated description"
        assert data["name"] == original_name  # Name carried forward
        assert data["status"] == "draft"  # New version starts as draft

    async def test_update_preserves_language_variants(
        self, client: AsyncClient, auth_token: str
    ):
        headers = {"Authorization": f"Bearer {auth_token}"}
        payload = _build_template_payload()
        create_resp = await client.post("/api/v1/templates", json=payload, headers=headers)
        original_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/v1/templates/{original_id}",
            json={"category": "MARKETING"},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["language_variants"] == payload["language_variants"]
        assert data["category"] == "MARKETING"


class TestTemplateDelete:
    async def test_soft_delete_template(self, client: AsyncClient, auth_token: str):
        headers = {"Authorization": f"Bearer {auth_token}"}
        create_resp = await client.post(
            "/api/v1/templates", json=_build_template_payload(), headers=headers
        )
        template_id = create_resp.json()["id"]

        del_resp = await client.delete(f"/api/v1/templates/{template_id}", headers=headers)
        assert del_resp.status_code == 204

        get_resp = await client.get(f"/api/v1/templates/{template_id}", headers=headers)
        assert get_resp.status_code == 404

    async def test_soft_delete_nonexistent(self, client: AsyncClient, auth_token: str):
        fake_id = uuid.uuid4()
        resp = await client.delete(
            f"/api/v1/templates/{fake_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 404


# ─── Approval Workflow Tests ─────────────────────────────────────────────────


class TestTemplateApprovalWorkflow:
    async def test_approve_draft_template(self, client: AsyncClient, auth_token: str):
        headers = {"Authorization": f"Bearer {auth_token}"}
        create_resp = await client.post(
            "/api/v1/templates", json=_build_template_payload(), headers=headers
        )
        template_id = create_resp.json()["id"]
        assert create_resp.json()["status"] == "draft"

        approve_resp = await client.post(
            f"/api/v1/templates/{template_id}/approve", headers=headers
        )
        assert approve_resp.status_code == 200
        data = approve_resp.json()
        assert data["status"] == "approved"
        assert data["approved_by"] is not None
        assert data["approved_at"] is not None

    async def test_activate_approved_template(self, client: AsyncClient, auth_token: str):
        headers = {"Authorization": f"Bearer {auth_token}"}
        create_resp = await client.post(
            "/api/v1/templates", json=_build_template_payload(), headers=headers
        )
        template_id = create_resp.json()["id"]

        # Approve first
        await client.post(f"/api/v1/templates/{template_id}/approve", headers=headers)

        # Then activate
        activate_resp = await client.post(
            f"/api/v1/templates/{template_id}/activate", headers=headers
        )
        assert activate_resp.status_code == 200
        assert activate_resp.json()["status"] == "active"

    async def test_cannot_activate_draft_template(self, client: AsyncClient, auth_token: str):
        headers = {"Authorization": f"Bearer {auth_token}"}
        create_resp = await client.post(
            "/api/v1/templates", json=_build_template_payload(), headers=headers
        )
        template_id = create_resp.json()["id"]

        # Try to activate without approving
        resp = await client.post(
            f"/api/v1/templates/{template_id}/activate", headers=headers
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    async def test_cannot_approve_active_template(self, client: AsyncClient, auth_token: str):
        headers = {"Authorization": f"Bearer {auth_token}"}
        create_resp = await client.post(
            "/api/v1/templates", json=_build_template_payload(), headers=headers
        )
        template_id = create_resp.json()["id"]

        # Approve and activate
        await client.post(f"/api/v1/templates/{template_id}/approve", headers=headers)
        await client.post(f"/api/v1/templates/{template_id}/activate", headers=headers)

        # Try to approve again — should fail (status=active, not draft/in_review)
        resp = await client.post(
            f"/api/v1/templates/{template_id}/approve", headers=headers
        )
        assert resp.status_code == 400

    async def test_archive_template(self, client: AsyncClient, auth_token: str):
        headers = {"Authorization": f"Bearer {auth_token}"}
        create_resp = await client.post(
            "/api/v1/templates", json=_build_template_payload(), headers=headers
        )
        template_id = create_resp.json()["id"]

        # Approve, activate, then archive
        await client.post(f"/api/v1/templates/{template_id}/approve", headers=headers)
        await client.post(f"/api/v1/templates/{template_id}/activate", headers=headers)

        archive_resp = await client.post(
            f"/api/v1/templates/{template_id}/archive", headers=headers
        )
        assert archive_resp.status_code == 200
        assert archive_resp.json()["status"] == "archived"

    async def test_full_lifecycle(self, client: AsyncClient, auth_token: str):
        """Test the complete lifecycle: draft -> approved -> active -> archived."""
        headers = {"Authorization": f"Bearer {auth_token}"}
        create_resp = await client.post(
            "/api/v1/templates", json=_build_template_payload(), headers=headers
        )
        template_id = create_resp.json()["id"]

        # draft -> approved
        resp = await client.post(f"/api/v1/templates/{template_id}/approve", headers=headers)
        assert resp.json()["status"] == "approved"

        # approved -> active
        resp = await client.post(f"/api/v1/templates/{template_id}/activate", headers=headers)
        assert resp.json()["status"] == "active"

        # active -> archived
        resp = await client.post(f"/api/v1/templates/{template_id}/archive", headers=headers)
        assert resp.json()["status"] == "archived"


# ─── Version Tests ──────────────────────────────────────────────────────────


class TestTemplateVersioning:
    async def test_get_versions(self, client: AsyncClient, auth_token: str):
        headers = {"Authorization": f"Bearer {auth_token}"}
        create_resp = await client.post(
            "/api/v1/templates", json=_build_template_payload(), headers=headers
        )
        v1_id = create_resp.json()["id"]

        # Create version 2
        v2_resp = await client.put(
            f"/api/v1/templates/{v1_id}",
            json={"description": "Version 2 description"},
            headers=headers,
        )
        v2_id = v2_resp.json()["id"]

        # Create version 3
        v3_resp = await client.put(
            f"/api/v1/templates/{v2_id}",
            json={"description": "Version 3 description"},
            headers=headers,
        )

        # Get all versions
        versions_resp = await client.get(
            f"/api/v1/templates/{v1_id}/versions", headers=headers
        )
        assert versions_resp.status_code == 200
        versions = versions_resp.json()["data"]
        assert len(versions) >= 3
        # Versions should be ordered by version desc
        version_nums = [v["version"] for v in versions]
        assert version_nums == sorted(version_nums, reverse=True)


# ─── Preview Tests ──────────────────────────────────────────────────────────


class TestTemplatePreview:
    async def test_preview_hindi(self, client: AsyncClient, auth_token: str):
        headers = {"Authorization": f"Bearer {auth_token}"}
        create_resp = await client.post(
            "/api/v1/templates", json=_build_template_payload(), headers=headers
        )
        template_id = create_resp.json()["id"]

        preview_resp = await client.post(
            f"/api/v1/templates/{template_id}/preview",
            json={"language": "hi", "params": {"agent_name": "Rajesh"}},
            headers=headers,
        )
        assert preview_resp.status_code == 200
        data = preview_resp.json()
        assert "Rajesh" in data["rendered"]
        assert "{agent_name}" not in data["rendered"]
        assert isinstance(data["buttons"], list)

    async def test_preview_english(self, client: AsyncClient, auth_token: str):
        headers = {"Authorization": f"Bearer {auth_token}"}
        create_resp = await client.post(
            "/api/v1/templates", json=_build_template_payload(), headers=headers
        )
        template_id = create_resp.json()["id"]

        preview_resp = await client.post(
            f"/api/v1/templates/{template_id}/preview",
            json={"language": "en", "params": {"agent_name": "Rajesh"}},
            headers=headers,
        )
        assert preview_resp.status_code == 200
        data = preview_resp.json()
        assert "Hi Rajesh" in data["rendered"]

    async def test_preview_fallback_to_hindi(self, client: AsyncClient, auth_token: str):
        headers = {"Authorization": f"Bearer {auth_token}"}
        create_resp = await client.post(
            "/api/v1/templates", json=_build_template_payload(), headers=headers
        )
        template_id = create_resp.json()["id"]

        # Request a language that doesn't exist — should fall back to Hindi
        preview_resp = await client.post(
            f"/api/v1/templates/{template_id}/preview",
            json={"language": "mr", "params": {"agent_name": "Rajesh"}},
            headers=headers,
        )
        assert preview_resp.status_code == 200
        data = preview_resp.json()
        assert "Rajesh ji" in data["rendered"]

    async def test_preview_nonexistent_template(self, client: AsyncClient, auth_token: str):
        fake_id = uuid.uuid4()
        resp = await client.post(
            f"/api/v1/templates/{fake_id}/preview",
            json={"language": "hi", "params": {}},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 404


# ─── Tenant Isolation Tests ─────────────────────────────────────────────────


class TestTemplateTenantIsolation:
    async def test_templates_isolated_between_tenants(self, client: AsyncClient):
        """Templates from tenant A should not be visible to tenant B."""
        t1_id, t2_id = uuid.uuid4(), uuid.uuid4()

        with sync_engine.begin() as conn:
            for tid, slug in [
                (t1_id, f"tmpl-a-{t1_id.hex[:6]}"),
                (t2_id, f"tmpl-b-{t2_id.hex[:6]}"),
            ]:
                conn.execute(
                    text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
                    {"id": str(tid), "name": f"Tenant {slug}", "slug": slug},
                )

        try:
            # Register users
            resp_a = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"tmpl-a-{uuid.uuid4().hex[:8]}@test.com",
                    "full_name": "Template User A",
                    "password": "password123",
                    "tenant_id": str(t1_id),
                    "roles": ["tenant_admin"],
                },
            )
            token_a = resp_a.json()["access_token"]

            resp_b = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"tmpl-b-{uuid.uuid4().hex[:8]}@test.com",
                    "full_name": "Template User B",
                    "password": "password123",
                    "tenant_id": str(t2_id),
                    "roles": ["tenant_admin"],
                },
            )
            token_b = resp_b.json()["access_token"]

            # Create template in tenant A
            tmpl_resp = await client.post(
                "/api/v1/templates",
                json=_build_template_payload(),
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert tmpl_resp.status_code == 201
            template_id_a = tmpl_resp.json()["id"]

            # Tenant B should NOT see tenant A's template
            list_resp_b = await client.get(
                "/api/v1/templates",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert list_resp_b.status_code == 200
            for tmpl in list_resp_b.json()["data"]:
                assert tmpl["id"] != template_id_a
                assert tmpl["tenant_id"] == str(t2_id)

            # Tenant B trying to GET tenant A's template should 404
            get_resp = await client.get(
                f"/api/v1/templates/{template_id_a}",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert get_resp.status_code == 404

        finally:
            with sync_engine.begin() as conn:
                conn.execute(text("DELETE FROM template_usage_log WHERE tenant_id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM message_templates WHERE tenant_id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM signals WHERE tenant_id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM users WHERE tenant_id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM tenants WHERE id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})
