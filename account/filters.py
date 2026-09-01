import django_filters
from django.contrib.auth import get_user_model

from account.models import Branch

User = get_user_model()


class UserFilter(django_filters.FilterSet):
    """
    FilterSet for the User model to support filtering strictly by role.
    """

    role = django_filters.ChoiceFilter(choices=User.ROLE_CHOICES)

    class Meta:
        model = User
        fields = ("role",)


class BranchFilter(django_filters.FilterSet):
    """
    FilterSet for the Branch model to support filtering by name and address.
    """

    name = django_filters.CharFilter(lookup_expr="icontains")
    address = django_filters.CharFilter(lookup_expr="icontains")
    latitude = django_filters.NumberFilter()
    longitude = django_filters.NumberFilter()

    class Meta:
        model = Branch
        fields = ("name", "address", "latitude", "longitude")
