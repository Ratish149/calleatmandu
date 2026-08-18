from rest_framework_simplejwt.tokens import RefreshToken

from account.models import User


def register_user(username, password, email, role, branch=None) -> User:
    """
    Creates a new user instance, hashes their password, and saves it.
    """
    user = User(
        username=username,
        email=email,
        role=role,
        branch=branch,
    )
    user.set_password(password)
    user.save()
    return user


def generate_tokens_for_user(user: User) -> dict:
    """
    Generates SimpleJWT access and refresh tokens for the given user.
    Includes custom claims for convenience.
    """
    refresh = RefreshToken.for_user(user)

    # Custom claims
    refresh["role"] = user.role
    refresh["username"] = user.username
    refresh["user_id"] = user.id

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }
