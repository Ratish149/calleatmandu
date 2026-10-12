from django.urls import path

from message.consumers import ConversationsConsumer, UnreadMessagesConsumer

websocket_urlpatterns = [
    path(
        "ws/messaging/unread/account/<str:business_account_id>/",
        UnreadMessagesConsumer.as_asgi(),
    ),
    path("ws/messaging/unread/", UnreadMessagesConsumer.as_asgi()),
    path(
        "ws/messaging/conversations/account/<str:business_account_id>/",
        ConversationsConsumer.as_asgi(),
    ),
    path("ws/messaging/conversations/", ConversationsConsumer.as_asgi()),
]
