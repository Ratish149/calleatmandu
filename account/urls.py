from django.urls import include, path

from account.views import (
    ChangePasswordView,
    CustomerListCreateAPIView,
    GoogleLoginView,
    LoginView,
    SignupView,
    UserListAPIView,
    UserMeAPIView,
    UserRetrieveUpdateDestroyAPIView,
)

urlpatterns = [
    path("signup/", SignupView.as_view(), name="signup"),
    path("login/", LoginView.as_view(), name="login"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("social/google/", GoogleLoginView.as_view(), name="google_login"),
    path("user/me/", UserMeAPIView.as_view(), name="user-me-alias"),
    path("users/", UserListAPIView.as_view(), name="user-list"),
    path(
        "users/<int:pk>/",
        UserRetrieveUpdateDestroyAPIView.as_view(),
        name="user-detail",
    ),
    path(
        "customers/", CustomerListCreateAPIView.as_view(), name="customer-list-create"
    ),
    path("headless/", include("allauth.headless.urls")),
]
