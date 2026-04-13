"""Service-layer exceptions."""


class ServiceError(Exception):
    """Base exception for service errors."""


class CheckoutError(ServiceError):
    """Raised when checkout cannot be completed."""