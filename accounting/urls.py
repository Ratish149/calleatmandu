from django.urls import path

from accounting.views import (
    CashBalanceSummaryAPIView,
    CashExpenditureListCreateAPIView,
    CashExpenditureRetrieveUpdateDestroyAPIView,
    CreditEntryListAPIView,
    CreditEntryRetrieveUpdateDestroyAPIView,
    CreditSettleAPIView,
    CreditStatsAPIView,
    VendorListCreateAPIView,
    VendorRetrieveUpdateDestroyAPIView,
    VendorSummaryAPIView,
    VendorTransactionListCreateAPIView,
    VendorTransactionRetrieveUpdateDestroyAPIView,
    VendorTransactionSummaryAPIView,
)

urlpatterns = [
    # --- Cash Flow ---
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
    # --- Credit Entries ---
    path(
        "accounting/credits/",
        CreditEntryListAPIView.as_view(),
        name="credit-entry-list-create",
    ),
    path(
        "accounting/credits/<int:pk>/",
        CreditEntryRetrieveUpdateDestroyAPIView.as_view(),
        name="credit-entry-detail",
    ),
    path(
        "accounting/credits/<int:pk>/settle/",
        CreditSettleAPIView.as_view(),
        name="credit-entry-settle",
    ),
    path(
        "accounting/credit-stats/",
        CreditStatsAPIView.as_view(),
        name="credit-stats",
    ),
    # --- Vendors ---
    path(
        "accounting/vendors/",
        VendorListCreateAPIView.as_view(),
        name="vendor-list-create",
    ),
    path(
        "accounting/vendors/<int:pk>/",
        VendorRetrieveUpdateDestroyAPIView.as_view(),
        name="vendor-detail",
    ),
    path(
        "accounting/vendor-summary/",
        VendorSummaryAPIView.as_view(),
        name="vendor-summary",
    ),
    # --- Vendor Transactions ---
    path(
        "accounting/vendor-transactions/",
        VendorTransactionListCreateAPIView.as_view(),
        name="vendor-transaction-list-create",
    ),
    path(
        "accounting/vendor-transactions/summary/",
        VendorTransactionSummaryAPIView.as_view(),
        name="vendor-transaction-summary",
    ),
    path(
        "accounting/vendor-transactions/<int:pk>/",
        VendorTransactionRetrieveUpdateDestroyAPIView.as_view(),
        name="vendor-transaction-detail",
    ),
]
