"""Tests for training module CRUD, quiz upsert, progress tracking, and tenant isolation."""
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
            "email": f"train-{uuid.uuid4().hex[:8]}@test.com",
            "full_name": "Training Test User",
            "password": "testpass123",
            "tenant_id": str(test_tenant["id"]),
            "roles": ["tenant_admin"],
        },
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


@pytest.fixture
def test_agent(test_tenant: dict) -> dict:
    """Create a test agent for training operations."""
    agent_id = uuid.uuid4()
    agent_code = f"TR-AGT-{agent_id.hex[:8]}"
    adm_id = uuid.uuid4()
    with sync_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO agents (id, tenant_id, agent_code, full_name, phone, "
                "lifecycle_state, assigned_adm_id) "
                "VALUES (:id, :tid, :code, :name, :phone, :state, :adm)"
            ),
            {
                "id": str(agent_id),
                "tid": str(test_tenant["id"]),
                "code": agent_code,
                "name": "Training Test Agent",
                "phone": "9876543211",
                "state": "dormant",
                "adm": str(adm_id),
            },
        )

    yield {
        "id": agent_id,
        "agent_code": agent_code,
        "tenant_id": test_tenant["id"],
        "adm_id": adm_id,
    }

    with sync_engine.begin() as conn:
        conn.execute(
            text("DELETE FROM training_progress WHERE agent_id = :aid"),
            {"aid": str(agent_id)},
        )
        conn.execute(
            text("DELETE FROM signals WHERE agent_id = :aid"),
            {"aid": str(agent_id)},
        )
        conn.execute(
            text("DELETE FROM agents WHERE id = :aid"),
            {"aid": str(agent_id)},
        )


def _build_module_payload(title: str | None = None) -> dict:
    """Helper to build a valid training module creation payload."""
    return {
        "title": title or f"Test Module {uuid.uuid4().hex[:8]}",
        "description": "A test training module for unit testing",
        "topic": "product_knowledge",
        "difficulty": "beginner",
        "duration_minutes": 15,
        "language": "hi",
        "content_type": "video",
    }


def _build_quiz_payload() -> dict:
    """Helper to build a valid quiz creation payload."""
    return {
        "questions": [
            {
                "question": "Term life insurance ka kya matlab hai?",
                "options": [
                    "Fixed term ke liye coverage",
                    "Lifetime coverage",
                    "Investment plan",
                    "Health insurance",
                ],
                "correct": 0,
                "explanation": "Term life sirf fixed years ke liye hota hai.",
            },
            {
                "question": "Premium kaise decide hota hai?",
                "options": [
                    "Age aur coverage amount se",
                    "Random hota hai",
                    "Sabka same hota hai",
                    "Bank decide karta hai",
                ],
                "correct": 0,
                "explanation": "Premium age aur coverage par depend karta hai.",
            },
        ],
        "passing_score": 70,
        "max_attempts": 3,
    }


# ─── Training Module CRUD Tests ──────────────────────────────────────────────


class TestTrainingModuleCreate:
    async def test_create_module_success(
        self, client: AsyncClient, auth_token: str, test_tenant: dict
    ):
        payload = _build_module_payload()
        resp = await client.post(
            "/api/v1/training/modules",
            json=payload,
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == payload["title"]
        assert data["topic"] == "product_knowledge"
        assert data["difficulty"] == "beginner"
        assert data["duration_minutes"] == 15
        assert data["language"] == "hi"
        assert data["content_type"] == "video"
        assert data["is_active"] is True
        assert data["is_default"] is False
        assert data["effectiveness_score"] == 0.0
        assert data["times_assigned"] == 0
        assert data["tenant_id"] == str(test_tenant["id"])

    async def test_create_module_minimal(
        self, client: AsyncClient, auth_token: str
    ):
        payload = {
            "title": f"Minimal-{uuid.uuid4().hex[:8]}",
            "topic": "sales_skills",
            "duration_minutes": 5,
        }
        resp = await client.post(
            "/api/v1/training/modules",
            json=payload,
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["difficulty"] == "beginner"  # default
        assert data["language"] == "hi"  # default
        assert data["content_type"] == "video"  # default

    async def test_create_module_invalid_duration(
        self, client: AsyncClient, auth_token: str
    ):
        payload = _build_module_payload()
        payload["duration_minutes"] = 0  # must be >= 1
        resp = await client.post(
            "/api/v1/training/modules",
            json=payload,
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 422


class TestTrainingModuleRead:
    async def test_get_module(self, client: AsyncClient, auth_token: str):
        headers = {"Authorization": f"Bearer {auth_token}"}
        payload = _build_module_payload()
        create_resp = await client.post("/api/v1/training/modules", json=payload, headers=headers)
        module_id = create_resp.json()["id"]

        get_resp = await client.get(f"/api/v1/training/modules/{module_id}", headers=headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == module_id
        assert get_resp.json()["title"] == payload["title"]

    async def test_get_nonexistent_module(self, client: AsyncClient, auth_token: str):
        fake_id = uuid.uuid4()
        resp = await client.get(
            f"/api/v1/training/modules/{fake_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 404

    async def test_list_modules(self, client: AsyncClient, auth_token: str):
        headers = {"Authorization": f"Bearer {auth_token}"}
        for _ in range(3):
            await client.post("/api/v1/training/modules", json=_build_module_payload(), headers=headers)

        resp = await client.get("/api/v1/training/modules", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) >= 3
        assert "next_cursor" in data
        assert "has_more" in data

    async def test_list_modules_filter_topic(self, client: AsyncClient, auth_token: str):
        headers = {"Authorization": f"Bearer {auth_token}"}

        payload_pk = _build_module_payload()
        payload_pk["topic"] = "product_knowledge"
        await client.post("/api/v1/training/modules", json=payload_pk, headers=headers)

        payload_sales = _build_module_payload()
        payload_sales["topic"] = "sales_skills"
        await client.post("/api/v1/training/modules", json=payload_sales, headers=headers)

        resp = await client.get(
            "/api/v1/training/modules?topic=product_knowledge", headers=headers
        )
        assert resp.status_code == 200
        for mod in resp.json()["data"]:
            assert mod["topic"] == "product_knowledge"

    async def test_list_modules_pagination(self, client: AsyncClient, auth_token: str):
        headers = {"Authorization": f"Bearer {auth_token}"}
        for _ in range(3):
            await client.post("/api/v1/training/modules", json=_build_module_payload(), headers=headers)

        resp = await client.get("/api/v1/training/modules?limit=2", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 2
        assert data["has_more"] is True
        assert data["next_cursor"] is not None

        # Fetch next page
        resp2 = await client.get(
            f"/api/v1/training/modules?limit=2&cursor={data['next_cursor']}",
            headers=headers,
        )
        assert resp2.status_code == 200
        assert len(resp2.json()["data"]) >= 1


class TestTrainingModuleUpdate:
    async def test_update_module(self, client: AsyncClient, auth_token: str):
        headers = {"Authorization": f"Bearer {auth_token}"}
        create_resp = await client.post(
            "/api/v1/training/modules", json=_build_module_payload(), headers=headers
        )
        module_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/v1/training/modules/{module_id}",
            json={"title": "Updated Title", "difficulty": "intermediate"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated Title"
        assert data["difficulty"] == "intermediate"

    async def test_deactivate_module(self, client: AsyncClient, auth_token: str):
        headers = {"Authorization": f"Bearer {auth_token}"}
        create_resp = await client.post(
            "/api/v1/training/modules", json=_build_module_payload(), headers=headers
        )
        module_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/v1/training/modules/{module_id}",
            json={"is_active": False},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False


class TestTrainingModuleDelete:
    async def test_soft_delete_module(self, client: AsyncClient, auth_token: str):
        headers = {"Authorization": f"Bearer {auth_token}"}
        create_resp = await client.post(
            "/api/v1/training/modules", json=_build_module_payload(), headers=headers
        )
        module_id = create_resp.json()["id"]

        del_resp = await client.delete(
            f"/api/v1/training/modules/{module_id}", headers=headers
        )
        assert del_resp.status_code == 204

        get_resp = await client.get(
            f"/api/v1/training/modules/{module_id}", headers=headers
        )
        assert get_resp.status_code == 404

    async def test_soft_delete_nonexistent(self, client: AsyncClient, auth_token: str):
        fake_id = uuid.uuid4()
        resp = await client.delete(
            f"/api/v1/training/modules/{fake_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 404


# ─── Quiz Tests ──────────────────────────────────────────────────────────────


class TestQuiz:
    async def test_create_quiz(self, client: AsyncClient, auth_token: str):
        headers = {"Authorization": f"Bearer {auth_token}"}
        # Create module first
        mod_resp = await client.post(
            "/api/v1/training/modules", json=_build_module_payload(), headers=headers
        )
        module_id = mod_resp.json()["id"]

        quiz_payload = _build_quiz_payload()
        resp = await client.put(
            f"/api/v1/training/modules/{module_id}/quiz",
            json=quiz_payload,
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["training_module_id"] == module_id
        assert len(data["questions"]) == 2
        assert data["passing_score"] == 70
        assert data["max_attempts"] == 3

    async def test_update_quiz(self, client: AsyncClient, auth_token: str):
        headers = {"Authorization": f"Bearer {auth_token}"}
        mod_resp = await client.post(
            "/api/v1/training/modules", json=_build_module_payload(), headers=headers
        )
        module_id = mod_resp.json()["id"]

        # Create quiz
        await client.put(
            f"/api/v1/training/modules/{module_id}/quiz",
            json=_build_quiz_payload(),
            headers=headers,
        )

        # Update quiz (upsert)
        updated_quiz = _build_quiz_payload()
        updated_quiz["passing_score"] = 80
        updated_quiz["questions"].append({
            "question": "Naya sawaal?",
            "options": ["A", "B", "C", "D"],
            "correct": 1,
            "explanation": "B sahi hai",
        })

        resp = await client.put(
            f"/api/v1/training/modules/{module_id}/quiz",
            json=updated_quiz,
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["passing_score"] == 80
        assert len(data["questions"]) == 3

    async def test_get_quiz(self, client: AsyncClient, auth_token: str):
        headers = {"Authorization": f"Bearer {auth_token}"}
        mod_resp = await client.post(
            "/api/v1/training/modules", json=_build_module_payload(), headers=headers
        )
        module_id = mod_resp.json()["id"]

        await client.put(
            f"/api/v1/training/modules/{module_id}/quiz",
            json=_build_quiz_payload(),
            headers=headers,
        )

        resp = await client.get(
            f"/api/v1/training/modules/{module_id}/quiz", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["training_module_id"] == module_id
        assert len(resp.json()["questions"]) == 2

    async def test_get_quiz_not_found(self, client: AsyncClient, auth_token: str):
        headers = {"Authorization": f"Bearer {auth_token}"}
        mod_resp = await client.post(
            "/api/v1/training/modules", json=_build_module_payload(), headers=headers
        )
        module_id = mod_resp.json()["id"]

        resp = await client.get(
            f"/api/v1/training/modules/{module_id}/quiz", headers=headers
        )
        assert resp.status_code == 404

    async def test_quiz_for_nonexistent_module(self, client: AsyncClient, auth_token: str):
        fake_id = uuid.uuid4()
        resp = await client.put(
            f"/api/v1/training/modules/{fake_id}/quiz",
            json=_build_quiz_payload(),
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 404


# ─── Training Progress Tests ─────────────────────────────────────────────────


class TestTrainingProgress:
    async def test_assign_module_to_agent(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        headers = {"Authorization": f"Bearer {auth_token}"}
        mod_resp = await client.post(
            "/api/v1/training/modules", json=_build_module_payload(), headers=headers
        )
        module_id = mod_resp.json()["id"]

        assign_resp = await client.post(
            "/api/v1/training/progress",
            json={
                "training_module_id": module_id,
                "agent_id": str(test_agent["id"]),
                "assigned_by": "test",
            },
            headers=headers,
        )
        assert assign_resp.status_code == 201
        data = assign_resp.json()
        assert data["training_module_id"] == module_id
        assert data["agent_id"] == str(test_agent["id"])
        assert data["status"] == "assigned"
        assert data["score"] is None
        assert data["attempts"] == 0
        assert data["assigned_by"] == "test"

    async def test_assign_increments_times_assigned(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        headers = {"Authorization": f"Bearer {auth_token}"}
        mod_resp = await client.post(
            "/api/v1/training/modules", json=_build_module_payload(), headers=headers
        )
        module_id = mod_resp.json()["id"]
        assert mod_resp.json()["times_assigned"] == 0

        await client.post(
            "/api/v1/training/progress",
            json={
                "training_module_id": module_id,
                "agent_id": str(test_agent["id"]),
            },
            headers=headers,
        )

        get_resp = await client.get(
            f"/api/v1/training/modules/{module_id}", headers=headers
        )
        assert get_resp.json()["times_assigned"] == 1

    async def test_update_progress(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        headers = {"Authorization": f"Bearer {auth_token}"}
        mod_resp = await client.post(
            "/api/v1/training/modules", json=_build_module_payload(), headers=headers
        )
        module_id = mod_resp.json()["id"]

        assign_resp = await client.post(
            "/api/v1/training/progress",
            json={
                "training_module_id": module_id,
                "agent_id": str(test_agent["id"]),
            },
            headers=headers,
        )
        progress_id = assign_resp.json()["id"]

        # Update to in_progress
        update_resp = await client.put(
            f"/api/v1/training/progress/{progress_id}",
            json={"status": "in_progress", "attempts": 1},
            headers=headers,
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["status"] == "in_progress"
        assert update_resp.json()["attempts"] == 1

        # Complete with score
        complete_resp = await client.put(
            f"/api/v1/training/progress/{progress_id}",
            json={"status": "completed", "score": 85.0},
            headers=headers,
        )
        assert complete_resp.status_code == 200
        assert complete_resp.json()["status"] == "completed"
        assert complete_resp.json()["score"] == 85.0

    async def test_list_progress(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        headers = {"Authorization": f"Bearer {auth_token}"}
        mod_resp = await client.post(
            "/api/v1/training/modules", json=_build_module_payload(), headers=headers
        )
        module_id = mod_resp.json()["id"]

        await client.post(
            "/api/v1/training/progress",
            json={
                "training_module_id": module_id,
                "agent_id": str(test_agent["id"]),
            },
            headers=headers,
        )

        resp = await client.get("/api/v1/training/progress", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) >= 1
        assert "next_cursor" in data
        assert "has_more" in data

    async def test_list_progress_filter_by_agent(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        headers = {"Authorization": f"Bearer {auth_token}"}
        mod_resp = await client.post(
            "/api/v1/training/modules", json=_build_module_payload(), headers=headers
        )
        module_id = mod_resp.json()["id"]

        await client.post(
            "/api/v1/training/progress",
            json={
                "training_module_id": module_id,
                "agent_id": str(test_agent["id"]),
            },
            headers=headers,
        )

        resp = await client.get(
            f"/api/v1/training/progress?agent_id={test_agent['id']}", headers=headers
        )
        assert resp.status_code == 200
        for p in resp.json()["data"]:
            assert p["agent_id"] == str(test_agent["id"])

    async def test_list_progress_filter_by_status(
        self, client: AsyncClient, auth_token: str, test_agent: dict
    ):
        headers = {"Authorization": f"Bearer {auth_token}"}
        mod_resp = await client.post(
            "/api/v1/training/modules", json=_build_module_payload(), headers=headers
        )
        module_id = mod_resp.json()["id"]

        await client.post(
            "/api/v1/training/progress",
            json={
                "training_module_id": module_id,
                "agent_id": str(test_agent["id"]),
            },
            headers=headers,
        )

        resp = await client.get(
            "/api/v1/training/progress?status=assigned", headers=headers
        )
        assert resp.status_code == 200
        for p in resp.json()["data"]:
            assert p["status"] == "assigned"

    async def test_update_nonexistent_progress(self, client: AsyncClient, auth_token: str):
        fake_id = uuid.uuid4()
        resp = await client.put(
            f"/api/v1/training/progress/{fake_id}",
            json={"status": "completed"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert resp.status_code == 404


# ─── Tenant Isolation Tests ─────────────────────────────────────────────────


class TestTrainingTenantIsolation:
    async def test_modules_isolated_between_tenants(self, client: AsyncClient):
        """Training modules from tenant A should not be visible to tenant B."""
        t1_id, t2_id = uuid.uuid4(), uuid.uuid4()

        with sync_engine.begin() as conn:
            for tid, slug in [
                (t1_id, f"trn-a-{t1_id.hex[:6]}"),
                (t2_id, f"trn-b-{t2_id.hex[:6]}"),
            ]:
                conn.execute(
                    text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
                    {"id": str(tid), "name": f"Tenant {slug}", "slug": slug},
                )

        try:
            resp_a = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"trn-a-{uuid.uuid4().hex[:8]}@test.com",
                    "full_name": "Training User A",
                    "password": "password123",
                    "tenant_id": str(t1_id),
                    "roles": ["tenant_admin"],
                },
            )
            token_a = resp_a.json()["access_token"]

            resp_b = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"trn-b-{uuid.uuid4().hex[:8]}@test.com",
                    "full_name": "Training User B",
                    "password": "password123",
                    "tenant_id": str(t2_id),
                    "roles": ["tenant_admin"],
                },
            )
            token_b = resp_b.json()["access_token"]

            # Create module in tenant A
            mod_resp = await client.post(
                "/api/v1/training/modules",
                json=_build_module_payload(),
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert mod_resp.status_code == 201
            module_id_a = mod_resp.json()["id"]

            # Tenant B should NOT see tenant A's module
            list_resp_b = await client.get(
                "/api/v1/training/modules",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert list_resp_b.status_code == 200
            for mod in list_resp_b.json()["data"]:
                assert mod["id"] != module_id_a
                assert mod["tenant_id"] == str(t2_id)

            # Tenant B trying to GET tenant A's module should 404
            get_resp = await client.get(
                f"/api/v1/training/modules/{module_id_a}",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert get_resp.status_code == 404

        finally:
            with sync_engine.begin() as conn:
                conn.execute(text("DELETE FROM training_progress WHERE tenant_id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM training_quizzes WHERE training_module_id IN (SELECT id FROM training_modules WHERE tenant_id IN (:t1, :t2))"), {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM training_modules WHERE tenant_id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM signals WHERE tenant_id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM users WHERE tenant_id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})
                conn.execute(text("DELETE FROM tenants WHERE id IN (:t1, :t2)"), {"t1": str(t1_id), "t2": str(t2_id)})
