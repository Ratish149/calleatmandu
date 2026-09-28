import contextvars
from typing import Optional

from rest_framework_simplejwt.authentication import JWTAuthentication

_current_user_var = contextvars.ContextVar("current_user", default=None)
_current_ip_var = contextvars.ContextVar("current_ip", default=None)


def set_current_user(user: Optional[object]) -> None:
    """Store the authenticated user for the current request context."""
    _current_user_var.set(user)


def get_current_user() -> Optional[object]:
    """Retrieve the authenticated user from the current request context."""
    return _current_user_var.get()


def set_current_ip(ip: Optional[str]) -> None:
    """Store the client IP address for the current request context."""
    _current_ip_var.set(ip)


def get_current_ip() -> Optional[str]:
    """Retrieve the client IP address from the current request context."""
    return _current_ip_var.get()


def clear_current_context() -> None:
    """Clear context variables at the end of a request."""
    _current_user_var.set(None)
    _current_ip_var.set(None)


class CurrentUserMiddleware:
    """
    Middleware that captures the currently authenticated user and client IP
    and stores them in request-scoped context variables so that Django signals,
    models, and services can automatically audit who performed an action.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)

        # If user is not authenticated from session/cookies, try DRF JWT authentication
        if not user or not user.is_authenticated:
            auth_header = request.META.get("HTTP_AUTHORIZATION", "")
            if auth_header.startswith("Bearer "):
                try:
                    auth_result = JWTAuthentication().authenticate(request)
                    if auth_result:
                        user = auth_result[0]
                except Exception:
                    pass

        authenticated_user = user if user and user.is_authenticated else None
        set_current_user(authenticated_user)

        # Extract client IP address
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR")
        set_current_ip(ip)

        try:
            response = self.get_response(request)
        finally:
            clear_current_context()

        return response
