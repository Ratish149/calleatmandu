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
    LoginSerializer,
    SignupSerializer,
    UserSerializer,
)
from account.services.auth_service import generate_tokens_for_user


class SignupView(GenericAPIView):
    """
    API view for user registration (signup).
    Requires username, email, password, and role.
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
    Requires username and password. Returns access/refresh JWT tokens and user profile details.
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

