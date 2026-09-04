from rest_framework import serializers

from product.models import Product


class DashboardStatsSerializer(serializers.Serializer):
    total_orders_today = serializers.IntegerField()
    total_revenue_today = serializers.FloatField()
    total_revenue = serializers.FloatField()
    total_products = serializers.IntegerField()
    total_orders = serializers.IntegerField()


class DailySalesItemSerializer(serializers.Serializer):
    date = serializers.CharField()
    total_orders = serializers.IntegerField()
    total_revenue = serializers.FloatField()


class BestSellerProductSerializer(serializers.ModelSerializer):
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
            "category_name",
            "price",
            "prepare_time",
            "type",
            "image",
            "total_quantity_sold",
            "total_revenue",
        ]


class PeakHourItemSerializer(serializers.Serializer):
    time_label = serializers.CharField()
    total_orders = serializers.IntegerField()
    total_revenue = serializers.FloatField()
