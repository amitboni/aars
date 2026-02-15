"""tests/test_integration/conftest.py — Ensure all models are loaded for integration tests."""
# Import all models so SQLAlchemy relationship mappings resolve correctly
# when running integration tests in isolation.
import modules.tenant.models  # noqa: F401
import modules.user.models  # noqa: F401
import modules.agent.models  # noqa: F401
import modules.signal.models  # noqa: F401
import modules.playbook.models  # noqa: F401
import modules.adm.models  # noqa: F401
import modules.decision.models  # noqa: F401
import modules.analytics.models  # noqa: F401
import modules.integration.models  # noqa: F401
import modules.content.models  # noqa: F401
import modules.training.models  # noqa: F401
import modules.settings.models  # noqa: F401
