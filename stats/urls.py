from django.urls import path

from stats.views import (
    BestSellerProductsAPIView,
    BillPrintConfigAPIView,
    DashboardStatsAPIView,
    OrderAnalyticsAPIView,
    PeakOrderHoursAPIView,
    RevenueBreakdownAPIView,
    SalesStatsAPIView,
)

urlpatterns = [
    path("stats/", DashboardStatsAPIView.as_view(), name="dashbimhgoard-stats"),
    path("stats/sales/", SalesStatsAPIView.as_view(), name="sales-stats"),
    path(
        "stats/best-sellers/",
        BestSellerProductsAPIView.as_view(),
        name="best-seller-products",
    ),
    path(
        "stats/peak-hours/",
        PeakOrderHoursAPIView.as_view(),
        name="peak-order-hours",
    ),
    path(
        "stats/order-analytics/",
        OrderAnalyticsAPIView.as_view(),
        name="order-analytics",
    ),
    path(
        "stats/revenue-breakdown/",
        RevenueBreakdownAPIView.as_view(),
        name="revenue-breakdown",
    ),
    path(
        "bill-print-config/",
        BillPrintConfigAPIView.as_view(),
        name="bill-print-config",
    ),
]
