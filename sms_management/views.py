from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)

from common.permissions import IsAdminRole, IsStaffOrOperationalRole
from common.utils import CustomPagination
from sms_management.filters import SMSLogFilter, SMSSettingsFilter
from sms_management.models import SMSLog, SMSSettings
from sms_management.serializers import SMSLogSerializer, SMSSettingsSerializer


def _sms_settings_for_user(user):
    """SMS settings scoped to the authenticated user's branch only."""
    qs = SMSSettings.objects.select_related("branch").all()
    branch_id = getattr(user, "branch_id", None)
    if not branch_id:
        return qs.none()
    return qs.filter(branch_id=branch_id)


class SMSSettingsListCreateAPIView(ListCreateAPIView):
    """
    List / create SMS settings for the authenticated user's branch only.
    On create, branch is taken from the user token (user.branch).
    """

    serializer_class = SMSSettingsSerializer
    permission_classes = [IsAdminRole]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = SMSSettingsFilter
    search_fields = ["branch__name", "message_template"]
    ordering_fields = ["created_at", "updated_at", "delay_minutes", "is_enabled"]
    ordering = ["branch__name"]

    def get_queryset(self):
        return _sms_settings_for_user(self.request.user)


class SMSSettingsRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    """Retrieve / update / delete SMS settings for the user's branch only."""

    serializer_class = SMSSettingsSerializer
    permission_classes = [IsAdminRole]
    lookup_field = "pk"

    def get_queryset(self):
        return _sms_settings_for_user(self.request.user)


def _sms_logs_for_user(user):
    """SMS logs scoped to the authenticated user's branch only."""
    qs = SMSLog.objects.select_related("order", "branch", "created_by").all()
    branch_id = getattr(user, "branch_id", None)
    if not branch_id:
        return qs.none()
    return qs.filter(branch_id=branch_id)


class SMSLogListCreateAPIView(ListCreateAPIView):
    """
    List / create SMS logs for the authenticated user's branch only.
    - GET: paginated list (staff)
    - POST: create a log record (staff); does not auto-send via NestSMS
    """

    serializer_class = SMSLogSerializer
    permission_classes = [IsStaffOrOperationalRole]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = SMSLogFilter
    search_fields = [
        "phone_number",
        "message",
        "job_id",
        "order__order_number",
        "branch__name",
    ]
    ordering_fields = ["created_at", "scheduled_at", "sent_at", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return _sms_logs_for_user(self.request.user)

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        branch = getattr(user, "branch", None) if user else None
        serializer.save(created_by=user, branch=branch)


class SMSLogRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    """Retrieve / update / delete a single SMS log for the user's branch only."""

    serializer_class = SMSLogSerializer
    permission_classes = [IsStaffOrOperationalRole]
    lookup_field = "pk"

    def get_queryset(self):
        return _sms_logs_for_user(self.request.user)
