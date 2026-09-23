import django_filters
from django.contrib.auth import get_user_model
from django.db.models import Q

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


class CustomerActivityFilter(django_filters.FilterSet):
    """
    FilterSet for customer activity:
    - status: 'active' (ordered recently within threshold) or 'inactive' (no recent orders).
    - branch: filter by customer branch ID.
    - search: search by name, phone_number, email, username.
    """

    status = django_filters.ChoiceFilter(
        choices=(
            ("active", "Active (ordered recently)"),
            ("inactive", "Inactive (no recent orders)"),
        ),
        method="filter_status",
    )
    branch = django_filters.NumberFilter(field_name="branch_id")
    search = django_filters.CharFilter(method="filter_search")

    class Meta:
        model = User
        fields = ("status", "branch", "search")

    def filter_status(self, queryset, name, value):
        if not value:
            return queryset
        val = str(value).strip().lower()
        if val == "active":
            return queryset.filter(is_active_customer=True)
        elif val == "inactive":
            return queryset.filter(is_active_customer=False)
        return queryset

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        val = str(value).strip()
        return queryset.filter(
            Q(first_name__icontains=val)
            | Q(last_name__icontains=val)
            | Q(phone_number__icontains=val)
            | Q(email__icontains=val)
            | Q(username__icontains=val)
        )
