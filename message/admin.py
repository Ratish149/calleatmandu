from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from message.models import (
    Attachment,
    BusinessAccount,
    Conversation,
    Message,
    PendingOAuthConnection,
    Post,
)


@admin.register(BusinessAccount)
class BusinessAccountAdmin(ModelAdmin):
    list_display = (
        "platform",
        "account_name",
        "branch",
        "zernio_account_id",
        "created_at",
    )
    list_filter = ("platform", "branch")
    search_fields = ("account_name", "zernio_account_id")


@admin.register(PendingOAuthConnection)
class PendingOAuthConnectionAdmin(ModelAdmin):
    list_display = ("platform", "branch", "nonce", "created_at", "expires_at")
    list_filter = ("platform", "branch")
    search_fields = ("nonce",)


class MessageInline(TabularInline):
    model = Message
    extra = 0
    fields = ("direction", "content", "sent_by", "is_read", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Conversation)
class ConversationAdmin(ModelAdmin):
    list_display = (
        "zernio_conversation_id",
        "participant_name",
        "platform",
        "branch",
        "business_account",
        "updated_at",
    )
    list_filter = ("platform", "branch")
    search_fields = ("participant_name", "zernio_conversation_id")
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(ModelAdmin):
    list_display = (
        "id",
        "conversation",
        "direction",
        "sent_by",
        "is_read",
        "created_at",
    )
    list_filter = ("direction", "is_read")
    search_fields = ("content", "zernio_message_id")


@admin.register(Attachment)
class AttachmentAdmin(ModelAdmin):
    list_display = ("id", "message", "type", "url", "created_at")
    list_filter = ("type",)


@admin.register(Post)
class PostAdmin(ModelAdmin):
    list_display = ("title", "status", "branch", "created_by_user", "scheduled_for")
    list_filter = ("status", "branch")
    search_fields = ("title", "content")
