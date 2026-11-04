from django.http import HttpResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import (
    GenericAPIView,
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsStaffOrOperationalRole
from common.utils import CustomPagination
from customer.filters import (
    CustomerFollowUpFilter,
    CustomerOrderActivityFilter,
)
from customer.models import CustomerFollowUp
from customer.selectors.customer_activity_selector import CustomerOrderActivitySelector
from customer.serializers import (
    CustomerFollowUpSerializer,
    CustomerOrderActivitySerializer,
    GroupedCustomerOrderActivitySerializer,
)
from customer.services.customer_export_service import CustomerExportService
from order.models import Order


class CustomerOrderActivityListAPIView(GenericAPIView):
    """
    API view to list customers derived directly from the Order table with active/inactive status:
    - Default activity window: 7 days.
    - Custom window: Customizable via `start_date` and `end_date` (or `days`).
    - Active: Customer who placed an order (or reordered) within the window.
    - Inactive: Customer who placed an order previously but has not ordered within the window.
    - Clean separation of registered customer accounts (User) and phone-based guest customers.
    - Supports query parameters:
      - `is_active` or `active`: boolean (true: active, false: inactive)
      - `status`: 'active' or 'inactive'
      - `customer_type`: 'registered', 'guest', or 'all'
      - `start_date`: e.g., '2026-10-01'
      - `end_date`: e.g., '2026-10-15'
      - `days`: default 7
      - `search`: search customer name, phone number, username, email
      - `is_reorder`: true/false
      - `branch`: filter by branch ID
      - `grouped`: boolean (if true, returns active and inactive lists grouped in one payload)
    """

    queryset = Order.objects.exclude(status=Order.OrderStatus.CANCELLED)
    serializer_class = CustomerOrderActivitySerializer
    permission_classes = [IsStaffOrOperationalRole]
    pagination_class = CustomPagination
    filterset_class = CustomerOrderActivityFilter

    def get_queryset(self):
        user = self.request.user
        queryset = Order.objects.exclude(status=Order.OrderStatus.CANCELLED)
        if (
            user
            and user.is_authenticated
            and not user.is_superuser
            and getattr(user, "role", None) != "admin"
            and getattr(user, "branch_id", None)
        ):
            return queryset.filter(branch_id=user.branch_id)
        return queryset

    def get(self, request, *args, **kwargs):
        params = request.query_params

        # 1. Parse window and filter parameters
        days_param = params.get("days", 7)
        try:
            days = int(days_param)
        except (ValueError, TypeError):
            days = 7

        start_date = params.get("start_date")
        end_date = params.get("end_date")
        status_filter = params.get("status")
        customer_type = params.get("customer_type")
        search = params.get("search")

        # Parse active / is_active boolean filter
        is_active_param = params.get("is_active")
        if is_active_param is None:
            is_active_param = params.get("active")
        is_active = None
        if is_active_param is not None:
            val = str(is_active_param).strip().lower()
            if val in ("true", "1", "yes", "active"):
                is_active = True
            elif val in ("false", "0", "no", "inactive"):
                is_active = False

        if is_active is None and status_filter:
            st = str(status_filter).strip().lower()
            if st in ("active", "true", "1", "yes"):
                is_active = True
            elif st in ("inactive", "false", "0", "no"):
                is_active = False

        branch_param = params.get("branch")
        branch_id = (
            int(branch_param) if branch_param and str(branch_param).isdigit() else None
        )

        is_reorder_param = params.get("is_reorder")
        is_reorder = None
        if is_reorder_param is not None:
            is_reorder = str(is_reorder_param).lower() in ("true", "1", "yes")

        grouped_param = params.get("grouped", "false").lower()
        is_grouped = grouped_param in ("true", "1", "yes")

        # 2. Query selector
        data = CustomerOrderActivitySelector.get_customer_order_activity(
            days=days,
            start_date=start_date,
            end_date=end_date,
            status=status_filter,
            is_active=is_active,
            customer_type=customer_type,
            search=search,
            is_reorder=is_reorder,
            branch_id=branch_id,
            user=request.user,
        )

        summary = data["summary"]
        customers = data["customers"]

        # 3. Handle Grouped response
        if is_grouped:
            active_list = [c for c in customers if c["is_active"]]
            inactive_list = [c for c in customers if not c["is_active"]]
            payload = {
                "summary": summary,
                "active_customers": active_list,
                "inactive_customers": inactive_list,
            }
            serializer = GroupedCustomerOrderActivitySerializer(payload)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # 4. Handle Standard Paginated response with embedded summary
        page = self.paginate_queryset(customers)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginated_response = self.get_paginated_response(serializer.data)
            paginated_response.data["summary"] = summary
            return paginated_response

        serializer = self.get_serializer(customers, many=True)
        return Response(
            {
                "summary": summary,
                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class CustomerFollowUpListCreateAPIView(ListCreateAPIView):
    """
    API view to list customer follow-up records or create a new follow-up.
    - Filterable by phone_number, branch, created_by, date range.
    - Optimized with select_related on 'user', 'created_by', and 'branch'.
    """

    permission_classes = [IsStaffOrOperationalRole]
    serializer_class = CustomerFollowUpSerializer
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = CustomerFollowUpFilter
    search_fields = ["phone_number", "customer_name", "notes"]
    ordering_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = CustomerFollowUp.objects.select_related(
            "user", "created_by", "branch"
        ).all()
        user = self.request.user
        if (
            user
            and user.is_authenticated
            and not user.is_superuser
            and getattr(user, "role", None) != "admin"
            and getattr(user, "branch_id", None)
        ):
            queryset = queryset.filter(branch_id=user.branch_id)

        phone_number = self.kwargs.get("phone_number")
        if phone_number:
            from customer.services.customer_followup_service import (
                CustomerFollowUpService,
            )

            clean_phone = CustomerFollowUpService.clean_phone_number(phone_number)
            queryset = queryset.filter(phone_number=clean_phone)

        return queryset

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(created_by=user)


class CustomerFollowUpRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, update, partial update, or delete a customer follow-up record.
    """

    permission_classes = [IsStaffOrOperationalRole]
    serializer_class = CustomerFollowUpSerializer
    queryset = CustomerFollowUp.objects.select_related(
        "user", "created_by", "branch"
    ).all()


class CustomerOrderActivityPhoneExportExcelAPIView(APIView):
    """
    API view to download an Excel sheet with only a 'phone' column containing
    customer phone numbers based on CustomerOrderActivityFilter parameters:
    - Default window: 7 days (or custom start_date, end_date, days).
    - Supports `is_active` or `active` query param (true: active, false: inactive).
    - Supports `status` query param ('active' or 'inactive').
    - Respects branch restrictions for branch managers / branch staff.
    - Preserves distinct and valid 10-digit phone numbers.
    """

    permission_classes = [IsStaffOrOperationalRole]

    def get(self, request, *args, **kwargs):
        params = request.query_params

        days_param = params.get("days", 7)
        try:
            days = int(days_param)
        except (ValueError, TypeError):
            days = 7

        start_date = params.get("start_date")
        end_date = params.get("end_date")
        status_filter = params.get("status")
        customer_type = params.get("customer_type")
        search = params.get("search")

        # Parse is_active / active boolean parameter
        is_active_param = params.get("is_active")
        if is_active_param is None:
            is_active_param = params.get("active")
        is_active = None
        if is_active_param is not None:
            val = str(is_active_param).strip().lower()
            if val in ("true", "1", "yes", "active"):
                is_active = True
            elif val in ("false", "0", "no", "inactive"):
                is_active = False

        if is_active is None and status_filter:
            st = str(status_filter).strip().lower()
            if st in ("active", "true", "1", "yes"):
                is_active = True
            elif st in ("inactive", "false", "0", "no"):
                is_active = False

        branch_param = params.get("branch")
        branch_id = (
            int(branch_param) if branch_param and str(branch_param).isdigit() else None
        )

        is_reorder_param = params.get("is_reorder")
        is_reorder = None
        if is_reorder_param is not None:
            is_reorder = str(is_reorder_param).lower() in ("true", "1", "yes")

        # Query customers from selector with flexible is_active / status filtering
        data = CustomerOrderActivitySelector.get_customer_order_activity(
            days=days,
            start_date=start_date,
            end_date=end_date,
            status=status_filter,
            is_active=is_active,
            customer_type=customer_type,
            search=search,
            is_reorder=is_reorder,
            branch_id=branch_id,
            user=request.user,
        )

        customers = data.get("customers", [])

        # Extract unique cleaned phone numbers from matched customers
        seen_phones = set()
        phone_numbers = []
        for c in customers:
            raw_phone = c.get("phone_number")
            cleaned = CustomerExportService.clean_phone_number(raw_phone)
            if cleaned and cleaned not in seen_phones:
                seen_phones.add(cleaned)
                phone_numbers.append(cleaned)

        # File naming according to active/inactive status
        status_label = "all"
        if is_active is True:
            status_label = "active"
        elif is_active is False:
            status_label = "inactive"

        excel_buffer = CustomerExportService.generate_phone_numbers_excel(
            phone_numbers,
            sheet_title=f"{status_label.title()} Customers",
        )
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{status_label}_customers_phones_{timestamp}.xlsx"

        response = HttpResponse(
            excel_buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
