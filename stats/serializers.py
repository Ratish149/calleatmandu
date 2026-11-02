from rest_framework import serializers

from product.models import Product


class DashboardStatsSerializer(serializers.Serializer):
    total_orders_today = serializers.IntegerField()
    total_revenue_today = serializers.FloatField()
    total_revenue = serializers.FloatField()
    total_profit = serializers.FloatField()
    total_orders = serializers.IntegerField()
    shift_start = serializers.DateTimeField(
        required=False,
        help_text="Start timestamp of the night service shift (6:00 PM).",
    )
    shift_end = serializers.DateTimeField(
        required=False,
        help_text="End timestamp of the night service shift (4:00 AM next day).",
    )


class DailySalesItemSerializer(serializers.Serializer):
    date = serializers.CharField()
    total_orders = serializers.IntegerField()
    total_revenue = serializers.FloatField()


class BestSellerProductSerializer(serializers.ModelSerializer):
    category_id = serializers.IntegerField(source="category.id", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    image = serializers.FileField(source="thumbnail_image", read_only=True)
    total_quantity_sold = serializers.IntegerField(read_only=True)
    total_revenue = serializers.FloatField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "category_id",
            "category_name",
            "price",
            "prepare_time",
            "type",
            "image",
            "total_quantity_sold",
            "total_revenue",
        ]


class BestSellerCategorySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField(allow_null=True)
    image = serializers.FileField(allow_null=True, required=False)
    total_quantity_sold = serializers.IntegerField()
    total_revenue = serializers.FloatField()


class BestSellerStatsSerializer(serializers.Serializer):
    products = BestSellerProductSerializer(many=True)
    categories = BestSellerCategorySerializer(many=True)


class PeakHourItemSerializer(serializers.Serializer):
    time_label = serializers.CharField()
    total_orders = serializers.IntegerField()
    total_revenue = serializers.FloatField()


class OrderVolumeSerializer(serializers.Serializer):
    today = serializers.IntegerField(
        help_text="Number of orders in the night service shift (6:00 PM to 4:00 AM)."
    )
    this_week = serializers.IntegerField(help_text="Number of orders this week.")
    this_month = serializers.IntegerField(help_text="Number of orders this month.")
    total = serializers.IntegerField(help_text="Total number of orders.")
    revenue_today = serializers.FloatField(
        help_text="Total revenue in the night service shift (6:00 PM to 4:00 AM)."
    )
    revenue_this_week = serializers.FloatField(help_text="Total revenue this week.")
    revenue_this_month = serializers.FloatField(help_text="Total revenue this month.")
    total_revenue = serializers.FloatField(help_text="Total revenue overall.")


class OrderTypeBreakdownItemSerializer(serializers.Serializer):
    order_type = serializers.CharField(allow_null=True)
    order_type_display = serializers.CharField()
    total_orders = serializers.IntegerField()
    total_revenue = serializers.FloatField()
    total_cost = serializers.FloatField()
    gross_profit = serializers.FloatField()
    profit_margin_percentage = serializers.FloatField()
    order_percentage = serializers.FloatField()


class OrderAnalyticsSummarySerializer(serializers.Serializer):
    total_orders = serializers.IntegerField()
    total_revenue = serializers.FloatField()
    total_cost = serializers.FloatField()
    gross_profit = serializers.FloatField()
    profit_margin_percentage = serializers.FloatField()


class OrderAnalyticsSerializer(serializers.Serializer):
    order_volume = OrderVolumeSerializer()
    by_order_type = OrderTypeBreakdownItemSerializer(many=True)
    summary = OrderAnalyticsSummarySerializer()


class RevenueBreakdownSerializer(serializers.Serializer):
    """
    Serializer representing revenue breakdown:
    - total_delivery_amount: Total delivery fees.
    - total_food_item_amount: Total revenue from food items.
    - total_liquor_or_drink_amount: Total revenue from liquor or drink items.
    - total_orders: Total non-cancelled orders count.
    - total_amount: Overall revenue.
    - start_date: Start date filter.
    - end_date: End date filter.
    """

    total_delivery_amount = serializers.FloatField(
        help_text="Total delivery fee collected across orders."
    )
    total_food_item_amount = serializers.FloatField(
        help_text="Total sales amount for food items."
    )
    total_liquor_or_drink_amount = serializers.FloatField(
        help_text="Total sales amount for liquor and drink items."
    )
    total_orders = serializers.IntegerField(
        help_text="Total count of non-cancelled orders."
    )
    total_amount = serializers.FloatField(
        help_text="Total revenue (food + drink + delivery)."
    )
    start_date = serializers.CharField(
        allow_null=True,
        required=False,
        help_text="Start date filter applied (YYYY-MM-DD).",
    )
    end_date = serializers.CharField(
        allow_null=True,
        required=False,
        help_text="End date filter applied (YYYY-MM-DD).",
    )
