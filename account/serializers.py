from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers

from account.models import Branch
from account.services.auth_service import register_user

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer representing the User profile details.
    """

    class Meta:
        model = User
        fields = ("id", "username", "email", "role", "branch")
        read_only_fields = ("id",)


class SignupSerializer(serializers.Serializer):
    """
    Serializer for handling user registration.
    """

    username = serializers.CharField(max_length=150, required=True)
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    password = serializers.CharField(write_only=True, required=True)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES, required=True)
    branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(), required=False, allow_null=True, default=None
    )

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError(
                "A user with this username already exists."
            )
        return value

    def validate_email(self, value):
        if value:
            if User.objects.filter(email__iexact=value).exists():
                raise serializers.ValidationError(
                    "A user with this email address already exists."
                )
        return value

    def create(self, validated_data):
        return register_user(
            username=validated_data["username"],
            password=validated_data["password"],
            email=validated_data["email"],
            role=validated_data["role"],
            branch=validated_data.get("branch"),
        )


class LoginSerializer(serializers.Serializer):
    """
    Serializer for validating user login credentials.
    """

    username = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        username = attrs.get("username")
        password = attrs.get("password")

        user = authenticate(username=username, password=password)

        if not user:
            raise serializers.ValidationError(
                "Unable to log in with provided credentials."
            )

        if not user.is_active:
            raise serializers.ValidationError("User account is deactivated.")

        attrs["user"] = user
        return attrs


class BranchSerializer(serializers.ModelSerializer):
    """
    Serializer representing the Branch details.
    """

    class Meta:
        model = Branch
        fields = (
            "id",
            "name",
            "slug",
            "address",
            "latitude",
            "longitude",
            "phone",
            "image",
            "opening_time",
            "closing_time",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "slug", "created_at", "updated_at")

