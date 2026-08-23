from typing import Any, Dict, Optional

from allauth.headless.socialaccount.internal import complete_token_login
from allauth.socialaccount.adapter import get_adapter as get_socialaccount_adapter
from allauth.socialaccount.models import SocialApp
from django.core.exceptions import ValidationError
from django.db.utils import OperationalError
from rest_framework.exceptions import AuthenticationFailed

from account.serializers import UserSerializer
from account.services.auth_service import generate_tokens_for_user


def google_social_login_service(
    request,
    id_token: Optional[str] = None,
    access_token: Optional[str] = None,
    client_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Service to perform Google social authentication using django-allauth headless flow,
    create or fetch the user model, and return SimpleJWT tokens with user data.
    """
    token_data = {}
    if id_token:
        token_data["id_token"] = id_token
    if access_token:
        token_data["access_token"] = access_token
    if client_id:
        token_data["client_id"] = client_id

    if not token_data.get("id_token") and not token_data.get("access_token"):
        raise AuthenticationFailed(
            "At least one of id_token or access_token must be provided."
        )

    adapter = get_socialaccount_adapter()
    try:
        provider = adapter.get_provider(request, "google", client_id=client_id)
    except (SocialApp.DoesNotExist, OperationalError):
        from allauth.socialaccount.providers.google.provider import GoogleProvider

        provider = GoogleProvider(request=request)

    try:
        sociallogin = provider.verify_token(request, token_data)
        sociallogin.state["process"] = "login"
        complete_token_login(request, sociallogin)
    except ValidationError as e:
        msg = e.messages if hasattr(e, "messages") else str(e)
        raise AuthenticationFailed(detail=msg)
    except Exception as e:
        raise AuthenticationFailed(detail=str(e))

    user = sociallogin.user
    tokens = generate_tokens_for_user(user)

    return {
        "user": UserSerializer(user).data,
        "tokens": tokens,
    }
