from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import (
    GenericAPIView,
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.response import Response

from accounting.filters import CashExpenditureFilter
from accounting.models import CashExpenditure
from accounting.selectors import get_cash_balance_summary
from accounting.serializers import (
    CashBalanceSummarySerializer,
    CashExpenditureSerializer,
)
from common.permissions import IsStaffOrOperationalRole
from common.utils import CustomPagination


class CashExpenditureListCreateAPIView(ListCreateAPIView):
    """
    API view to list cash & expenditure transactions or record a new entry:
    - GET: Returns paginated transactions with embedded balance summary
           (total_cash_amount, total_expenditure_amount, total_available_balance).
    - POST: Adds cash amount or records an expenditure.
    """

    permission_classes = [IsStaffOrOperationalRole]
    serializer_class = CashExpenditureSerializer
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = CashExpenditureFilter
    search_fields = ["title", "notes", "created_by__username"]
    ordering_fields = ["date", "cash_amount", "expenditure_amount", "created_at"]
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

        # Calculate balance summary for the filtered dataset
        summary_data = get_cash_balance_summary(
            queryset=filtered_qs,
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
    Dedicated API view to retrieve total cash, total expenditure, and available balance:
    - total_cash_amount: Total cash added/inflow.
    - total_expenditure_amount: Total expenditure/outflow.
    - total_available_balance: Available balance (cash - expenditure).
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
        summary = get_cash_balance_summary(
            queryset=filtered_qs,
            start_date=request.query_params.get("start_date"),
            end_date=request.query_params.get("end_date"),
        )
        serializer = self.get_serializer(summary)
        return Response(serializer.data, status=status.HTTP_200_OK)
