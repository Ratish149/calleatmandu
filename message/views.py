import json
import logging
from typing import Optional, Union

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from message.selectors.messaging_selector import (
    get_conversation_messages,
    get_conversations_for_branch,
    get_linked_accounts_for_branch,
)
from message.serializers import (
    BusinessAccountSerializer,
    ConversationSerializer,
    LinkConversationSerializer,
    MessageSerializer,
    OAuthCallbackRequestSerializer,
    OAuthConnectURLQuerySerializer,
    SendMessageSerializer,
)
from message.services.messaging_service import MessagingService

logger = logging.getLogger(__name__)


def get_branch_id_from_request(request) -> Optional[Union[int, str]]:
    """Extract branch ID based on the authenticated user's token.

    Prioritizes the logged in user's assigned branch from the authentication token (request.user.branch_id).
    If the user has no assigned branch (e.g. admin) or is unauthenticated,
    falls back to query parameters, request headers, or request body.
    """
    if (
        request.user
        and request.user.is_authenticated
        and getattr(request.user, "branch_id", None)
    ):
        return request.user.branch_id

    branch_val = (
        request.query_params.get("branch_id")
        or request.query_params.get("branch")
        or request.headers.get("X-Branch-ID")
    )
    if not branch_val and hasattr(request, "data") and isinstance(request.data, dict):
        branch_val = request.data.get("branch_id") or request.data.get("branch")

    return branch_val


class ConversationListAPIView(APIView):
    """GET /api/conversations/?branch_id=X&person_id=Y List conversations for a branch."""

    permission_classes = [AllowAny]

    def get(self, request):
        branch_id = get_branch_id_from_request(request)
        person_id = request.query_params.get("person_id")

        queryset = get_conversations_for_branch(
            branch_id=branch_id, person_id=person_id
        )
        serializer = ConversationSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ConversationDetailAPIView(APIView):
    """GET /api/conversations/<id>/ Retrieve a conversation.

    DELETE /api/conversations/<id>/ Delete a conversation.
    """

    permission_classes = [AllowAny]

    def get(self, request, pk: str):
        branch_id = get_branch_id_from_request(request)
        service = MessagingService()
        try:
            conversation = service.assert_conversation_belongs_to_branch(pk, branch_id)
            serializer = ConversationSerializer(conversation)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, pk: str):
        branch_id = get_branch_id_from_request(request)
        service = MessagingService()
        try:
            res = service.delete_conversation(pk, branch_id)
            return Response(res, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class ConversationMessagesAPIView(APIView):
    """GET /api/conversations/<id>/messages/ Retrieve messages.

    POST /api/conversations/<id>/messages/ Send outbound message.
    """

    permission_classes = [AllowAny]

    def get(self, request, conversation_id: str):
        branch_id = get_branch_id_from_request(request)
        service = MessagingService()
        try:
            service.assert_conversation_belongs_to_branch(conversation_id, branch_id)
            messages = get_conversation_messages(conversation_id)
            serializer = MessageSerializer(messages, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request, conversation_id: str):
        branch_id = get_branch_id_from_request(request)
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = MessagingService()
        try:
            result = service.send_message(
                conversation_id=conversation_id,
                message_text=serializer.validated_data["message"],
                branch_id=branch_id,
                user=request.user,
            )
            return Response(result, status=status.HTTP_201_CREATED)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class ConversationMarkReadAPIView(APIView):
    """POST /api/conversations/<id>/read/ Mark all inbound messages in conversation as read."""

    permission_classes = [AllowAny]

    def post(self, request, conversation_id: str):
        branch_id = get_branch_id_from_request(request)
        service = MessagingService()
        try:
            res = service.mark_conversation_as_read(conversation_id, branch_id)
            return Response(res, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class ConversationLinkAPIView(APIView):
    """POST /api/conversations/<id>/link/ Link an applicant ID to a conversation."""

    permission_classes = [AllowAny]

    def post(self, request, conversation_id: str):
        branch_id = get_branch_id_from_request(request)
        serializer = LinkConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = MessagingService()
        try:
            conv = service.link_conversation(
                conversation_id=conversation_id,
                applicant_id=serializer.validated_data["applicant_id"],
                branch_id=branch_id,
            )
            return Response(
                ConversationSerializer(conv).data, status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class ConversationUnlinkAPIView(APIView):
    """POST /api/conversations/<id>/unlink/ Unlink applicant ID from conversation."""

    permission_classes = [AllowAny]

    def post(self, request, conversation_id: str):
        branch_id = get_branch_id_from_request(request)
        service = MessagingService()
        try:
            conv = service.unlink_conversation(conversation_id, branch_id)
            return Response(
                ConversationSerializer(conv).data, status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class BusinessAccountListAPIView(APIView):
    """GET /api/messaging/accounts/?branch_id=X List connected business accounts."""

    permission_classes = [AllowAny]

    def get(self, request):
        branch_id = get_branch_id_from_request(request)
        sync = request.query_params.get("sync", "false").lower() in ("true", "1")
        if sync:
            service = MessagingService()
            try:
                service.sync_accounts_from_zernio(branch_id=branch_id)
            except Exception as exc:
                logger.warning(f"Failed to sync accounts from Zernio: {exc}")

        accounts = get_linked_accounts_for_branch(branch_id)
        serializer = BusinessAccountSerializer(accounts, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class BusinessAccountUnlinkAPIView(APIView):
    """DELETE /api/messaging/accounts/<platform>/unlink/?branch_id=X Unlink social account."""

    permission_classes = [AllowAny]

    def delete(self, request, platform: str):
        branch_id = get_branch_id_from_request(request)
        account_id = request.query_params.get("account_id") or (
            request.data.get("account_id") if isinstance(request.data, dict) else None
        )
        service = MessagingService()
        try:
            res = service.unlink_account(
                platform=platform, branch_id=branch_id, account_id=account_id
            )
            return Response(res, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class ZernioConnectAPIView(APIView):
    """GET /api/connect/<platform>/ Get OAuth connect URL.

    POST /api/connect/<platform>/ Exchange code/state for tokens.
    """

    permission_classes = [AllowAny]

    def get(self, request, platform: str):
        serializer = OAuthConnectURLQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        branch_id = data.get("branch_id") or get_branch_id_from_request(request)
        service = MessagingService()
        try:
            res = service.get_connect_url(platform=platform, branch_id=branch_id)
            return Response(res, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request, platform: str):
        serializer = OAuthCallbackRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        service = MessagingService()
        try:
            res = service.zernio_service.handle_oauth_callback(
                platform=platform,
                code=data.get("code", ""),
                state=data.get("state", ""),
                profile_id=data.get("profile_id", ""),
            )
            return Response(res, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class OAuthCallbackAPIView(APIView):
    """GET/POST /api/messaging/accounts/callback/ Endpoint for OAuth redirect callback with nonce."""

    permission_classes = [AllowAny]

    def get(self, request):
        service = MessagingService()
        try:
            params = {k: v for k, v in request.query_params.items()}
            branch_id = get_branch_id_from_request(request)
            res = service.handle_oauth_callback(params, fallback_branch_id=branch_id)
            return Response(res, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request):
        service = MessagingService()
        try:
            params = request.data if isinstance(request.data, dict) else {}
            branch_id = get_branch_id_from_request(request)
            res = service.handle_oauth_callback(params, fallback_branch_id=branch_id)
            return Response(res, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class ZernioWebhookAPIView(APIView):
    """POST /api/messaging/webhook/ Zernio incoming webhook endpoint."""

    permission_classes = [AllowAny]

    def post(self, request):
        payload = request.data
        print("\n" + "=" * 50)
        print("INCOMING WEBHOOK PAYLOAD:")
        try:
            print(json.dumps(payload, indent=2, default=str))
        except Exception:
            print(payload)
        print("=" * 50 + "\n")

        service = MessagingService()
        try:
            res = service.handle_incoming_webhook(payload)
            return Response(
                {"status": "received", "data": res}, status=status.HTTP_200_OK
            )
        except Exception as exc:
            print(f"Error handling webhook: {exc}")
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
