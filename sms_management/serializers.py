from rest_framework import serializers

from sms_management.models import SMSLog, SMSSettings


class SMSSettingsSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        model = SMSSettings
        fields = [
            "id",
            "branch",
            "branch_name",
            "is_enabled",
            "delay_minutes",
            "message_template",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "branch",
            "branch_name",
            "created_at",
            "updated_at",
        ]

    def validate_delay_minutes(self, value):
        if value is None or value < 0:
            raise serializers.ValidationError("delay_minutes must be 0 or greater.")
        return value

    def validate_message_template(self, value):
        text = (value or "").strip()
        if not text:
            raise serializers.ValidationError("message_template cannot be empty.")
        if len(text) > 720:
            raise serializers.ValidationError(
                "message_template exceeds NestSMS text limit of 720 characters."
            )
        return text

    def create(self, validated_data):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        branch = getattr(user, "branch", None) if user else None
        if not branch:
            raise serializers.ValidationError(
                {
                    "branch": (
                        "Your account has no branch assigned. "
                        "Assign a branch to the user to create SMS settings."
                    )
                }
            )
        if SMSSettings.objects.filter(branch=branch).exists():
            raise serializers.ValidationError(
                {
                    "branch": "SMS settings already exist for your branch."
                }
            )
        validated_data["branch"] = branch
        return super().create(validated_data)


class SMSLogSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(
        source="order.order_number", read_only=True, allow_null=True
    )
    branch_name = serializers.CharField(
        source="branch.name", read_only=True, allow_null=True
    )

    class Meta:
        model = SMSLog
        fields = [
            "id",
            "order",
            "order_number",
            "branch",
            "branch_name",
            "status",
            "phone_number",
            "message",
            "job_id",
            "scheduled_at",
            "sent_at",
            "cost",
            "error_message",
            "response_payload",
            "created_at",
            "updated_at",
            "created_by",
        ]
        read_only_fields = [
            "id",
            "job_id",
            "sent_at",
            "cost",
            "error_message",
            "response_payload",
            "created_at",
            "updated_at",
            "created_by",
            "order_number",
            "branch_name",
        ]
