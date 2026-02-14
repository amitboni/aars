"""Tests for the Integration Framework (Slice 9).

- CSV agent import → agents created
- CSV policy import → POLICY_SOLD signals with idempotency keys → lifecycle updates
- Duplicate CSV upload → no duplicates (idempotency)
- Field mapping transforms correctly
- Tenant isolation
- Webhook signature verification
- Commission and training CSV imports
"""
from __future__ import annotations

import csv
import hashlib
import hmac
import io
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from config.database import sync_engine


@pytest.fixture
def test_agent(test_tenant: dict) -> dict:
    """Create a test agent in the test tenant."""
    agent_id = uuid.uuid4()
    agent_code = f"INT-{agent_id.hex[:8]}"
    with sync_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO agents (id, tenant_id, agent_code, full_name, phone, lifecycle_state) "
                "VALUES (:id, :tid, :code, :name, :phone, :state)"
            ),
            {
                "id": str(agent_id),
                "tid": str(test_tenant["id"]),
                "code": agent_code,
                "name": "Integration Test Agent",
                "phone": "9876543210",
                "state": "licensed",
            },
        )

    yield {
        "id": agent_id,
        "agent_code": agent_code,
        "tenant_id": test_tenant["id"],
    }

    with sync_engine.begin() as conn:
        conn.execute(
            text("DELETE FROM signals WHERE agent_id = :aid"),
            {"aid": str(agent_id)},
        )
        conn.execute(
            text("DELETE FROM agents WHERE id = :aid"),
            {"aid": str(agent_id)},
        )


@pytest.fixture
async def auth_token(client: AsyncClient, test_tenant: dict) -> str:
    """Register a tenant_admin user and return access token."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"inttest-{uuid.uuid4().hex[:8]}@test.com",
            "full_name": "Integration Test User",
            "password": "testpass123",
            "tenant_id": str(test_tenant["id"]),
            "roles": ["tenant_admin"],
        },
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


def _make_csv(headers: list[str], rows: list[list[str]]) -> bytes:
    """Build a CSV file in memory."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return output.getvalue().encode("utf-8")


# ─── Field Mapping Tests ───


class TestFieldMapping:
    def test_apply_field_mapping(self):
        from modules.integration.field_mapping import apply_field_mapping

        row = {"Agent_ID": "A001", "Mobile": "9876543210", "Name": "Test Agent"}
        mapping = {"agent_id": "agent_code", "mobile": "phone", "name": "full_name"}
        result = apply_field_mapping(row, mapping)

        assert result["agent_code"] == "A001"
        assert result["phone"] == "9876543210"
        assert result["full_name"] == "Test Agent"

    def test_unmapped_fields_pass_through(self):
        from modules.integration.field_mapping import apply_field_mapping

        row = {"agent_code": "A001", "custom_field": "value"}
        mapping = {}
        result = apply_field_mapping(row, mapping)

        assert result["agent_code"] == "A001"
        assert result["custom_field"] == "value"

    def test_default_mapping_exists(self):
        from modules.integration.field_mapping import get_default_mapping

        for system in ("pas", "lms", "commission"):
            mapping = get_default_mapping(system)
            assert isinstance(mapping, dict)
            assert len(mapping) > 0

    def test_default_mapping_unknown_system(self):
        from modules.integration.field_mapping import get_default_mapping

        mapping = get_default_mapping("nonexistent")
        assert mapping == {}


# ─── Agent CSV Import Tests ───


class TestAgentCSVImport:
    async def test_csv_agent_import_creates_agents(
        self, client: AsyncClient, auth_token: str, test_tenant: dict
    ):
        """Agent CSV → agents created."""
        headers = {"Authorization": f"Bearer {auth_token}"}
        code1 = f"CSV-{uuid.uuid4().hex[:6]}"
        code2 = f"CSV-{uuid.uuid4().hex[:6]}"

        csv_data = _make_csv(
            ["agent_code", "full_name", "phone", "email"],
            [
                [code1, "Agent One", "9111111111", "one@test.com"],
                [code2, "Agent Two", "9222222222", "two@test.com"],
            ],
        )

        resp = await client.post(
            "/api/v1/integration/upload",
            files={"file": ("agents.csv", csv_data, "text/csv")},
            data={"source_system": "pas"},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["total_records"] == 2
        assert data["processed_records"] == 2
        assert data["failed_records"] == 0

        # Verify agents were created
        for code in (code1, code2):
            agents_resp = await client.get(
                "/api/v1/agents",
                headers=headers,
            )
            assert agents_resp.status_code == 200
            agent_codes = [a["agent_code"] for a in agents_resp.json()["data"]]
            assert code in agent_codes

    async def test_csv_agent_import_updates_existing(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        """Agent CSV with existing agent_code → updates agent."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        csv_data = _make_csv(
            ["agent_code", "full_name", "phone", "email"],
            [
                [test_agent["agent_code"], "Updated Name", "9876543210", "updated@test.com"],
            ],
        )

        resp = await client.post(
            "/api/v1/integration/upload",
            files={"file": ("agents.csv", csv_data, "text/csv")},
            data={"source_system": "pas"},
            headers=headers,
        )
        assert resp.status_code == 201
        assert resp.json()["processed_records"] == 1


# ─── Policy CSV Import Tests ───


class TestPolicyCSVImport:
    async def test_csv_policy_import_creates_signals(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        """Policy CSV → POLICY_SOLD signals with idempotency keys."""
        headers = {"Authorization": f"Bearer {auth_token}"}
        pol_num = f"POL-{uuid.uuid4().hex[:8]}"

        csv_data = _make_csv(
            ["agent_code", "policy_number", "product_name", "premium_amount"],
            [
                [test_agent["agent_code"], pol_num, "Term Life", "50000"],
            ],
        )

        resp = await client.post(
            "/api/v1/integration/upload",
            files={"file": ("policies.csv", csv_data, "text/csv")},
            data={"source_system": "pas"},
            headers=headers,
        )
        assert resp.status_code == 201
        assert resp.json()["processed_records"] == 1

        # Verify POLICY_SOLD signal was emitted
        signals_resp = await client.get(
            f"/api/v1/agents/{test_agent['id']}/signals?signal_type=policy_sold",
            headers=headers,
        )
        assert signals_resp.status_code == 200
        policy_signals = signals_resp.json()["data"]
        assert len(policy_signals) >= 1
        assert policy_signals[0]["payload"]["policy_number"] == pol_num

    async def test_duplicate_csv_upload_no_duplicates(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        """Same CSV uploaded twice → no duplicate signals (idempotency)."""
        headers = {"Authorization": f"Bearer {auth_token}"}
        pol_num = f"POL-DUP-{uuid.uuid4().hex[:8]}"

        csv_data = _make_csv(
            ["agent_code", "policy_number"],
            [[test_agent["agent_code"], pol_num]],
        )

        # First upload
        resp1 = await client.post(
            "/api/v1/integration/upload",
            files={"file": ("policies.csv", csv_data, "text/csv")},
            data={"source_system": "pas"},
            headers=headers,
        )
        assert resp1.status_code == 201

        # Second upload — same data
        resp2 = await client.post(
            "/api/v1/integration/upload",
            files={"file": ("policies.csv", csv_data, "text/csv")},
            data={"source_system": "pas"},
            headers=headers,
        )
        assert resp2.status_code == 201

        # Should still have only 1 POLICY_SOLD signal for this policy number
        signals_resp = await client.get(
            f"/api/v1/agents/{test_agent['id']}/signals?signal_type=policy_sold",
            headers=headers,
        )
        assert signals_resp.status_code == 200
        matching = [
            s for s in signals_resp.json()["data"]
            if s["payload"].get("policy_number") == pol_num
        ]
        assert len(matching) == 1

    async def test_policy_csv_unknown_agent_skipped(
        self, client: AsyncClient, auth_token: str
    ):
        """Policy CSV with unknown agent_code → row skipped."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        csv_data = _make_csv(
            ["agent_code", "policy_number"],
            [["NONEXISTENT-AGENT", "POL-SKIP-001"]],
        )

        resp = await client.post(
            "/api/v1/integration/upload",
            files={"file": ("policies.csv", csv_data, "text/csv")},
            data={"source_system": "pas"},
            headers=headers,
        )
        assert resp.status_code == 201
        # Row processed but no signal emitted (agent not found)
        assert resp.json()["processed_records"] == 1


# ─── Commission CSV Import Tests ───


class TestCommissionCSVImport:
    async def test_commission_csv_creates_signals(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        """Commission CSV → COMMISSION_CREDITED signals."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        csv_data = _make_csv(
            ["agent_code", "amount", "credit_date", "policy_number"],
            [
                [test_agent["agent_code"], "15000.50", "2025-01-15", "POL-COMM-001"],
            ],
        )

        resp = await client.post(
            "/api/v1/integration/upload",
            files={"file": ("commissions.csv", csv_data, "text/csv")},
            data={"source_system": "commission"},
            headers=headers,
        )
        assert resp.status_code == 201
        assert resp.json()["processed_records"] == 1

        # Verify signal
        signals_resp = await client.get(
            f"/api/v1/agents/{test_agent['id']}/signals?signal_type=commission_credited",
            headers=headers,
        )
        assert signals_resp.status_code == 200
        assert len(signals_resp.json()["data"]) >= 1


# ─── Training CSV Import Tests ───


class TestTrainingCSVImport:
    async def test_training_csv_creates_signals(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        """Training CSV → TRAINING_COMPLETED_EXTERNAL signals."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        csv_data = _make_csv(
            ["agent_code", "training_name", "completion_date", "score"],
            [
                [test_agent["agent_code"], "Product Knowledge 101", "2025-01-20", "85"],
            ],
        )

        resp = await client.post(
            "/api/v1/integration/upload",
            files={"file": ("training.csv", csv_data, "text/csv")},
            data={"source_system": "lms"},
            headers=headers,
        )
        assert resp.status_code == 201
        assert resp.json()["processed_records"] == 1

        signals_resp = await client.get(
            f"/api/v1/agents/{test_agent['id']}/signals?signal_type=training_completed_external",
            headers=headers,
        )
        assert signals_resp.status_code == 200
        assert len(signals_resp.json()["data"]) >= 1


# ─── License CSV Import Tests ───


class TestLicenseCSVImport:
    async def test_license_csv_creates_signals(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        """License CSV → LICENSE_STATUS_CHANGED signals."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        csv_data = _make_csv(
            ["agent_code", "license_number", "status", "expiry_date"],
            [
                [test_agent["agent_code"], "LIC-001", "active", "2026-12-31"],
            ],
        )

        resp = await client.post(
            "/api/v1/integration/upload",
            files={"file": ("licenses.csv", csv_data, "text/csv")},
            data={"source_system": "lms"},
            headers=headers,
        )
        assert resp.status_code == 201
        assert resp.json()["processed_records"] == 1

        signals_resp = await client.get(
            f"/api/v1/agents/{test_agent['id']}/signals?signal_type=license_status_changed",
            headers=headers,
        )
        assert signals_resp.status_code == 200
        assert len(signals_resp.json()["data"]) >= 1


# ─── Webhook Tests ───


class TestWebhookReceiver:
    def test_webhook_signature_verification(self):
        """Webhook signature verification works correctly."""
        from modules.integration.webhook_receiver import verify_webhook_signature

        secret = "test-secret-key"
        payload = b'{"event_type": "policy_sold", "data": {}}'

        # Compute correct signature
        sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

        # Valid signature
        assert verify_webhook_signature(payload, f"sha256={sig}", secret) is True
        assert verify_webhook_signature(payload, sig, secret) is True

        # Invalid signature
        assert verify_webhook_signature(payload, "sha256=invalid", secret) is False

        # Missing signature/secret
        assert verify_webhook_signature(payload, "", secret) is False
        assert verify_webhook_signature(payload, sig, "") is False

    async def test_webhook_endpoint_rejects_bad_signature(
        self, client: AsyncClient, test_tenant: dict
    ):
        """Webhook endpoint rejects requests with invalid signature."""
        # Configure webhook secret for the tenant
        with sync_engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE tenants SET config = :config WHERE id = :tid"
                ),
                {
                    "tid": str(test_tenant["id"]),
                    "config": '{"integrations": {"pas": {"webhook_secret": "test-secret"}}}',
                },
            )

        resp = await client.post(
            f"/api/v1/integration/webhooks/{test_tenant['slug']}/pas",
            json={"event_type": "policy_sold", "data": {"agent_code": "A001"}},
            headers={"X-Webhook-Signature": "sha256=invalid"},
        )
        assert resp.status_code == 401


# ─── Tenant Isolation Tests ───


class TestIntegrationTenantIsolation:
    async def test_jobs_isolated_between_tenants(self, client: AsyncClient):
        """Integration jobs from tenant A not visible to tenant B."""
        t1_id, t2_id = uuid.uuid4(), uuid.uuid4()

        with sync_engine.begin() as conn:
            for tid, slug in [
                (t1_id, f"int-a-{t1_id.hex[:6]}"),
                (t2_id, f"int-b-{t2_id.hex[:6]}"),
            ]:
                conn.execute(
                    text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
                    {"id": str(tid), "name": f"Tenant {slug}", "slug": slug},
                )

        try:
            # Register users in each tenant
            resp_a = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"int-a-{uuid.uuid4().hex[:8]}@test.com",
                    "full_name": "User A",
                    "password": "password123",
                    "tenant_id": str(t1_id),
                    "roles": ["tenant_admin"],
                },
            )
            token_a = resp_a.json()["access_token"]

            resp_b = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"int-b-{uuid.uuid4().hex[:8]}@test.com",
                    "full_name": "User B",
                    "password": "password123",
                    "tenant_id": str(t2_id),
                    "roles": ["tenant_admin"],
                },
            )
            token_b = resp_b.json()["access_token"]

            # Upload CSV in tenant A
            agent_code = f"ISO-{uuid.uuid4().hex[:6]}"
            csv_data = _make_csv(
                ["agent_code", "full_name", "phone"],
                [[agent_code, "Agent A", "9111111111"]],
            )

            await client.post(
                "/api/v1/integration/upload",
                files={"file": ("agents.csv", csv_data, "text/csv")},
                data={"source_system": "pas"},
                headers={"Authorization": f"Bearer {token_a}"},
            )

            # Tenant B should see no jobs
            jobs_b = await client.get(
                "/api/v1/integration/jobs",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert jobs_b.status_code == 200
            assert len(jobs_b.json()["data"]) == 0

            # Tenant A should see the job
            jobs_a = await client.get(
                "/api/v1/integration/jobs",
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert jobs_a.status_code == 200
            assert len(jobs_a.json()["data"]) >= 1

        finally:
            with sync_engine.begin() as conn:
                conn.execute(text("DELETE FROM integration_jobs WHERE tenant_id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM signals WHERE tenant_id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM agents WHERE tenant_id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM users WHERE tenant_id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM tenants WHERE id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})


# ─── Job Listing Tests ───


class TestJobListing:
    async def test_list_jobs_paginated(
        self, client: AsyncClient, auth_token: str, test_tenant: dict
    ):
        """List integration jobs with pagination."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        # Upload a few files to create jobs
        for i in range(3):
            code = f"JOB-{uuid.uuid4().hex[:6]}"
            csv_data = _make_csv(
                ["agent_code", "full_name", "phone"],
                [[code, f"Agent {i}", f"9{i}11111111"]],
            )
            await client.post(
                "/api/v1/integration/upload",
                files={"file": (f"agents_{i}.csv", csv_data, "text/csv")},
                data={"source_system": "pas"},
                headers=headers,
            )

        resp = await client.get(
            "/api/v1/integration/jobs?limit=2",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 2
        assert data["has_more"] is True

    async def test_get_job_details(
        self, client: AsyncClient, auth_token: str, test_tenant: dict
    ):
        """Get individual job details."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        code = f"DET-{uuid.uuid4().hex[:6]}"
        csv_data = _make_csv(
            ["agent_code", "full_name", "phone"],
            [[code, "Detail Agent", "9333333333"]],
        )
        upload_resp = await client.post(
            "/api/v1/integration/upload",
            files={"file": ("detail.csv", csv_data, "text/csv")},
            data={"source_system": "pas"},
            headers=headers,
        )
        assert upload_resp.status_code == 201
        job_id = upload_resp.json()["id"]

        # Get job details
        resp = await client.get(
            f"/api/v1/integration/jobs/{job_id}",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == job_id
        assert resp.json()["source_system"] == "pas"
        assert resp.json()["job_type"] == "csv_upload"


# ─── Validation Tests ───


class TestUploadValidation:
    async def test_invalid_source_system(
        self, client: AsyncClient, auth_token: str
    ):
        headers = {"Authorization": f"Bearer {auth_token}"}
        csv_data = _make_csv(["a"], [["b"]])

        resp = await client.post(
            "/api/v1/integration/upload",
            files={"file": ("test.csv", csv_data, "text/csv")},
            data={"source_system": "invalid"},
            headers=headers,
        )
        assert resp.status_code == 400

    async def test_invalid_file_type(
        self, client: AsyncClient, auth_token: str
    ):
        headers = {"Authorization": f"Bearer {auth_token}"}

        resp = await client.post(
            "/api/v1/integration/upload",
            files={"file": ("test.txt", b"hello", "text/plain")},
            data={"source_system": "pas"},
            headers=headers,
        )
        assert resp.status_code == 400

    async def test_empty_file(
        self, client: AsyncClient, auth_token: str
    ):
        headers = {"Authorization": f"Bearer {auth_token}"}

        resp = await client.post(
            "/api/v1/integration/upload",
            files={"file": ("test.csv", b"", "text/csv")},
            data={"source_system": "pas"},
            headers=headers,
        )
        assert resp.status_code == 400


# ─── Adapter Type Enum Tests ───


class TestAdapterType:
    def test_adapter_type_enum_values(self):
        """Spec 3.6.1: AdapterType enum has all five types."""
        from modules.integration.base import AdapterType

        assert AdapterType.REALTIME_API == "realtime_api"
        assert AdapterType.BATCH_FILE == "batch_file"
        assert AdapterType.WEBHOOK == "webhook"
        assert AdapterType.MANUAL_UPLOAD == "manual_upload"
        assert AdapterType.DATABASE_SYNC == "database_sync"

    def test_adapters_have_type(self):
        """All adapters expose adapter_type."""
        from modules.integration.pas_adapter import PASAgentAdapter, PASPolicyAdapter
        from modules.integration.lms_adapter import LMSTrainingAdapter
        from modules.integration.commission_adapter import CommissionAdapter
        from modules.integration.base import AdapterType

        for adapter in (PASAgentAdapter(), PASPolicyAdapter(), LMSTrainingAdapter(), CommissionAdapter()):
            assert adapter.adapter_type == AdapterType.BATCH_FILE


# ─── Phone Validation Tests ───


class TestPhoneValidation:
    def test_valid_indian_phone(self):
        from modules.integration.pas_adapter import _validate_phone

        assert _validate_phone("9876543210") is True
        assert _validate_phone("6123456789") is True
        assert _validate_phone("7000000000") is True
        assert _validate_phone("8999999999") is True

    def test_invalid_phone(self):
        from modules.integration.pas_adapter import _validate_phone

        assert _validate_phone("1234567890") is False  # Starts with 1
        assert _validate_phone("12345") is False        # Too short
        assert _validate_phone("abcdefghij") is False   # Non-numeric

    def test_phone_with_country_code(self):
        from modules.integration.pas_adapter import _validate_phone

        assert _validate_phone("+919876543210") is True
        assert _validate_phone("919876543210") is True


# ─── Commission Idempotency Key Tests ───


class TestCommissionIdempotencyKey:
    def test_uses_policy_number_not_amount(self):
        """Commission idempotency key uses policy_number (not amount)."""
        from modules.integration.commission_adapter import CommissionAdapter

        adapter = CommissionAdapter()
        row = {
            "agent_code": "A001",
            "amount": "15000",
            "credit_date": "2025-01-15",
            "policy_number": "POL-001",
        }
        key = adapter.get_idempotency_key(row)
        assert key == "commission_sync:A001:2025-01-15:POL-001"
        assert "15000" not in key  # amount should NOT be in the key


# ─── Agent Import Endpoint Tests ───


class TestAgentImportEndpoint:
    async def test_agents_import_endpoint(
        self, client: AsyncClient, auth_token: str, test_tenant: dict
    ):
        """POST /api/v1/agents/import — bulk CSV import (spec 4.13)."""
        headers = {"Authorization": f"Bearer {auth_token}"}
        code = f"IMP-{uuid.uuid4().hex[:6]}"

        csv_data = _make_csv(
            ["agent_code", "full_name", "phone"],
            [[code, "Import Agent", "9444444444"]],
        )

        resp = await client.post(
            "/api/v1/agents/import",
            files={"file": ("agents.csv", csv_data, "text/csv")},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["source_system"] == "pas"
        assert data["total_records"] == 1

    async def test_agents_import_rejects_bad_file(
        self, client: AsyncClient, auth_token: str
    ):
        """POST /api/v1/agents/import rejects non-CSV files."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        resp = await client.post(
            "/api/v1/agents/import",
            files={"file": ("test.txt", b"hello", "text/plain")},
            headers=headers,
        )
        assert resp.status_code == 400


# ─── Integration Status Endpoint Tests ───


class TestIntegrationStatus:
    async def test_status_endpoint(
        self, client: AsyncClient, auth_token: str, test_tenant: dict
    ):
        """GET /api/v1/integration/status returns system summary."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        # First upload something
        code = f"STAT-{uuid.uuid4().hex[:6]}"
        csv_data = _make_csv(
            ["agent_code", "full_name", "phone"],
            [[code, "Status Agent", "9555555555"]],
        )
        await client.post(
            "/api/v1/integration/upload",
            files={"file": ("agents.csv", csv_data, "text/csv")},
            data={"source_system": "pas"},
            headers=headers,
        )

        resp = await client.get(
            "/api/v1/integration/status",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "systems" in data
        assert "pas" in data["systems"]
        assert data["systems"]["pas"]["total_jobs"] >= 1
