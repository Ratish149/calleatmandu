from django.urls import include, path

from account.views import GoogleLoginView, LoginView, SignupView

urlpatterns = [
    path("signup/", SignupView.as_view(), name="signup"),
    path("login/", LoginView.as_view(), name="login"),
    path("social/google/", GoogleLoginView.as_view(), name="google_login"),
    path("headless/", include("allauth.headless.urls")),
]
