from django.urls import path

from stats.views import (
    BestSellerProductsAPIView,
    DashboardStatsAPIView,
    PeakOrderHoursAPIView,
    SalesStatsAPIView,
)

urlpatterns = [
    path("stats/", DashboardStatsAPIView.as_view(), name="dashboard-stats"),
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
]
