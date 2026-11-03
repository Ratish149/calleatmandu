from django.urls import path

from accounting.views import (
    CashBalanceSummaryAPIView,
    CashExpenditureListCreateAPIView,
    CashExpenditureRetrieveUpdateDestroyAPIView,
)

urlpatterns = [
    path(
        "accounting/cash-flow/",
        CashExpenditureListCreateAPIView.as_view(),
        name="cash-expenditure-list-create",
    ),
    path(
        "accounting/cash-flow/<int:pk>/",
        CashExpenditureRetrieveUpdateDestroyAPIView.as_view(),
        name="cash-expenditure-detail",
    ),
    path(
        "accounting/balance/",
        CashBalanceSummaryAPIView.as_view(),
        name="accounting-balance-summary",
    ),
]
