from rest_framework_simplejwt.tokens import RefreshToken

from account.models import User


def register_user(
    full_name: str,
    email: str,
    password: str,
    phone_number: str = "",
    role: str = "customer",
    branch=None,
    username: str = None,
) -> User:
    """
    Creates a new user instance with full_name parsed into first_name and last_name,
    hashes their password, and saves it.
    """
    names = full_name.strip().split(" ", 1)
    first_name = names[0]
    last_name = names[1] if len(names) > 1 else ""

    if not username:
        base_username = email.split("@")[0][:140]
        username = base_username
        counter = 1
        while User.objects.filter(username__iexact=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

    user = User(
        username=username,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone_number=phone_number,
        role=role,
        branch=branch,
    )
    user.set_password(password)
    user.save()

    # Create associated EmailAddress record for django-allauth compatibility
    try:
        from allauth.account.models import EmailAddress

        EmailAddress.objects.get_or_create(
            user=user,
            email=email,
            defaults={"verified": True, "primary": True},
        )
    except Exception:
        pass

    return user


def generate_tokens_for_user(user: User) -> dict:
    """
    Generates SimpleJWT access and refresh tokens for the given user.
    Includes custom claims for convenience.
    """
    refresh = RefreshToken.for_user(user)

    # Custom claims
    refresh["role"] = user.role
    refresh["email"] = user.email
    refresh["name"] = user.get_full_name()
    refresh["phone_number"] = user.phone_number
    refresh["user_id"] = user.id

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }
