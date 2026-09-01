from django.contrib.auth import get_user_model
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.filters import SearchFilter
from rest_framework.generics import (
    GenericAPIView,
    ListAPIView,
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from account.filters import BranchFilter, UserFilter
from account.models import Branch
from account.serializers import (
    BranchSerializer,
    CustomerCreateSerializer,
    GoogleLoginSerializer,
    LoginSerializer,
    SignupSerializer,
    UserSerializer,
)
from account.services.auth_service import generate_tokens_for_user
from account.services.social_auth_service import google_social_login_service
from common.permissions import IsStaffOrOperationalRole
from common.utils import CustomPagination

User = get_user_model()


class UserListAPIView(ListAPIView):
    """
    API view to list users with filtering by role and search.
    """

    queryset = User.objects.select_related("branch").order_by("-date_joined")
    serializer_class = UserSerializer
    permission_classes = [IsStaffOrOperationalRole]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = UserFilter
    search_fields = ["first_name", "last_name", "username", "email", "phone_number"]
    pagination_class = CustomPagination


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


class CustomerListCreateAPIView(ListCreateAPIView):
    """
    API view to list all customers or create a new customer using full_name & phone_number.
    """

    queryset = (
        User.objects
        .filter(role="customer")
        .select_related("branch")
        .order_by("-date_joined")
    )
    filter_backends = [DjangoFilterBackend, SearchFilter]
    pagination_class = CustomPagination
    search_fields = ["phone_number", "first_name", "last_name", "username"]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CustomerCreateSerializer
        return UserSerializer

    def create(self, request, *args, **kwargs):
        serializer = CustomerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer = serializer.save()
        response_serializer = UserSerializer(customer)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


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
