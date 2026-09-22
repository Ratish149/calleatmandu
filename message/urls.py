from django.urls import path

from message.views import (
    BusinessAccountListAPIView,
    BusinessAccountUnlinkAPIView,
    ConversationDetailAPIView,
    ConversationLinkAPIView,
    ConversationListAPIView,
    ConversationMarkReadAPIView,
    ConversationMessagesAPIView,
    ConversationUnlinkAPIView,
    OAuthCallbackAPIView,
    UnreadCountsAPIView,
    ZernioConnectAPIView,
    ZernioWebhookAPIView,
)

urlpatterns = [
    # Conversations
    path(
        "conversations/",
        ConversationListAPIView.as_view(),
        name="conversation-list",
    ),
    path(
        "conversations/<str:pk>/",
        ConversationDetailAPIView.as_view(),
        name="conversation-detail",
    ),
    path(
        "conversations/<str:conversation_id>/messages/",
        ConversationMessagesAPIView.as_view(),
        name="conversation-messages",
    ),
    path(
        "conversations/<str:conversation_id>/read/",
        ConversationMarkReadAPIView.as_view(),
        name="conversation-mark-read",
    ),
    path(
        "conversations/<str:conversation_id>/link/",
        ConversationLinkAPIView.as_view(),
        name="conversation-link",
    ),
    path(
        "conversations/<str:conversation_id>/unlink/",
        ConversationUnlinkAPIView.as_view(),
        name="conversation-unlink",
    ),
    # Accounts & Unread counts
    path(
        "unread-counts/",
        UnreadCountsAPIView.as_view(),
        name="unread-counts",
    ),
    path(
        "accounts/",
        BusinessAccountListAPIView.as_view(),
        name="account-list",
    ),
    path(
        "accounts/<str:platform>/unlink/",
        BusinessAccountUnlinkAPIView.as_view(),
        name="account-unlink",
    ),
    path(
        "accounts/callback/",
        OAuthCallbackAPIView.as_view(),
        name="account-callback",
    ),
    path(
        "webhook/",
        ZernioWebhookAPIView.as_view(),
        name="webhook",
    ),
    # Zernio OAuth Connect
    path(
        "connect/<str:platform>/",
        ZernioConnectAPIView.as_view(),
        name="zernio-connect",
    ),
]
