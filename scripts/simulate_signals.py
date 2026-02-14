"""scripts/simulate_signals.py — Generate realistic signal sequences for demo agents.

Usage:
    python scripts/simulate_signals.py --tenant-id <uuid> [--days 90] [--signals-per-day 20]
    python scripts/simulate_signals.py --demo  # Use demo tenant ID
"""
from __future__ import annotations

import argparse
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text

from config.database import sync_engine
from core.enums import SignalSource, SignalType


def _random_timestamp(base: datetime, days_back: int, days_forward: int = 0) -> datetime:
    """Generate a random timestamp within a range."""
    delta = timedelta(
        days=random.randint(-days_back, days_forward),
        hours=random.randint(9, 20),
        minutes=random.randint(0, 59),
    )
    return base + delta


def generate_signals_for_agent(
    tenant_id: uuid.UUID,
    agent_id: uuid.UUID,
    agent_code: str,
    lifecycle_state: str,
    days: int = 90,
) -> list[dict]:
    """Generate realistic signal sequences based on agent's lifecycle state."""
    now = datetime.now(timezone.utc)
    signals = []

    def _sig(signal_type: str, source: str, payload: dict,
             timestamp: datetime | None = None, channel: str | None = None) -> dict:
        import json
        return {
            "id": str(uuid.uuid4()),
            "tenant_id": str(tenant_id),
            "signal_type": signal_type,
            "source": source,
            "agent_id": str(agent_id),
            "timestamp": (timestamp or now).isoformat(),
            "channel": channel,
            "payload": json.dumps(payload),
            "metadata": "{}",
            "idempotency_key": f"sim:{agent_code}:{signal_type}:{uuid.uuid4().hex[:8]}",
            "processed": True,
            "processed_at": (timestamp or now).isoformat(),
        }

    if lifecycle_state == "dormant":
        # Past voice calls (not answered), WhatsApp (delivered but not read)
        for i in range(3):
            ts = _random_timestamp(now, days_back=days - 10, days_forward=-30)
            signals.append(_sig(
                SignalType.VOICE_CALL_OUTCOME, SignalSource.VOICE_AI,
                {"outcome": "not_answered", "duration_seconds": 0},
                timestamp=ts, channel="voice_ai",
            ))
        for i in range(5):
            ts = _random_timestamp(now, days_back=days - 5, days_forward=-20)
            signals.append(_sig(
                SignalType.WHATSAPP_MESSAGE_SENT, SignalSource.WHATSAPP_BOT,
                {"template": "check_in", "status": "sent"},
                timestamp=ts, channel="whatsapp_bot",
            ))
            signals.append(_sig(
                SignalType.WHATSAPP_MESSAGE_DELIVERED, SignalSource.WHATSAPP_BOT,
                {"status": "delivered"},
                timestamp=ts + timedelta(seconds=5), channel="whatsapp_bot",
            ))
        # One eventually answered call with dormancy reason
        ts = _random_timestamp(now, days_back=20)
        signals.append(_sig(
            SignalType.VOICE_CALL_OUTCOME, SignalSource.VOICE_AI,
            {"outcome": "answered", "duration_seconds": 180},
            timestamp=ts, channel="voice_ai",
        ))
        signals.append(_sig(
            SignalType.VOICE_CONVERSATION_ANALYZED, SignalSource.VOICE_AI,
            {"sentiment": "neutral", "dormancy_reason_detected": True},
            timestamp=ts + timedelta(minutes=1), channel="voice_ai",
        ))

    elif lifecycle_state == "active":
        # Regular POLICY_SOLD signals, WhatsApp training, ADM visits
        for i in range(random.randint(3, 8)):
            ts = _random_timestamp(now, days_back=days)
            signals.append(_sig(
                SignalType.POLICY_SOLD, SignalSource.PAS_SYNC,
                {"policy_number": f"POL-{agent_code}-{i+1:03d}", "premium_amount": random.randint(5000, 50000)},
                timestamp=ts,
            ))
        for i in range(random.randint(2, 5)):
            ts = _random_timestamp(now, days_back=days)
            signals.append(_sig(
                SignalType.WHATSAPP_TRAINING_INTERACTION, SignalSource.WHATSAPP_BOT,
                {"completion_percentage": random.randint(60, 100), "interaction_type": "VIDEO_WATCHED"},
                timestamp=ts, channel="whatsapp_bot",
            ))
        if random.random() > 0.5:
            ts = _random_timestamp(now, days_back=30)
            signals.append(_sig(
                SignalType.ADM_AGENT_VISIT_LOGGED, SignalSource.ADM_REPORT,
                {"visit_type": "scheduled", "outcome": "PRODUCTIVE"},
                timestamp=ts,
            ))

    elif lifecycle_state == "at_risk":
        # Declining signal frequency, last positive signal 30+ days ago
        for i in range(random.randint(1, 3)):
            ts = _random_timestamp(now, days_back=days, days_forward=-40)
            signals.append(_sig(
                SignalType.POLICY_SOLD, SignalSource.PAS_SYNC,
                {"policy_number": f"POL-{agent_code}-{i+1:03d}", "premium_amount": random.randint(5000, 30000)},
                timestamp=ts,
            ))
        # Recent WhatsApp sent but no reply
        ts = _random_timestamp(now, days_back=15)
        signals.append(_sig(
            SignalType.WHATSAPP_MESSAGE_SENT, SignalSource.WHATSAPP_BOT,
            {"template": "check_in"},
            timestamp=ts, channel="whatsapp_bot",
        ))
        # Voice call not answered
        ts = _random_timestamp(now, days_back=10)
        signals.append(_sig(
            SignalType.VOICE_CALL_OUTCOME, SignalSource.VOICE_AI,
            {"outcome": "not_answered", "duration_seconds": 0},
            timestamp=ts, channel="voice_ai",
        ))

    elif lifecycle_state == "first_sale":
        # Recent POLICY_SOLD signal
        ts = now - timedelta(days=random.randint(1, 5))
        signals.append(_sig(
            SignalType.POLICY_SOLD, SignalSource.PAS_SYNC,
            {"policy_number": f"POL-{agent_code}-001", "premium_amount": random.randint(8000, 25000)},
            timestamp=ts,
        ))

    elif lifecycle_state == "productive":
        # Many policies, regular engagement
        for i in range(random.randint(6, 12)):
            ts = _random_timestamp(now, days_back=days)
            signals.append(_sig(
                SignalType.POLICY_SOLD, SignalSource.PAS_SYNC,
                {"policy_number": f"POL-{agent_code}-{i+1:03d}", "premium_amount": random.randint(10000, 100000)},
                timestamp=ts,
            ))
        for i in range(random.randint(3, 6)):
            ts = _random_timestamp(now, days_back=60)
            signals.append(_sig(
                SignalType.WHATSAPP_AGENT_REPLIED, SignalSource.WHATSAPP_BOT,
                {"message_type": "text"},
                timestamp=ts, channel="whatsapp_bot",
            ))

    elif lifecycle_state in ("onboarded", "licensed"):
        # Light signals — maybe one voice call, WhatsApp welcome
        ts = _random_timestamp(now, days_back=min(days, 15))
        signals.append(_sig(
            SignalType.WHATSAPP_MESSAGE_SENT, SignalSource.WHATSAPP_BOT,
            {"template": "welcome", "status": "sent"},
            timestamp=ts, channel="whatsapp_bot",
        ))
        if random.random() > 0.5:
            ts = _random_timestamp(now, days_back=min(days, 10))
            signals.append(_sig(
                SignalType.VOICE_CALL_OUTCOME, SignalSource.VOICE_AI,
                {"outcome": random.choice(["answered", "not_answered"]), "duration_seconds": random.randint(0, 120)},
                timestamp=ts, channel="voice_ai",
            ))

    elif lifecycle_state == "lapsed":
        ts = _random_timestamp(now, days_back=60, days_forward=-30)
        signals.append(_sig(
            SignalType.LICENSE_STATUS_CHANGED, SignalSource.LMS_SYNC,
            {"new_status": "EXPIRED", "license_number": f"IRDAI-{agent_code}"},
            timestamp=ts,
        ))

    return signals


def run_simulation(tenant_id: uuid.UUID, days: int = 90, signals_per_day: int = 20):
    """Generate and insert signals for all agents of a tenant."""
    import json

    with sync_engine.begin() as conn:
        result = conn.execute(
            text("SELECT id, agent_code, lifecycle_state FROM agents WHERE tenant_id = :tid AND deleted_at IS NULL"),
            {"tid": str(tenant_id)},
        )
        agents = result.fetchall()

    if not agents:
        print(f"No agents found for tenant {tenant_id}")
        return

    print(f"Generating signals for {len(agents)} agents over {days} days...")

    total_signals = 0
    with sync_engine.begin() as conn:
        for agent_id, agent_code, lifecycle_state in agents:
            signals = generate_signals_for_agent(
                tenant_id, uuid.UUID(str(agent_id)), agent_code, lifecycle_state, days,
            )
            for sig in signals:
                # Check idempotency
                existing = conn.execute(
                    text("SELECT id FROM signals WHERE idempotency_key = :key AND tenant_id = :tid"),
                    {"key": sig["idempotency_key"], "tid": str(tenant_id)},
                ).fetchone()
                if existing:
                    continue

                conn.execute(
                    text("""
                        INSERT INTO signals (id, tenant_id, signal_type, source, agent_id,
                            timestamp, channel, payload, metadata, idempotency_key,
                            processed, processed_at)
                        VALUES (:id, :tenant_id, :signal_type, :source, CAST(:agent_id AS uuid),
                            CAST(:timestamp AS timestamptz), :channel, CAST(:payload AS jsonb), CAST(:metadata AS jsonb),
                            :idempotency_key, :processed, CAST(:processed_at AS timestamptz))
                    """),
                    sig,
                )
                total_signals += 1

    print(f"Inserted {total_signals} signals for {len(agents)} agents.")


def main():
    parser = argparse.ArgumentParser(description="Simulate signals for demo agents")
    parser.add_argument("--tenant-id", type=str, help="Tenant UUID")
    parser.add_argument("--demo", action="store_true", help="Use demo tenant ID")
    parser.add_argument("--days", type=int, default=90, help="Days of history to simulate")
    parser.add_argument("--signals-per-day", type=int, default=20, help="Target signals per day")
    args = parser.parse_args()

    if args.demo:
        from seeds.demo_tenant import DEMO_TENANT_ID
        tenant_id = DEMO_TENANT_ID
    elif args.tenant_id:
        tenant_id = uuid.UUID(args.tenant_id)
    else:
        print("Provide --tenant-id <uuid> or --demo")
        sys.exit(1)

    run_simulation(tenant_id, args.days, args.signals_per_day)


if __name__ == "__main__":
    main()
