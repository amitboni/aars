"""Integration tests for the Settings Management flow (OTP-protected changes)."""
from __future__ import annotations

import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from config.database import sync_engine


# ─── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def admin_user(client: AsyncClient, test_tenant: dict) -> dict:
    """Register a tenant_admin user for settings tests."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"settings-admin-{uuid.uuid4().hex[:8]}@test.com",
            "full_name": "Settings Admin",
            "password": "password123",
            "tenant_id": str(test_tenant["id"]),
            "roles": ["tenant_admin"],
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    return {
        "access_token": data["access_token"],
        "user_id": data["user"]["id"],
        "email": data["user"]["email"],
        "tenant_id": str(test_tenant["id"]),
    }


@pytest.fixture
def auth_headers(admin_user: dict) -> dict:
    return {"Authorization": f"Bearer {admin_user['access_token']}"}


@pytest.fixture(autouse=True)
def _mock_otp_deps(monkeypatch):
    """Mock OTP dependencies: Redis ops, generate_otp, send_otp_email."""

    async def noop(*args, **kwargs):
        pass

    async def redis_verify_false(*args, **kwargs):
        return False

    monkeypatch.setattr("modules.settings.service.generate_otp", lambda: "123456")
    monkeypatch.setattr("modules.settings.service.store_otp", noop)
    monkeypatch.setattr("modules.settings.service.redis_verify_otp", redis_verify_false)
    monkeypatch.setattr("modules.settings.service.invalidate_otp", noop)
    monkeypatch.setattr("modules.settings.service.send_otp_email", noop)


# ─── Helpers ───────────────────────────────────────────────────────────────────


async def _request_change(client, headers, section, changes):
    """POST a settings change request."""
    return await client.post(
        f"/api/v1/settings/{section}/request-change",
        json={"changes": changes},
        headers=headers,
    )


async def _verify_otp(client, headers, cr_id, otp="123456"):
    """POST an OTP verification."""
    return await client.post(
        "/api/v1/settings/verify-otp",
        json={"change_request_id": str(cr_id), "otp": otp},
        headers=headers,
    )


async def _full_change(client, headers, section, changes):
    """Request + verify in one step. Returns (request_resp, verify_resp)."""
    req = await _request_change(client, headers, section, changes)
    assert req.status_code == 201
    cr_id = req.json()["change_request_id"]
    verify = await _verify_otp(client, headers, cr_id)
    return req, verify


# ─── Settings Read ─────────────────────────────────────────────────────────────


class TestSettingsRead:
    async def test_get_all_settings(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/settings", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        expected = [
            "lifecycle_thresholds", "engagement_scoring_weights",
            "contact_rules", "trai_calling_hours", "rate_limits",
            "branding", "languages",
        ]
        for section in expected:
            assert section in data
            assert "values" in data[section]
            assert "metadata" in data[section]

    async def test_get_section_settings(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get(
            "/api/v1/settings/lifecycle_thresholds", headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "values" in data
        assert "metadata" in data

    async def test_get_invalid_section(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get(
            "/api/v1/settings/nonexistent_section", headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_get_settings_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/settings")
        assert resp.status_code == 422

    async def test_get_settings_requires_admin_role(
        self, client: AsyncClient, test_tenant: dict,
    ):
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"adm-read-{uuid.uuid4().hex[:8]}@test.com",
                "full_name": "ADM User",
                "password": "password123",
                "tenant_id": str(test_tenant["id"]),
                "roles": ["adm"],
            },
        )
        adm_token = reg.json()["access_token"]
        resp = await client.get(
            "/api/v1/settings",
            headers={"Authorization": f"Bearer {adm_token}"},
        )
        assert resp.status_code == 403

    async def test_settings_include_metadata(
        self, client: AsyncClient, auth_headers: dict,
    ):
        resp = await client.get(
            "/api/v1/settings/lifecycle_thresholds", headers=auth_headers,
        )
        assert resp.status_code == 200
        meta = resp.json()["metadata"]
        assert "dormancy_days" in meta
        assert "type" in meta["dormancy_days"]
        assert "min" in meta["dormancy_days"]
        assert "max" in meta["dormancy_days"]
        assert "description" in meta["dormancy_days"]

    async def test_all_seven_sections_present(
        self, client: AsyncClient, auth_headers: dict,
    ):
        resp = await client.get("/api/v1/settings", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 7


# ─── Change Request & OTP ─────────────────────────────────────────────────────


class TestSettingsChangeRequestAndOTP:
    async def test_request_change_success(
        self, client: AsyncClient, auth_headers: dict,
    ):
        resp = await _request_change(
            client, auth_headers,
            "lifecycle_thresholds", {"dormancy_days": 120},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "change_request_id" in data
        assert "otp_sent_to" in data
        assert "expires_at" in data
        assert "changes_summary" in data
        assert data["changes_summary"]["dormancy_days"] == 120

    async def test_request_change_validation_fail(
        self, client: AsyncClient, auth_headers: dict,
    ):
        resp = await _request_change(
            client, auth_headers,
            "lifecycle_thresholds", {"dormancy_days": 5},
        )
        assert resp.status_code == 400

    async def test_request_change_unknown_section(
        self, client: AsyncClient, auth_headers: dict,
    ):
        resp = await _request_change(
            client, auth_headers,
            "nonexistent_section", {"field": "value"},
        )
        assert resp.status_code == 404

    async def test_request_change_no_changes(
        self, client: AsyncClient, auth_headers: dict, test_tenant: dict,
    ):
        # Pre-set config so proposed matches current
        with sync_engine.begin() as conn:
            conn.execute(
                text("UPDATE tenants SET config = CAST(:config AS jsonb) WHERE id = :tid"),
                {
                    "config": json.dumps({"lifecycle_thresholds": {"dormancy_days": 120}}),
                    "tid": str(test_tenant["id"]),
                },
            )
        resp = await _request_change(
            client, auth_headers,
            "lifecycle_thresholds", {"dormancy_days": 120},
        )
        assert resp.status_code == 409

    async def test_request_change_unknown_field(
        self, client: AsyncClient, auth_headers: dict,
    ):
        resp = await _request_change(
            client, auth_headers,
            "lifecycle_thresholds", {"fake_field": 42},
        )
        assert resp.status_code == 400
        assert "Unknown field" in resp.json()["error"]["message"]

    async def test_otp_sent_to_masked(
        self, client: AsyncClient, auth_headers: dict, admin_user: dict,
    ):
        resp = await _request_change(
            client, auth_headers,
            "lifecycle_thresholds", {"dormancy_days": 120},
        )
        assert resp.status_code == 201
        otp_sent_to = resp.json()["otp_sent_to"]
        assert "***" in otp_sent_to
        assert otp_sent_to != admin_user["email"]

    async def test_request_change_cancels_previous(
        self, client: AsyncClient, auth_headers: dict,
    ):
        resp1 = await _request_change(
            client, auth_headers,
            "lifecycle_thresholds", {"dormancy_days": 120},
        )
        assert resp1.status_code == 201
        cr1_id = resp1.json()["change_request_id"]

        resp2 = await _request_change(
            client, auth_headers,
            "lifecycle_thresholds", {"dormancy_days": 150},
        )
        assert resp2.status_code == 201
        cr2_id = resp2.json()["change_request_id"]
        assert cr1_id != cr2_id

        # First request should be expired
        verify = await _verify_otp(client, auth_headers, cr1_id, "123456")
        assert verify.status_code == 400

    async def test_request_change_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/settings/lifecycle_thresholds/request-change",
            json={"changes": {"dormancy_days": 120}},
        )
        assert resp.status_code == 422

    async def test_request_change_requires_admin(
        self, client: AsyncClient, test_tenant: dict,
    ):
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"adm-rc-{uuid.uuid4().hex[:8]}@test.com",
                "full_name": "ADM No Access",
                "password": "password123",
                "tenant_id": str(test_tenant["id"]),
                "roles": ["adm"],
            },
        )
        adm_token = reg.json()["access_token"]
        resp = await client.post(
            "/api/v1/settings/lifecycle_thresholds/request-change",
            json={"changes": {"dormancy_days": 120}},
            headers={"Authorization": f"Bearer {adm_token}"},
        )
        assert resp.status_code == 403

    async def test_weights_validation_sum(
        self, client: AsyncClient, auth_headers: dict,
    ):
        resp = await _request_change(
            client, auth_headers,
            "engagement_scoring_weights",
            {
                "call_answer_rate": 0.1,
                "whatsapp_response_rate": 0.2,
                "training_completion": 0.2,
                "recency": 0.3,
            },
        )
        assert resp.status_code == 400
        assert "sum to 1.0" in resp.json()["error"]["message"]

    async def test_cross_field_lifecycle(
        self, client: AsyncClient, auth_headers: dict,
    ):
        resp = await _request_change(
            client, auth_headers,
            "lifecycle_thresholds",
            {"at_risk_days": 100, "dormancy_days": 50},
        )
        assert resp.status_code == 400
        assert "strictly less" in resp.json()["error"]["message"]

    async def test_cross_field_contact_rules(
        self, client: AsyncClient, auth_headers: dict,
    ):
        resp = await _request_change(
            client, auth_headers,
            "contact_rules",
            {"max_contacts_per_month": 2, "max_whatsapp_per_day_per_agent": 5},
        )
        assert resp.status_code == 400
        assert "max_contacts_per_month" in resp.json()["error"]["message"]


# ─── OTP Verification ─────────────────────────────────────────────────────────


class TestOTPVerification:
    async def test_verify_otp_success(
        self, client: AsyncClient, auth_headers: dict,
    ):
        resp = await _request_change(
            client, auth_headers,
            "lifecycle_thresholds", {"dormancy_days": 120},
        )
        assert resp.status_code == 201
        cr_id = resp.json()["change_request_id"]

        verify = await _verify_otp(client, auth_headers, cr_id)
        assert verify.status_code == 200
        data = verify.json()
        assert data["section"] == "lifecycle_thresholds"
        assert "dormancy_days" in data["changed_fields"]

    async def test_verify_wrong_otp(
        self, client: AsyncClient, auth_headers: dict,
    ):
        resp = await _request_change(
            client, auth_headers,
            "lifecycle_thresholds", {"dormancy_days": 120},
        )
        cr_id = resp.json()["change_request_id"]

        verify = await _verify_otp(client, auth_headers, cr_id, "999999")
        assert verify.status_code == 401
        assert "Invalid OTP" in verify.json()["error"]["message"]

    async def test_verify_after_three_failures(
        self, client: AsyncClient, auth_headers: dict,
    ):
        resp = await _request_change(
            client, auth_headers,
            "lifecycle_thresholds", {"dormancy_days": 120},
        )
        cr_id = resp.json()["change_request_id"]

        # 3 wrong attempts
        for _ in range(3):
            r = await _verify_otp(client, auth_headers, cr_id, "999999")
            assert r.status_code == 401

        # 4th attempt even with correct OTP → rejected
        r = await _verify_otp(client, auth_headers, cr_id, "123456")
        assert r.status_code == 400
        assert "rejected" in r.json()["error"]["message"].lower()

    async def test_verify_expired_otp(
        self, client: AsyncClient, auth_headers: dict, test_tenant: dict,
    ):
        resp = await _request_change(
            client, auth_headers,
            "lifecycle_thresholds", {"dormancy_days": 120},
        )
        cr_id = resp.json()["change_request_id"]

        # Expire the request
        with sync_engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE settings_change_requests "
                    "SET otp_expires_at = NOW() - INTERVAL '1 hour' "
                    "WHERE id = :id"
                ),
                {"id": cr_id},
            )

        verify = await _verify_otp(client, auth_headers, cr_id, "123456")
        assert verify.status_code == 400
        assert "expired" in verify.json()["error"]["message"].lower()

    async def test_verify_already_applied(
        self, client: AsyncClient, auth_headers: dict,
    ):
        _, verify = await _full_change(
            client, auth_headers,
            "lifecycle_thresholds", {"dormancy_days": 120},
        )
        assert verify.status_code == 200
        cr_id = _.json()["change_request_id"]

        # Try again
        verify2 = await _verify_otp(client, auth_headers, cr_id, "123456")
        assert verify2.status_code == 400
        assert "already been applied" in verify2.json()["error"]["message"]

    async def test_verify_cancelled(
        self, client: AsyncClient, auth_headers: dict,
    ):
        resp = await _request_change(
            client, auth_headers,
            "lifecycle_thresholds", {"dormancy_days": 120},
        )
        cr_id = resp.json()["change_request_id"]

        # Cancel
        cancel = await client.post(
            "/api/v1/settings/lifecycle_thresholds/request-change/cancel",
            json={"change_request_id": cr_id},
            headers=auth_headers,
        )
        assert cancel.status_code == 200

        # Try to verify cancelled request
        verify = await _verify_otp(client, auth_headers, cr_id, "123456")
        assert verify.status_code == 400

    async def test_settings_applied_after_verify(
        self, client: AsyncClient, auth_headers: dict,
    ):
        await _full_change(
            client, auth_headers,
            "lifecycle_thresholds", {"dormancy_days": 120},
        )

        # Read settings to confirm
        settings = await client.get(
            "/api/v1/settings/lifecycle_thresholds", headers=auth_headers,
        )
        assert settings.status_code == 200
        assert settings.json()["values"]["dormancy_days"] == 120

    async def test_audit_log_created_on_verify(
        self, client: AsyncClient, auth_headers: dict, admin_user: dict,
    ):
        _, verify = await _full_change(
            client, auth_headers,
            "lifecycle_thresholds", {"dormancy_days": 120},
        )
        assert verify.status_code == 200
        audit = verify.json()
        assert audit["section"] == "lifecycle_thresholds"
        assert audit["changed_by"] == admin_user["user_id"]
        assert audit["changed_by_email"] == admin_user["email"]
        assert "dormancy_days" in audit["changed_fields"]

    async def test_verify_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/settings/verify-otp",
            json={"change_request_id": str(uuid.uuid4()), "otp": "123456"},
        )
        assert resp.status_code == 422


# ─── Audit Log ─────────────────────────────────────────────────────────────────


class TestSettingsAuditLog:
    async def test_list_audit_log(
        self, client: AsyncClient, auth_headers: dict,
    ):
        await _full_change(
            client, auth_headers,
            "lifecycle_thresholds", {"dormancy_days": 120},
        )

        log = await client.get(
            "/api/v1/settings/audit-log", headers=auth_headers,
        )
        assert log.status_code == 200
        data = log.json()
        assert "data" in data
        assert len(data["data"]) >= 1
        assert data["data"][0]["section"] == "lifecycle_thresholds"

    async def test_audit_log_section_filter(
        self, client: AsyncClient, auth_headers: dict,
    ):
        await _full_change(
            client, auth_headers,
            "lifecycle_thresholds", {"dormancy_days": 120},
        )
        await _full_change(
            client, auth_headers,
            "branding", {"company_name": "Test Corp"},
        )

        log = await client.get(
            "/api/v1/settings/audit-log?section=branding", headers=auth_headers,
        )
        assert log.status_code == 200
        for entry in log.json()["data"]:
            assert entry["section"] == "branding"

    async def test_audit_log_pagination(
        self, client: AsyncClient, auth_headers: dict,
    ):
        for days in [120, 150, 180]:
            await _full_change(
                client, auth_headers,
                "lifecycle_thresholds", {"dormancy_days": days},
            )

        log = await client.get(
            "/api/v1/settings/audit-log?limit=1", headers=auth_headers,
        )
        assert log.status_code == 200
        data = log.json()
        assert len(data["data"]) == 1
        assert data["has_more"] is True
        assert data["next_cursor"] is not None

    async def test_audit_log_empty(
        self, client: AsyncClient, auth_headers: dict,
    ):
        log = await client.get(
            "/api/v1/settings/audit-log", headers=auth_headers,
        )
        assert log.status_code == 200
        assert log.json()["data"] == []
        assert log.json()["has_more"] is False

    async def test_audit_log_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/settings/audit-log")
        assert resp.status_code == 422


# ─── Cancel Change Request ────────────────────────────────────────────────────


class TestCancelChangeRequest:
    async def test_cancel_pending(
        self, client: AsyncClient, auth_headers: dict,
    ):
        resp = await _request_change(
            client, auth_headers,
            "lifecycle_thresholds", {"dormancy_days": 120},
        )
        cr_id = resp.json()["change_request_id"]

        cancel = await client.post(
            "/api/v1/settings/lifecycle_thresholds/request-change/cancel",
            json={"change_request_id": cr_id},
            headers=auth_headers,
        )
        assert cancel.status_code == 200
        assert cancel.json()["status"] == "expired"

    async def test_cancel_already_applied(
        self, client: AsyncClient, auth_headers: dict,
    ):
        req, verify = await _full_change(
            client, auth_headers,
            "lifecycle_thresholds", {"dormancy_days": 120},
        )
        assert verify.status_code == 200
        cr_id = req.json()["change_request_id"]

        cancel = await client.post(
            "/api/v1/settings/lifecycle_thresholds/request-change/cancel",
            json={"change_request_id": cr_id},
            headers=auth_headers,
        )
        assert cancel.status_code == 400

    async def test_cancel_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/settings/lifecycle_thresholds/request-change/cancel",
            json={"change_request_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 422


# ─── Tenant Isolation ─────────────────────────────────────────────────────────


class TestSettingsTenantIsolation:
    async def test_settings_isolated(self, client: AsyncClient):
        """Changes in tenant A are not visible to tenant B."""
        t1_id, t2_id = uuid.uuid4(), uuid.uuid4()

        with sync_engine.begin() as conn:
            for tid, slug in [
                (t1_id, f"iso-a-{t1_id.hex[:6]}"),
                (t2_id, f"iso-b-{t2_id.hex[:6]}"),
            ]:
                conn.execute(
                    text(
                        "INSERT INTO tenants (id, name, slug, subscription_tier, is_active, config) "
                        "VALUES (:id, :name, :slug, 'trial', true, '{}'::jsonb)"
                    ),
                    {"id": str(tid), "name": f"Tenant {slug}", "slug": slug},
                )

        try:
            # Register admins
            r1 = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"iso-a-{uuid.uuid4().hex[:8]}@test.com",
                    "full_name": "Admin A",
                    "password": "password123",
                    "tenant_id": str(t1_id),
                    "roles": ["tenant_admin"],
                },
            )
            token_a = r1.json()["access_token"]
            headers_a = {"Authorization": f"Bearer {token_a}"}

            r2 = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"iso-b-{uuid.uuid4().hex[:8]}@test.com",
                    "full_name": "Admin B",
                    "password": "password123",
                    "tenant_id": str(t2_id),
                    "roles": ["tenant_admin"],
                },
            )
            token_b = r2.json()["access_token"]
            headers_b = {"Authorization": f"Bearer {token_b}"}

            # Apply change in tenant A
            await _full_change(
                client, headers_a,
                "lifecycle_thresholds", {"dormancy_days": 120},
            )

            # Tenant A sees the change
            settings_a = await client.get(
                "/api/v1/settings/lifecycle_thresholds", headers=headers_a,
            )
            assert settings_a.json()["values"]["dormancy_days"] == 120

            # Tenant B does NOT see tenant A's change
            settings_b = await client.get(
                "/api/v1/settings/lifecycle_thresholds", headers=headers_b,
            )
            assert settings_b.json()["values"] == {}

        finally:
            with sync_engine.begin() as conn:
                conn.execute(text("DELETE FROM settings_audit_log WHERE tenant_id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM settings_change_requests WHERE tenant_id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM users WHERE tenant_id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM tenants WHERE id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})

    async def test_audit_log_isolated(self, client: AsyncClient):
        """Tenant B cannot see tenant A's audit log."""
        t1_id, t2_id = uuid.uuid4(), uuid.uuid4()

        with sync_engine.begin() as conn:
            for tid, slug in [
                (t1_id, f"aud-a-{t1_id.hex[:6]}"),
                (t2_id, f"aud-b-{t2_id.hex[:6]}"),
            ]:
                conn.execute(
                    text(
                        "INSERT INTO tenants (id, name, slug, subscription_tier, is_active, config) "
                        "VALUES (:id, :name, :slug, 'trial', true, '{}'::jsonb)"
                    ),
                    {"id": str(tid), "name": f"Tenant {slug}", "slug": slug},
                )

        try:
            r1 = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"aud-a-{uuid.uuid4().hex[:8]}@test.com",
                    "full_name": "Admin A",
                    "password": "password123",
                    "tenant_id": str(t1_id),
                    "roles": ["tenant_admin"],
                },
            )
            headers_a = {"Authorization": f"Bearer {r1.json()['access_token']}"}

            r2 = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"aud-b-{uuid.uuid4().hex[:8]}@test.com",
                    "full_name": "Admin B",
                    "password": "password123",
                    "tenant_id": str(t2_id),
                    "roles": ["tenant_admin"],
                },
            )
            headers_b = {"Authorization": f"Bearer {r2.json()['access_token']}"}

            # Apply change in tenant A
            await _full_change(
                client, headers_a,
                "lifecycle_thresholds", {"dormancy_days": 120},
            )

            # Tenant A has audit entry
            log_a = await client.get("/api/v1/settings/audit-log", headers=headers_a)
            assert len(log_a.json()["data"]) >= 1

            # Tenant B has no audit entries
            log_b = await client.get("/api/v1/settings/audit-log", headers=headers_b)
            assert log_b.json()["data"] == []

        finally:
            with sync_engine.begin() as conn:
                conn.execute(text("DELETE FROM settings_audit_log WHERE tenant_id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM settings_change_requests WHERE tenant_id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM users WHERE tenant_id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM tenants WHERE id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})

    async def test_change_request_isolated(self, client: AsyncClient):
        """Tenant B cannot verify tenant A's change request."""
        t1_id, t2_id = uuid.uuid4(), uuid.uuid4()

        with sync_engine.begin() as conn:
            for tid, slug in [
                (t1_id, f"cr-a-{t1_id.hex[:6]}"),
                (t2_id, f"cr-b-{t2_id.hex[:6]}"),
            ]:
                conn.execute(
                    text(
                        "INSERT INTO tenants (id, name, slug, subscription_tier, is_active, config) "
                        "VALUES (:id, :name, :slug, 'trial', true, '{}'::jsonb)"
                    ),
                    {"id": str(tid), "name": f"Tenant {slug}", "slug": slug},
                )

        try:
            r1 = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"cr-a-{uuid.uuid4().hex[:8]}@test.com",
                    "full_name": "Admin A",
                    "password": "password123",
                    "tenant_id": str(t1_id),
                    "roles": ["tenant_admin"],
                },
            )
            headers_a = {"Authorization": f"Bearer {r1.json()['access_token']}"}

            r2 = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"cr-b-{uuid.uuid4().hex[:8]}@test.com",
                    "full_name": "Admin B",
                    "password": "password123",
                    "tenant_id": str(t2_id),
                    "roles": ["tenant_admin"],
                },
            )
            headers_b = {"Authorization": f"Bearer {r2.json()['access_token']}"}

            # Create change request in tenant A
            req = await _request_change(
                client, headers_a,
                "lifecycle_thresholds", {"dormancy_days": 120},
            )
            assert req.status_code == 201
            cr_id = req.json()["change_request_id"]

            # Tenant B tries to verify tenant A's change request → 404
            verify_b = await _verify_otp(client, headers_b, cr_id, "123456")
            assert verify_b.status_code == 404

        finally:
            with sync_engine.begin() as conn:
                conn.execute(text("DELETE FROM settings_audit_log WHERE tenant_id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM settings_change_requests WHERE tenant_id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM users WHERE tenant_id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM tenants WHERE id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})


# ─── Deprecated Config Endpoint ───────────────────────────────────────────────


class TestDeprecatedConfigEndpoint:
    async def test_super_admin_can_update_config(
        self, client: AsyncClient, test_tenant: dict,
    ):
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"super-{uuid.uuid4().hex[:8]}@test.com",
                "full_name": "Super Admin",
                "password": "password123",
                "tenant_id": str(test_tenant["id"]),
                "roles": ["super_admin"],
            },
        )
        assert reg.status_code == 201
        token = reg.json()["access_token"]

        resp = await client.put(
            f"/api/v1/tenants/{test_tenant['id']}/config",
            json={"config": {"test_key": "test_value"}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    async def test_tenant_admin_cannot_update_config(
        self, client: AsyncClient, test_tenant: dict, auth_headers: dict,
    ):
        resp = await client.put(
            f"/api/v1/tenants/{test_tenant['id']}/config",
            json={"config": {"test_key": "test_value"}},
            headers=auth_headers,
        )
        assert resp.status_code == 403
