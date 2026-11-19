import django_filters

from sms_management.models import SMSLog, SMSSettings


class SMSSettingsFilter(django_filters.FilterSet):
    branch = django_filters.NumberFilter(field_name="branch_id")
    is_enabled = django_filters.BooleanFilter(field_name="is_enabled")

    class Meta:
        model = SMSSettings
        fields = ["is_enabled"]


class SMSLogFilter(django_filters.FilterSet):
    order_number = django_filters.CharFilter(
        field_name="order__order_number", lookup_expr="iexact"
    )
    phone_number = django_filters.CharFilter(
        field_name="phone_number", lookup_expr="icontains"
    )
    status = django_filters.CharFilter(field_name="status", lookup_expr="iexact")
    branch = django_filters.NumberFilter(field_name="branch_id")
    order = django_filters.NumberFilter(field_name="order_id")
    scheduled_at_after = django_filters.DateTimeFilter(
        field_name="scheduled_at", lookup_expr="gte"
    )
    scheduled_at_before = django_filters.DateTimeFilter(
        field_name="scheduled_at", lookup_expr="lte"
    )

    class Meta:
        model = SMSLog
        fields = ["status"]
