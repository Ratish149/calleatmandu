from django.urls import include, path

from account.views import (
    CustomerListCreateAPIView,
    GoogleLoginView,
    LoginView,
    SignupView,
    UserListAPIView,
    UserRetrieveUpdateDestroyAPIView,
)

urlpatterns = [
    path("signup/", SignupView.as_view(), name="signup"),
    path("login/", LoginView.as_view(), name="login"),
    path("social/google/", GoogleLoginView.as_view(), name="google_login"),
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
