from django.conf import settings
from django.db import models

from common.models import BaseModel


class BusinessAccount(BaseModel):
    branch = models.ForeignKey(
        "user_account.Branch",
        on_delete=models.CASCADE,
        related_name="business_accounts",
        null=True,
        blank=True,
    )
    zernio_account_id = models.CharField(max_length=255, unique=True, db_index=True)
    platform = models.CharField(max_length=50, db_index=True)
    account_name = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "business_accounts"
        indexes = [
            models.Index(fields=["branch", "platform"]),
        ]

    def __str__(self):
        branch_str = f"Branch {self.branch_id}" if self.branch_id else "Global"
        return f"{self.platform} ({self.account_name or self.zernio_account_id}) - {branch_str}"


class PendingOAuthConnection(models.Model):
    branch = models.ForeignKey(
        "user_account.Branch",
        on_delete=models.CASCADE,
        related_name="pending_oauth_connections",
        null=True,
        blank=True,
    )
    platform = models.CharField(max_length=50)
    nonce = models.CharField(max_length=255, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        db_table = "pending_oauth_connections"

    def __str__(self):
        return f"PendingOAuthConnection {self.platform} - Branch {self.branch_id}"


class Conversation(BaseModel):
    branch = models.ForeignKey(
        "user_account.Branch",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="conversations",
    )
    zernio_conversation_id = models.CharField(
        max_length=255, unique=True, db_index=True
    )
    zernio_account_id = models.CharField(max_length=255, db_index=True)
    platform = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    participant_name = models.CharField(max_length=255, blank=True, null=True)
    participant_avatar = models.TextField(blank=True, null=True)

    applicant_id = models.CharField(
        max_length=255, blank=True, null=True, db_index=True
    )
    contact_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)

    business_account = models.ForeignKey(
        BusinessAccount,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="conversations",
    )

    class Meta:
        db_table = "conversations"
        indexes = [
            models.Index(fields=["branch", "updated_at"]),
            models.Index(fields=["business_account", "updated_at"]),
        ]

    def __str__(self):
        return f"Conversation {self.zernio_conversation_id} ({self.participant_name or 'Unknown'})"


class Message(BaseModel):
    DIRECTION_CHOICES = (
        ("INBOUND", "Inbound"),
        ("OUTBOUND", "Outbound"),
    )

    zernio_message_id = models.CharField(
        max_length=255, unique=True, blank=True, null=True, db_index=True
    )
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )

    content = models.TextField(blank=True, null=True)
    direction = models.CharField(
        max_length=10, choices=DIRECTION_CHOICES, db_index=True
    )

    external_sender_id = models.CharField(max_length=255, blank=True, null=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="messages_sent",
    )

    is_read = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = "messages"
        indexes = [
            models.Index(fields=["conversation", "direction", "is_read"]),
            models.Index(fields=["conversation", "created_at"]),
        ]

    def __str__(self):
        return f"Message {self.id} [{self.direction}] - Conv: {self.conversation_id}"


class Attachment(models.Model):
    ATTACHMENT_TYPE_CHOICES = (
        ("IMAGE", "Image"),
        ("VIDEO", "Video"),
        ("AUDIO", "Audio"),
        ("FILE", "File"),
    )

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    type = models.CharField(
        max_length=10, choices=ATTACHMENT_TYPE_CHOICES, default="FILE"
    )
    url = models.TextField()
    stored_url = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "message_attachments"

    def __str__(self):
        return f"Attachment {self.id} ({self.type})"


class Post(BaseModel):
    zernio_post_id = models.CharField(
        max_length=255, unique=True, blank=True, null=True, db_index=True
    )
    title = models.CharField(max_length=255, blank=True, null=True)
    content = models.TextField(blank=True, null=True)
    tags = models.JSONField(default=list, blank=True)
    hashtags = models.JSONField(default=list, blank=True)
    mentions = models.JSONField(default=list, blank=True)
    media_urls = models.JSONField(default=list, blank=True)
    platforms = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=50, default="draft", db_index=True)
    scheduled_for = models.DateTimeField(blank=True, null=True)
    timezone = models.CharField(max_length=50, blank=True, null=True)
    platform_post_urls = models.JSONField(default=list, blank=True)

    created_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="posts",
    )
    branch = models.ForeignKey(
        "user_account.Branch",
        on_delete=models.CASCADE,
        related_name="posts",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "posts"
        indexes = [
            models.Index(fields=["branch", "status"]),
        ]

    def __str__(self):
        return f"Post {self.id} ({self.status}) - Branch {self.branch_id}"
