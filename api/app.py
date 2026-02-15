"""api/app.py — FastAPI app factory."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.health import router as health_router
from config.settings import settings
from core.exceptions import AARSError


def create_app() -> FastAPI:
    app = FastAPI(
        title="AARS — Agent Activation & Retention System",
        version="0.1.0",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    @app.exception_handler(AARSError)
    async def aars_error_handler(request, exc: AARSError):
        status_map = {
            "VALIDATION_ERROR": 400,
            "AUTHENTICATION_ERROR": 401,
            "AUTHORIZATION_ERROR": 403,
            "CONFLICT": 409,
            "SIGNAL_PROCESSING_ERROR": 422,
            "EXTERNAL_SERVICE_ERROR": 502,
        }
        # Default to 404 for NOT_FOUND codes, 500 for unknown
        if exc.code.endswith("_NOT_FOUND"):
            status_code = 404
        else:
            status_code = status_map.get(exc.code, 500)
        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    # Routers
    app.include_router(health_router)

    from modules.user.router import router as user_router
    from modules.tenant.router import router as tenant_router
    from modules.agent.router import router as agent_router
    from modules.signal.router import router as signal_router
    from modules.playbook.router import router as playbook_router
    from modules.channel.voice.webhook_router import router as voice_webhook_router
    from modules.channel.whatsapp.webhook_router import router as whatsapp_webhook_router
    from modules.adm.router import router as adm_router
    from modules.decision.router import router as decision_router
    from modules.analytics.router import router as analytics_router
    from modules.integration.router import router as integration_router
    from modules.content.router import router as content_router
    from modules.training.router import router as training_router
    from modules.settings.router import router as settings_router

    app.include_router(user_router)
    app.include_router(tenant_router)
    app.include_router(agent_router)
    app.include_router(signal_router)
    app.include_router(playbook_router)
    app.include_router(voice_webhook_router)
    app.include_router(whatsapp_webhook_router)
    app.include_router(adm_router)
    app.include_router(decision_router)
    app.include_router(analytics_router)
    app.include_router(integration_router)
    app.include_router(content_router)
    app.include_router(training_router)
    app.include_router(settings_router)

    return app
