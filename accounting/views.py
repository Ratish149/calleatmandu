from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import (
    GenericAPIView,
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.response import Response

from accounting.filters import (
    CashExpenditureFilter,
    CreditEntryFilter,
    VendorFilter,
    VendorSummaryFilter,
    VendorTransactionFilter,
)
from accounting.models import CashExpenditure, CreditEntry, Vendor, VendorTransaction
from accounting.selectors import (
    get_cash_balance_summary,
    get_credit_stats,
    get_vendor_summary_report,
    get_vendor_transaction_summary,
)
from accounting.serializers import (
    CashBalanceSummarySerializer,
    CashExpenditureSerializer,
    CreditEntrySerializer,
    CreditSettleActionSerializer,
    CreditStatsSerializer,
    VendorSerializer,
    VendorSummaryResponseSerializer,
    VendorTransactionSerializer,
    VendorTransactionSummarySerializer,
)
from accounting.services.accounting_service import CreditEntryService
from common.permissions import IsStaffOrOperationalRole
from common.utils import CustomPagination


class CashExpenditureListCreateAPIView(ListCreateAPIView):
    """
    API view to list cash & expenditure transactions or record a new entry:
    - GET: Returns paginated transactions with embedded balance summary
           (total_cash_amount, total_online_amount, total_delivery_charge, total_available_balance).
    - POST: Adds a new record with cash_amount, online_amount, and delivery_charge.
    """

    permission_classes = [IsStaffOrOperationalRole]
    serializer_class = CashExpenditureSerializer
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = CashExpenditureFilter
    search_fields = ["notes", "created_by__username"]
    ordering_fields = [
        "date",
        "cash_amount",
        "online_amount",
        "delivery_charge",
        "created_at",
    ]
    ordering = ["-date", "-created_at"]

    def get_queryset(self):
        queryset = CashExpenditure.objects.select_related("branch", "created_by").all()
        user = self.request.user
        if (
            user
            and user.is_authenticated
            and not user.is_superuser
            and getattr(user, "role", None) != "admin"
            and getattr(user, "branch_id", None)
        ):
            queryset = queryset.filter(branch_id=user.branch_id)
        return queryset

    def list(self, request, *args, **kwargs):
        filtered_qs = self.filter_queryset(self.get_queryset())

        user = request.user
        branch_id = None
        if (
            user
            and user.is_authenticated
            and not user.is_superuser
            and getattr(user, "role", None) != "admin"
            and getattr(user, "branch_id", None)
        ):
            branch_id = user.branch_id
        elif request.query_params.get("branch"):
            try:
                branch_id = int(request.query_params.get("branch"))
            except (ValueError, TypeError):
                branch_id = None

        # Calculate balance summary for the filtered dataset
        summary_data = get_cash_balance_summary(
            queryset=filtered_qs,
            branch_id=branch_id,
            start_date=request.query_params.get("start_date"),
            end_date=request.query_params.get("end_date"),
        )

        page = self.paginate_queryset(filtered_qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginated_response = self.get_paginated_response(serializer.data)
            paginated_response.data["summary"] = summary_data
            return paginated_response

        serializer = self.get_serializer(filtered_qs, many=True)
        return Response(
            {
                "summary": summary_data,
                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class CashExpenditureRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, update, partial update, or delete a cash/expenditure record.
    """

    permission_classes = [IsStaffOrOperationalRole]
    serializer_class = CashExpenditureSerializer

    def get_queryset(self):
        queryset = CashExpenditure.objects.select_related("branch", "created_by").all()
        user = self.request.user
        if (
            user
            and user.is_authenticated
            and not user.is_superuser
            and getattr(user, "role", None) != "admin"
            and getattr(user, "branch_id", None)
        ):
            queryset = queryset.filter(branch_id=user.branch_id)
        return queryset


class CashBalanceSummaryAPIView(GenericAPIView):
    """
    Dedicated API view to retrieve comprehensive cash flow balance summary:
    - total_cash_amount: Sum of all physical cash amounts.
    - total_online_amount: Sum of all digital/online payment amounts.
    - total_delivery_charge: Sum of all delivery charge expenses.
    - total_vendor_paid_amount: Sum of all payments made to vendors (vendor payment amount).
    - vendor_payment_amount: Alias for total_vendor_paid_amount.
    - total_available_balance: Net available balance:
      (total_cash_amount + total_online_amount - total_delivery_charge - total_vendor_paid_amount).
    - available_balance: Alias for total_available_balance.
    Filters:
    - start_date (YYYY-MM-DD)
    - end_date (YYYY-MM-DD)
    - branch (Branch ID)
    """

    permission_classes = [IsStaffOrOperationalRole]
    serializer_class = CashBalanceSummarySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = CashExpenditureFilter

    def get_queryset(self):
        queryset = CashExpenditure.objects.all()
        user = self.request.user
        if (
            user
            and user.is_authenticated
            and not user.is_superuser
            and getattr(user, "role", None) != "admin"
            and getattr(user, "branch_id", None)
        ):
            queryset = queryset.filter(branch_id=user.branch_id)
        return queryset

    def get(self, request, *args, **kwargs):
        filtered_qs = self.filter_queryset(self.get_queryset())
        user = request.user
        branch_id = None
        if (
            user
            and user.is_authenticated
            and not user.is_superuser
            and getattr(user, "role", None) != "admin"
            and getattr(user, "branch_id", None)
        ):
            branch_id = user.branch_id
        elif request.query_params.get("branch"):
            try:
                branch_id = int(request.query_params.get("branch"))
            except (ValueError, TypeError):
                branch_id = None

        summary = get_cash_balance_summary(
            queryset=filtered_qs,
            branch_id=branch_id,
            start_date=request.query_params.get("start_date"),
            end_date=request.query_params.get("end_date"),
        )
        serializer = self.get_serializer(summary)
        return Response(serializer.data, status=status.HTTP_200_OK)


class VendorListCreateAPIView(ListCreateAPIView):
    """
    API view to list vendors or create a new vendor:
    - GET: Returns paginated vendor list. Supports search (name, phone) and branch filter.
    - POST: Creates a new vendor. Branch is auto-assigned from the logged-in user.
    Filters: branch, search
    """

    permission_classes = [IsStaffOrOperationalRole]
    serializer_class = VendorSerializer
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = VendorFilter
    search_fields = ["name", "phone_number", "address"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        user = self.request.user
        queryset = Vendor.objects.select_related("branch").all()
        if (
            user
            and user.is_authenticated
            and not user.is_superuser
            and getattr(user, "role", None) != "admin"
            and getattr(user, "branch_id", None)
        ):
            queryset = queryset.filter(branch_id=user.branch_id)
        return queryset


class VendorRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, update, partial update, or delete a vendor.
    """

    permission_classes = [IsStaffOrOperationalRole]
    serializer_class = VendorSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Vendor.objects.select_related("branch").all()
        if (
            user
            and user.is_authenticated
            and not user.is_superuser
            and getattr(user, "role", None) != "admin"
            and getattr(user, "branch_id", None)
        ):
            queryset = queryset.filter(branch_id=user.branch_id)
        return queryset


class VendorTransactionListCreateAPIView(ListCreateAPIView):
    """
    API view to list vendor transactions or create a new one:
    - GET: Returns paginated transactions with embedded financial summary
           (total_billed, total_paid, remaining_due).
    - POST: Creates a new transaction (BILL or PAYMENT) for a vendor.
    Filters: vendor, transaction_type, payment_method, start_date, end_date, branch, search
    """

    permission_classes = [IsStaffOrOperationalRole]
    serializer_class = VendorTransactionSerializer
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = VendorTransactionFilter
    search_fields = ["notes", "vendor__name"]
    ordering_fields = ["date", "amount", "created_at"]
    ordering = ["-date", "-created_at"]

    def get_queryset(self):
        user = self.request.user
        queryset = VendorTransaction.objects.select_related(
            "vendor", "branch", "created_by"
        ).all()
        if (
            user
            and user.is_authenticated
            and not user.is_superuser
            and getattr(user, "role", None) != "admin"
            and getattr(user, "branch_id", None)
        ):
            queryset = queryset.filter(branch_id=user.branch_id)
        return queryset

    def list(self, request, *args, **kwargs):
        filtered_qs = self.filter_queryset(self.get_queryset())

        # Compute financial summary on the filtered dataset
        summary = get_vendor_transaction_summary(queryset=filtered_qs)

        page = self.paginate_queryset(filtered_qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            paginated_response = self.get_paginated_response(serializer.data)
            paginated_response.data["summary"] = summary
            return paginated_response

        serializer = self.get_serializer(filtered_qs, many=True)
        return Response(
            {"summary": summary, "results": serializer.data},
            status=status.HTTP_200_OK,
        )


class VendorTransactionRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, update, partial update, or delete a vendor transaction.
    """

    permission_classes = [IsStaffOrOperationalRole]
    serializer_class = VendorTransactionSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = VendorTransaction.objects.select_related(
            "vendor", "branch", "created_by"
        ).all()
        if (
            user
            and user.is_authenticated
            and not user.is_superuser
            and getattr(user, "role", None) != "admin"
            and getattr(user, "branch_id", None)
        ):
            queryset = queryset.filter(branch_id=user.branch_id)
        return queryset


class VendorTransactionSummaryAPIView(GenericAPIView):
    """
    Dedicated API view to retrieve vendor transactions financial summary:
    - total_billed: Total bills/invoices billed by vendors.
    - total_paid: Total payments made to vendors.
    - remaining_due: Net outstanding balance owed (total_billed - total_paid).
    - total_entries: Total transaction count.
    - bill_count: Count of BILL transactions.
    - payment_count: Count of PAYMENT transactions.

    Filters:
    - vendor (Vendor ID)
    - transaction_type (BILL, PAYMENT)
    - payment_method
    - start_date (YYYY-MM-DD)
    - end_date (YYYY-MM-DD)
    - branch (Branch ID)
    - search (title, notes)
    """

    permission_classes = [IsStaffOrOperationalRole]
    serializer_class = VendorTransactionSummarySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = VendorTransactionFilter

    def get_queryset(self):
        user = self.request.user
        queryset = VendorTransaction.objects.all()
        if (
            user
            and user.is_authenticated
            and not user.is_superuser
            and getattr(user, "role", None) != "admin"
            and getattr(user, "branch_id", None)
        ):
            queryset = queryset.filter(branch_id=user.branch_id)
        return queryset

    def get(self, request, *args, **kwargs):
        filtered_qs = self.filter_queryset(self.get_queryset())
        summary = get_vendor_transaction_summary(
            queryset=filtered_qs,
            start_date=request.query_params.get("start_date"),
            end_date=request.query_params.get("end_date"),
        )
        serializer = self.get_serializer(summary)
        return Response(serializer.data, status=status.HTTP_200_OK)


class VendorSummaryAPIView(GenericAPIView):
    """
    Dedicated API view to retrieve vendor financial summary:
    - Without vendor filter: returns aggregated totals and individual breakdown across all vendors.
    - With vendor filter (?vendor=ID): returns summary and details for that specific vendor only.

    Filters:
    - vendor: Vendor ID (e.g. ?vendor=3)
    - branch: Branch ID
    - start_date: YYYY-MM-DD
    - end_date: YYYY-MM-DD
    - search: Vendor name or phone number
    """

    permission_classes = [IsStaffOrOperationalRole]
    serializer_class = VendorSummaryResponseSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = VendorSummaryFilter
    queryset = Vendor.objects.all()

    def get(self, request, *args, **kwargs):
        params = request.query_params

        vendor_param = params.get("vendor")
        vendor_id = (
            int(vendor_param) if vendor_param and str(vendor_param).isdigit() else None
        )

        branch_param = params.get("branch")
        branch_id = (
            int(branch_param) if branch_param and str(branch_param).isdigit() else None
        )

        start_date = params.get("start_date")
        end_date = params.get("end_date")
        search = params.get("search")

        data = get_vendor_summary_report(
            vendor_id=vendor_id,
            branch_id=branch_id,
            start_date=start_date,
            end_date=end_date,
            search=search,
            user=request.user,
        )

        serializer = self.get_serializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CreditEntryListAPIView(ListCreateAPIView):
    """
    API view to list all credit entries or create a standalone credit entry:
    - GET: Returns paginated credit entries with status, amounts, and settlement info.
           Supports filtering by status, branch, date range, and search.
    - POST: Manually create a credit entry linked to an existing cash entry.
            (In normal flow, credit entries are auto-created from CashExpenditure
            when credit_amount > 0.)

    Filters: status, branch, start_date, end_date, search
    """

    permission_classes = [IsStaffOrOperationalRole]
    serializer_class = CreditEntrySerializer
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = CreditEntryFilter
    search_fields = ["notes"]
    ordering_fields = ["cash_entry__date", "credit_amount", "status", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        queryset = CreditEntry.objects.select_related(
            "cash_entry", "branch", "created_by", "settlement"
        ).all()
        if (
            user
            and user.is_authenticated
            and not user.is_superuser
            and getattr(user, "role", None) != "admin"
            and getattr(user, "branch_id", None)
        ):
            queryset = queryset.filter(branch_id=user.branch_id)
        return queryset


class CreditEntryRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, update, or delete a credit entry.
    Only PENDING credit entries (without a settlement) can be edited or deleted.
    """

    permission_classes = [IsStaffOrOperationalRole]
    serializer_class = CreditEntrySerializer

    def get_queryset(self):
        user = self.request.user
        queryset = CreditEntry.objects.select_related(
            "cash_entry", "branch", "created_by", "settlement"
        ).all()
        if (
            user
            and user.is_authenticated
            and not user.is_superuser
            and getattr(user, "role", None) != "admin"
            and getattr(user, "branch_id", None)
        ):
            queryset = queryset.filter(branch_id=user.branch_id)
        return queryset


class CreditSettleAPIView(GenericAPIView):
    """
    POST endpoint to settle a credit entry.

    Body:
      - cash_settled (float): Amount settled via cash (default 0).
      - online_settled (float): Amount settled via online (default 0).
      - settled_date (date, optional): Date of settlement (defaults to today).
      - notes (str, optional): Remarks.

    Rules:
      - At least one of cash_settled or online_settled must be > 0.
      - Total (cash + online) cannot exceed the original credit_amount.
      - A credit entry can only be settled once.

    Returns the updated CreditEntry with the embedded settlement.
    """

    permission_classes = [IsStaffOrOperationalRole]
    serializer_class = CreditSettleActionSerializer

    def get_object(self):
        user = self.request.user
        queryset = CreditEntry.objects.select_related("settlement").all()
        if (
            user
            and user.is_authenticated
            and not user.is_superuser
            and getattr(user, "role", None) != "admin"
            and getattr(user, "branch_id", None)
        ):
            queryset = queryset.filter(branch_id=user.branch_id)
        return queryset.get(pk=self.kwargs["pk"])

    def post(self, request, *args, **kwargs):
        credit_entry = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user if request.user.is_authenticated else None
        CreditEntryService.settle_credit(
            credit_entry=credit_entry,
            data=serializer.validated_data,
            created_by=user,
        )

        # Return the refreshed CreditEntry with settlement nested
        credit_entry.refresh_from_db()
        response_serializer = CreditEntrySerializer(
            credit_entry, context={"request": request}
        )
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class CreditStatsAPIView(GenericAPIView):
    """
    GET endpoint returning a credit statistics summary for the filtered period.

    Response fields:
      - total_credit_amount    : Total credit given in period.
      - total_credit_settled   : Amount already collected from credits.
      - total_credit_remaining : Still outstanding (total - settled).
      - settled_count          : Number of SETTLED credit entries.
      - pending_count          : Number of PENDING credit entries.
      - total_entries          : All credit entries in period.

    Query params:
      - branch      (int)
      - start_date  (YYYY-MM-DD)
      - end_date    (YYYY-MM-DD)
    """

    permission_classes = [IsStaffOrOperationalRole]
    serializer_class = CreditStatsSerializer

    def get(self, request, *args, **kwargs):
        user = request.user
        params = request.query_params

        branch_id = None
        if (
            user
            and user.is_authenticated
            and not user.is_superuser
            and getattr(user, "role", None) != "admin"
            and getattr(user, "branch_id", None)
        ):
            branch_id = user.branch_id
        elif params.get("branch"):
            try:
                branch_id = int(params.get("branch"))
            except (ValueError, TypeError):
                branch_id = None

        stats = get_credit_stats(
            branch_id=branch_id,
            start_date=params.get("start_date"),
            end_date=params.get("end_date"),
        )
        serializer = self.get_serializer(stats)
        return Response(serializer.data, status=status.HTTP_200_OK)
