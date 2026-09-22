from rest_framework import serializers

from message.models import Attachment, BusinessAccount, Conversation, Message


class BusinessAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessAccount
        fields = [
            "id",
            "organization_id",
            "zernio_account_id",
            "platform",
            "account_name",
            "created_at",
            "updated_at",
        ]


class AttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = ["id", "type", "url", "stored_url", "created_at"]


class MessageSerializer(serializers.ModelSerializer):
    attachments = AttachmentSerializer(many=True, read_only=True)
    sent_by_username = serializers.CharField(
        source="sent_by.username", read_only=True, default=None
    )

    class Meta:
        model = Message
        fields = [
            "id",
            "zernio_message_id",
            "conversation",
            "content",
            "direction",
            "external_sender_id",
            "sent_by",
            "sent_by_username",
            "is_read",
            "attachments",
            "created_at",
            "updated_at",
        ]


class ConversationSerializer(serializers.ModelSerializer):
    business_account = BusinessAccountSerializer(read_only=True)
    latest_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "id",
            "zernio_conversation_id",
            "zernio_account_id",
            "platform",
            "participant_name",
            "participant_avatar",
            "applicant_id",
            "contact_id",
            "business_account",
            "latest_message",
            "unread_count",
            "created_at",
            "updated_at",
        ]

    def get_latest_message(self, obj):
        latest = obj.messages.order_by("-created_at").first()
        if latest:
            return MessageSerializer(latest).data
        return None

    def get_unread_count(self, obj):
        return obj.messages.filter(direction="INBOUND", is_read=False).count()


class SendMessageSerializer(serializers.Serializer):
    message = serializers.CharField(
        required=True,
        allow_blank=False,
        help_text="Text content of the message to send",
    )


class LinkConversationSerializer(serializers.Serializer):
    applicant_id = serializers.CharField(
        required=True,
        help_text="ID of applicant to link to conversation",
    )


class OAuthConnectURLQuerySerializer(serializers.Serializer):
    organization_id = serializers.CharField(
        required=False,
        default="default",
        help_text="Organization ID initiating connection",
    )
    profile_id = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="Zernio profile ID",
    )
    redirect_url = serializers.URLField(
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="Custom redirect URL after OAuth connection",
    )
    headless = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Enable headless mode for custom UI",
    )
    login_method = serializers.CharField(
        required=False,
        default="instagram_login",
        help_text="Instagram login method (instagram_login or facebook_login)",
    )
    onboarding = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="WhatsApp onboarding screen type (api or business_app)",
    )
    signup = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="WhatsApp signup mode (hosted)",
    )
    brand_name = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=60,
        help_text="Brand name for hosted signup page",
    )
    primary_color = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="Hex color (#RRGGBB) for hosted signup page",
    )
    language = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        help_text="Language for hosted signup page",
    )


class OAuthCallbackRequestSerializer(serializers.Serializer):
    code = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="OAuth authorization code from callback",
    )
    state = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="OAuth state parameter",
    )
    profile_id = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Zernio profile ID",
    )
    nonce = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Security nonce emitted during getConnectUrl",
    )
