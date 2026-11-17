from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from message.models import (
    Attachment,
    BranchAISettings,
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
    fields = ("direction", "content", "sent_by", "is_ai_generated", "is_read", "created_at")
    readonly_fields = ("created_at",)


@admin.register(BranchAISettings)
class BranchAISettingsAdmin(ModelAdmin):
    list_display = (
        "branch",
        "ai_chat_enabled",
        "ai_reply_delay_seconds",
        "ai_order_creation_enabled",
        "ai_order_cancellation_enabled",
        "ai_order_cancellation_window_minutes",
        "ai_order_dedup_window_minutes",
        "updated_at",
    )
    list_filter = (
        "ai_chat_enabled",
        "ai_order_creation_enabled",
        "ai_order_cancellation_enabled",
    )


@admin.register(Conversation)
class ConversationAdmin(ModelAdmin):
    list_display = (
        "zernio_conversation_id",
        "participant_name",
        "platform",
        "branch",
        "business_account",
        "ai_replies_active",
        "ai_reply_pending",
        "ai_reply_due_at",
        "updated_at",
    )
    list_filter = ("platform", "branch", "ai_replies_active", "ai_reply_pending")
    search_fields = ("participant_name", "zernio_conversation_id")
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(ModelAdmin):
    list_display = (
        "id",
        "conversation",
        "direction",
        "sent_by",
        "is_ai_generated",
        "is_read",
        "created_at",
    )
    list_filter = ("direction", "is_read", "is_ai_generated")
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
