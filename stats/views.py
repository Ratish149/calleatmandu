from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from common.permissions import IsStaffOrOperationalRole
from order.models import Order
from stats.filters import (
    PeakHoursFilter,
    RevenueBreakdownFilter,
    SalesStatsFilter,
)
from stats.selectors import (
    get_best_seller_categories,
    get_best_seller_products,
    get_best_sellers_stats,
    get_daily_sales_stats,
    get_dashboard_stats,
    get_order_analytics,
    get_peak_order_hours,
    get_revenue_breakdown_stats,
)
from stats.serializers import (
    BestSellerCategorySerializer,
    BestSellerProductSerializer,
    BestSellerStatsSerializer,
    DailySalesItemSerializer,
    DashboardStatsSerializer,
    OrderAnalyticsSerializer,
    PeakHourItemSerializer,
    RevenueBreakdownSerializer,
)


class DashboardStatsAPIView(GenericAPIView):
    """
    API View to retrieve dashboard summary statistics:
    - total_orders_today (calculated for night service: 6:00 PM to 4:00 AM next day)
    - total_revenue_today (calculated for night service: 6:00 PM to 4:00 AM next day)
    - total_revenue
    - total_profit
    - total_orders
    - shift_start
    - shift_end
    Supports optional `date` query parameter (YYYY-MM-DD) to query a specific night service shift.
    """

    permission_classes = [IsStaffOrOperationalRole]
    serializer_class = DashboardStatsSerializer

    def get(self, request, *args, **kwargs):
        user = request.user
        branch_id = None
        if (
            user
            and user.is_authenticated
            and not user.is_superuser
            and getattr(user, "role", None) != "admin"
        ):
            branch_id = getattr(user, "branch_id", None)
        elif request.query_params.get("branch"):
            branch_param = request.query_params.get("branch")
            if branch_param and str(branch_param).isdigit():
                branch_id = int(branch_param)

        target_date = request.query_params.get("date")

        stats_data = get_dashboard_stats(branch_id=branch_id, target_date=target_date)
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
        period = request.query_params.get("period", "daily")
        sales_data = get_daily_sales_stats(filtered_qs, period=period)
        serializer = self.get_serializer(sales_data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class BestSellerProductsAPIView(GenericAPIView):
    """
    API View to retrieve top best selling products and categories aggregated from OrderItems.
    Accepts query parameters:
    - `limit`: number of top items to return (default: 5).
    - `category`: optional category ID or slug/name to filter best selling products.
    - `by`: optional display mode: 'product' for products list, 'category' for categories list,
            or omit for combined dictionary containing both products and categories.
    """

    # permission_classes = [IsStaffOrOperationalRole]
    serializer_class = BestSellerStatsSerializer

    def get(self, request, *args, **kwargs):
        user = request.user
        branch_id = getattr(user, "branch_id", None)

        try:
            limit = int(request.query_params.get("limit", 5))
        except (ValueError, TypeError):
            limit = 5

        category = request.query_params.get("category")
        by = request.query_params.get("by")

        if by == "category":
            categories = get_best_seller_categories(branch_id=branch_id, limit=limit)
            serializer = BestSellerCategorySerializer(categories, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        elif by == "product":
            products = get_best_seller_products(
                branch_id=branch_id, category_id=category, limit=limit
            )
            serializer = BestSellerProductSerializer(products, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        best_sellers = get_best_sellers_stats(
            branch_id=branch_id, category_id=category, limit=limit
        )
        serializer = self.get_serializer(best_sellers)
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


class OrderAnalyticsAPIView(GenericAPIView):
    """
    API View to retrieve order analytics:
    - Order volume: count and revenue of orders today (night service shift), this week, this month, and total.
    - Order type data: breakdown by order type (Delivery, Dine-in, Takeaway, POS, etc.)
      including order count, revenue, cost price from OrderItems, gross profit, and margin.
    - Overall summary metrics.
    """

    # permission_classes = [IsStaffOrOperationalRole]
    serializer_class = OrderAnalyticsSerializer

    def get_queryset(self):
        queryset = Order.objects.all()
        user = self.request.user
        if user and user.is_authenticated and getattr(user, "branch_id", None):
            queryset = queryset.filter(branch_id=user.branch_id)
        return queryset

    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        analytics_data = get_order_analytics(queryset)
        serializer = self.get_serializer(analytics_data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RevenueBreakdownAPIView(GenericAPIView):
    """
    API View to retrieve revenue breakdown:
    - total_delivery_amount: Total delivery fees collected from non-cancelled orders.
    - total_food_item_amount: Total sales amount from food items.
    - total_liquor_or_drink_amount: Total sales amount from liquor or drink items.
    - total_orders: Total count of non-cancelled orders.
    - total_amount: Overall revenue.
    Filters:
    - start_date: YYYY-MM-DD (Filter starting from this date)
    - end_date: YYYY-MM-DD (Filter up to this date)
    """

    permission_classes = [IsStaffOrOperationalRole]
    serializer_class = RevenueBreakdownSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = RevenueBreakdownFilter

    def get_queryset(self):
        queryset = Order.objects.exclude(status=Order.OrderStatus.CANCELLED)
        user = self.request.user
        if (
            user
            and user.is_authenticated
            and not user.is_superuser
            and getattr(user, "role", None) != "admin"
            and getattr(user, "branch_id", None)
        ):
            queryset = queryset.filter(branch_id=user.branch_id)
        elif self.request.query_params.get("branch"):
            branch_param = self.request.query_params.get("branch")
            if branch_param and str(branch_param).isdigit():
                queryset = queryset.filter(branch_id=int(branch_param))
        return queryset

    def get(self, request, *args, **kwargs):
        filtered_orders = self.filter_queryset(self.get_queryset())
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        stats_data = get_revenue_breakdown_stats(
            orders_qs=filtered_orders,
            start_date=start_date,
            end_date=end_date,
        )
        serializer = self.get_serializer(stats_data)
        return Response(serializer.data, status=status.HTTP_200_OK)
