from rest_framework import status
from rest_framework.generics import (
    GenericAPIView,
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from account.filters import BranchFilter
from account.models import Branch
from account.serializers import (
    BranchSerializer,
    GoogleLoginSerializer,
    LoginSerializer,
    SignupSerializer,
    UserSerializer,
)
from account.services.auth_service import generate_tokens_for_user
from account.services.social_auth_service import google_social_login_service


class SignupView(GenericAPIView):
    """
    API view for user registration (signup).
    Requires full_name, email, password, and optional phone_number.
    """

    serializer_class = SignupSerializer
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {
                "message": "User registered successfully.",
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(GenericAPIView):
    """
    API view for user authentication (login).
    Requires email and password. Returns access/refresh JWT tokens and user profile details.
    """

    serializer_class = LoginSerializer
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        # Call service to generate tokens
        tokens = generate_tokens_for_user(user)

        return Response(
            {
                "message": "Login successful.",
                "tokens": tokens,
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class GoogleLoginView(GenericAPIView):
    """
    API view for Google social authentication using django-allauth headless.
    Accepts id_token or access_token, authenticates/registers user, and returns JWT tokens.
    """

    serializer_class = GoogleLoginSerializer
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = google_social_login_service(
            request=request,
            id_token=serializer.validated_data.get("id_token"),
            access_token=serializer.validated_data.get("access_token"),
            client_id=serializer.validated_data.get("client_id"),
        )

        return Response(
            {
                "message": "Google login successful.",
                "tokens": result["tokens"],
                "user": result["user"],
            },
            status=status.HTTP_200_OK,
        )


class BranchListCreateView(ListCreateAPIView):
    """
    API view to list all branches or create a new branch.
    """

    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    filterset_class = BranchFilter
    permission_classes = (AllowAny,)


class BranchRetrieveUpdateDestroyView(RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, update or delete a branch instance.
    """

    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    permission_classes = (AllowAny,)
