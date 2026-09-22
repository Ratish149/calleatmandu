from typing import Any, Dict, Optional

from django.conf import settings
from zernio import Zernio


class ZernioService:
    """Service to handle Zernio SDK operations for OAuth connections, accounts, and inbox messaging."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, "ZERNIO_KEY", "")
        if not self.api_key:
            raise ValueError(
                "Zernio API Key is missing. Ensure ZERNIO_KEY is set in settings/.env."
            )
        self.client = Zernio(api_key=self.api_key)

    def get_connect_url(
        self,
        platform: str,
        profile_id: str,
        redirect_url: Optional[str] = None,
        headless: Optional[bool] = False,
        login_method: Optional[str] = "instagram_login",
        onboarding: Optional[str] = None,
        signup: Optional[str] = None,
        brand_name: Optional[str] = None,
        primary_color: Optional[str] = None,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Initiate OAuth connection flow for a platform."""
        kwargs: Dict[str, Any] = {}
        if redirect_url:
            kwargs["redirect_url"] = redirect_url
        if headless is not None:
            kwargs["headless"] = headless
        if login_method:
            kwargs["login_method"] = login_method
        if onboarding:
            kwargs["onboarding"] = onboarding
        if signup:
            kwargs["signup"] = signup
        if brand_name:
            kwargs["brand_name"] = brand_name
        if primary_color:
            kwargs["primary_color"] = primary_color
        if language:
            kwargs["language"] = language

        return self.client.connect.get_connect_url(
            platform=platform,
            profile_id=profile_id,
            **kwargs,
        )

    def handle_oauth_callback(
        self,
        platform: str,
        code: str,
        state: str,
        profile_id: str,
    ) -> Dict[str, Any]:
        """Complete OAuth callback by exchanging authorization code for connected account tokens."""
        return self.client.connect.handle_o_auth_callback(
            platform=platform,
            code=code,
            state=state,
            profile_id=profile_id,
        )

    def send_inbox_message(
        self,
        conversation_id: str,
        account_id: str,
        message: str,
    ) -> Dict[str, Any]:
        """Send an outbound message via Zernio Inbox API."""
        return self.client.messages.send_inbox_message(
            conversation_id=conversation_id,
            account_id=account_id,
            message=message,
        )

    def delete_account(self, account_id: str) -> Dict[str, Any]:
        """Delete / unlink a social account from Zernio."""
        return self.client.accounts.delete_account(account_id=account_id)

    def get_or_create_profile_id(self, organization_id: str) -> str:
        """Get or create Zernio Profile ID for an organization."""
        try:
            profiles_response = self.client.profiles.list_profiles()
            profiles = profiles_response.get("profiles", [])
            for profile in profiles:
                if profile.get("name") == f"Org-{organization_id}":
                    return profile.get("id") or profile.get("_id")

            # Create if not found
            new_profile = self.client.profiles.create_profile(
                name=f"Org-{organization_id}"
            )
            return new_profile.get("id") or new_profile.get("_id") or organization_id
        except Exception:
            # Fallback to organization_id as profile_id if list/create is restricted
            return organization_id
