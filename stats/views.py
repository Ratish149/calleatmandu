from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from common.permissions import IsStaffOrOperationalRole
from order.models import Order
from stats.filters import PeakHoursFilter, SalesStatsFilter
from stats.selectors import (
    get_best_seller_products,
    get_daily_sales_stats,
    get_dashboard_stats,
    get_peak_order_hours,
)
from stats.serializers import (
    BestSellerProductSerializer,
    DailySalesItemSerializer,
    DashboardStatsSerializer,
    PeakHourItemSerializer,
)


class DashboardStatsAPIView(GenericAPIView):
    """
    API View to retrieve dashboard summary statistics:
    - total_orders_today
    - total_revenue_today
    - total_revenue
    - total_products
    - total_orders
    """

    permission_classes = [IsStaffOrOperationalRole]
    serializer_class = DashboardStatsSerializer

    def get(self, request, *args, **kwargs):
        user = request.user
        branch_id = getattr(user, "branch_id", None)

        stats_data = get_dashboard_stats(branch_id=branch_id)
        serializer = self.get_serializer(stats_data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SalesStatsAPIView(GenericAPIView):
    """
    API View to retrieve daily sales breakdown (total orders and total revenue per day).
    Defaults to current month daily stats if no filter parameters are passed.
    Supports filters:
    - period: 'daily' (current month), 'weekly' (last 7 days), 'monthly' (last 30 days)
    - start_date: YYYY-MM-DD
    - end_date: YYYY-MM-DD
    """

    permission_classes = [IsStaffOrOperationalRole]
    serializer_class = DailySalesItemSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = SalesStatsFilter

    def get_queryset(self):
        queryset = Order.objects.all()
        user = self.request.user
        if user and user.is_authenticated and getattr(user, "branch_id", None):
            queryset = queryset.filter(branch_id=user.branch_id)
        return queryset

    def get(self, request, *args, **kwargs):
        filtered_qs = self.filter_queryset(self.get_queryset())
        sales_data = get_daily_sales_stats(filtered_qs)
        serializer = self.get_serializer(sales_data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class BestSellerProductsAPIView(GenericAPIView):
    """
    API View to retrieve top 5 best selling products aggregated from OrderItems.
    Accepts optional query parameter `limit` (default: 5).
    """

    permission_classes = [IsStaffOrOperationalRole]
    serializer_class = BestSellerProductSerializer

    def get(self, request, *args, **kwargs):
        user = request.user
        branch_id = getattr(user, "branch_id", None)

        try:
            limit = int(request.query_params.get("limit", 5))
        except (ValueError, TypeError):
            limit = 5

        best_sellers = get_best_seller_products(branch_id=branch_id, limit=limit)
        serializer = self.get_serializer(best_sellers, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PeakOrderHoursAPIView(GenericAPIView):
    """
    API View to retrieve peak order hours (total orders and total revenue grouped by hour 0-23).
    Defaults to this week's data if no filter parameters are passed.
    Supports filters:
    - period: 'weekly' (last 7 days / default), 'daily' (current month), 'monthly' (last 30 days)
    - start_date: YYYY-MM-DD
    - end_date: YYYY-MM-DD
    """

    permission_classes = [IsStaffOrOperationalRole]
    serializer_class = PeakHourItemSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = PeakHoursFilter

    def get_queryset(self):
        queryset = Order.objects.all()
        user = self.request.user
        if user and user.is_authenticated and getattr(user, "branch_id", None):
            queryset = queryset.filter(branch_id=user.branch_id)
        return queryset

    def get(self, request, *args, **kwargs):
        filtered_qs = self.filter_queryset(self.get_queryset())
        peak_hours_data = get_peak_order_hours(filtered_qs)
        serializer = self.get_serializer(peak_hours_data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
