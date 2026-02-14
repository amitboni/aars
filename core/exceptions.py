"""core/exceptions.py — Domain exceptions."""
from __future__ import annotations

import uuid


class AARSError(Exception):
    """Base exception for all AARS errors."""

    def __init__(self, code: str, message: str, details: dict | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


class NotFoundError(AARSError):
    """Resource not found."""

    def __init__(self, resource: str, resource_id: uuid.UUID | str):
        super().__init__(
            code=f"{resource.upper()}_NOT_FOUND",
            message=f"{resource} with id {resource_id} not found in this tenant",
            details={"resource": resource, "id": str(resource_id)},
        )


class ConflictError(AARSError):
    """Resource already exists or state conflict."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(code="CONFLICT", message=message, details=details)


class ValidationError(AARSError):
    """Input validation failed."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(code="VALIDATION_ERROR", message=message, details=details)


class AuthenticationError(AARSError):
    """Authentication failed."""

    def __init__(self, message: str = "Invalid or expired token"):
        super().__init__(code="AUTHENTICATION_ERROR", message=message)


class AuthorizationError(AARSError):
    """Authorization failed — insufficient permissions."""

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(code="AUTHORIZATION_ERROR", message=message)


class TenantContextError(AARSError):
    """Tenant context not set."""

    def __init__(self):
        super().__init__(code="TENANT_CONTEXT_ERROR", message="Tenant context not set")


class SignalProcessingError(AARSError):
    """Error during signal processing."""

    def __init__(self, message: str, signal_id: uuid.UUID | None = None):
        super().__init__(
            code="SIGNAL_PROCESSING_ERROR",
            message=message,
            details={"signal_id": str(signal_id)} if signal_id else {},
        )


class ExternalServiceError(AARSError):
    """Error communicating with external service."""

    def __init__(self, service: str, message: str, details: dict | None = None):
        super().__init__(
            code="EXTERNAL_SERVICE_ERROR",
            message=f"{service}: {message}",
            details={"service": service, **(details or {})},
        )
