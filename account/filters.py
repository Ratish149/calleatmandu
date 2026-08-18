import django_filters

from account.models import Branch


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
