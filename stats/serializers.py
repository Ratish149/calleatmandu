from rest_framework import serializers

from product.models import Product


class DashboardStatsSerializer(serializers.Serializer):
    total_orders_today = serializers.IntegerField()
    total_revenue_today = serializers.FloatField()
    total_revenue = serializers.FloatField()
    total_profit = serializers.FloatField()
    total_orders = serializers.IntegerField()


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
    today = serializers.IntegerField(help_text="Number of orders today.")
    this_week = serializers.IntegerField(help_text="Number of orders this week.")
    this_month = serializers.IntegerField(help_text="Number of orders this month.")
    total = serializers.IntegerField(help_text="Total number of orders.")
    revenue_today = serializers.FloatField(help_text="Total revenue today.")
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
