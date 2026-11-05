import json

from rest_framework import serializers

from offer.selectors import calculate_product_offer_price, get_active_offers
from product.models import (
    Category,
    KitchenInventoryItem,
    KitchenInventoryLog,
    Product,
    ProductExtra,
    ProductImage,
    Subcategory,
)

# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug", "image", "created_at", "updated_at"]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]


# ---------------------------------------------------------------------------
# Subcategory
# ---------------------------------------------------------------------------


class SubcategorySerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Subcategory
        fields = [
            "id",
            "name",
            "slug",
            "image",
            "category",
            "category_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]


# ---------------------------------------------------------------------------
# ProductExtra
# ---------------------------------------------------------------------------


class ProductExtraSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductExtra
        fields = ["id", "name", "additional_price", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProductExtraCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductExtra
        fields = [
            "id",
            "product",
            "name",
            "additional_price",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "product", "created_at", "updated_at"]


class ProductExtraInlineSerializer(serializers.Serializer):
    """Used to validate individual extra entries during product creation."""

    name = serializers.CharField(max_length=100)
    additional_price = serializers.FloatField(default=0.0)


# ---------------------------------------------------------------------------
# ProductImage
# ---------------------------------------------------------------------------


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "image", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProductImageCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "product", "image", "created_at", "updated_at"]
        read_only_fields = ["id", "product", "created_at", "updated_at"]


# ---------------------------------------------------------------------------
# Product — list
# ---------------------------------------------------------------------------


class ProductListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""

    category_name = serializers.CharField(source="category.name", read_only=True)
    image = serializers.FileField(source="thumbnail_image", read_only=True)
    offer_price = serializers.SerializerMethodField()
    extras = ProductExtraSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "category_name",
            "price",
            "offer_price",
            "prepare_time",
            "stock",
            "is_best_seller",
            "type",
            "image",
            "extras",
            "take_order",
        ]

    def get_offer_price(self, obj):
        active_offers = self.context.get("active_offers")
        if active_offers is None:
            if not hasattr(self, "_cached_active_offers"):
                self._cached_active_offers = get_active_offers()
            active_offers = self._cached_active_offers
        return calculate_product_offer_price(obj, active_offers)


# ---------------------------------------------------------------------------
# Product — detail (read)
# ---------------------------------------------------------------------------


class ProductDetailSerializer(serializers.ModelSerializer):
    """Full serializer with nested extras and images."""

    category_name = serializers.CharField(source="category.name", read_only=True)
    sub_category_name = serializers.CharField(
        source="sub_category.name", read_only=True
    )
    extras = ProductExtraSerializer(many=True, read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    offer_price = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "price",
            "cost_price",
            "offer_price",
            "type",
            "thumbnail_image",
            "category",
            "category_name",
            "sub_category",
            "sub_category_name",
            "is_best_seller",
            "prepare_time",
            "extras",
            "images",
            "stock",
            "take_order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]

    def get_offer_price(self, obj):
        active_offers = self.context.get("active_offers")
        if active_offers is None:
            if not hasattr(self, "_cached_active_offers"):
                self._cached_active_offers = get_active_offers()
            active_offers = self._cached_active_offers
        return calculate_product_offer_price(obj, active_offers)


# ---------------------------------------------------------------------------
# Product — create/update (write)
# ---------------------------------------------------------------------------


class ProductCreateSerializer(serializers.ModelSerializer):
    """
    Accepts a product, its extras, and additional images in a single request.

    multipart/form-data fields:
      name, description, price, type, thumbnail_image, category, sub_category, is_best_seller, prepare_time, stock — standard fields
      extras      — JSON string, e.g. '[{"name":"Extra Cheese","additional_price":50}]'
      images      — one or more image files (send multiple 'images' fields)
    """

    extras = serializers.CharField(
        required=False,
        default="[]",
        write_only=True,
        help_text='JSON array, e.g. [{"name":"Extra Cheese","additional_price":50}]',
    )
    images = serializers.ListField(
        child=serializers.ImageField(),
        required=False,
        default=list,
        write_only=True,
    )

    class Meta:
        model = Product
        fields = [
            "name",
            "description",
            "price",
            "cost_price",
            "type",
            "thumbnail_image",
            "category",
            "sub_category",
            "is_best_seller",
            "prepare_time",
            "extras",
            "images",
            "take_order",
            "stock",
        ]

    def validate_extras(self, value):
        """Parse JSON string and validate each extra entry."""
        if isinstance(value, list):
            # already parsed (e.g. in tests)
            data = value
        else:
            try:
                data = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                raise serializers.ValidationError(
                    'Invalid JSON. Expected format: [{"name": "...", "additional_price": 0}]'
                )

        if not isinstance(data, list):
            raise serializers.ValidationError("extras must be a JSON array.")

        validated = []
        for i, item in enumerate(data):
            s = ProductExtraInlineSerializer(data=item)
            if not s.is_valid():
                raise serializers.ValidationError({f"extras[{i}]": s.errors})
            validated.append(s.validated_data)

        return validated

    def create(self, validated_data):
        extras_data = validated_data.pop("extras", [])
        images_data = validated_data.pop("images", [])

        product = Product.objects.create(**validated_data)

        if extras_data:
            ProductExtra.objects.bulk_create([
                ProductExtra(
                    product=product,
                    name=extra["name"],
                    additional_price=extra.get("additional_price", 0.0),
                )
                for extra in extras_data
            ])

        if images_data:
            ProductImage.objects.bulk_create([
                ProductImage(product=product, image=image) for image in images_data
            ])

        # Re-fetch with all relations for the response
        return (
            Product.objects
            .select_related("category", "sub_category")
            .prefetch_related("extras", "images")
            .get(pk=product.pk)
        )

    def update(self, instance, validated_data):
        extras_data = validated_data.pop("extras", None)
        images_data = validated_data.pop("images", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if extras_data is not None:
            instance.extras.all().delete()
            ProductExtra.objects.bulk_create([
                ProductExtra(
                    product=instance,
                    name=extra["name"],
                    additional_price=extra.get("additional_price", 0.0),
                )
                for extra in extras_data
            ])

        if images_data is not None:
            ProductImage.objects.bulk_create([
                ProductImage(product=instance, image=image) for image in images_data
            ])

        return (
            Product.objects
            .select_related("category", "sub_category")
            .prefetch_related("extras", "images")
            .get(pk=instance.pk)
        )


# ---------------------------------------------------------------------------
# Kitchen Inventory
# ---------------------------------------------------------------------------


class KitchenInventoryItemSerializer(serializers.ModelSerializer):
    """
    Read / list serializer for KitchenInventoryItem.
    Includes a computed flag that tells the client whether stock is below benchmark.
    """

    is_below_benchmark = serializers.BooleanField(read_only=True)

    class Meta:
        model = KitchenInventoryItem
        fields = [
            "id",
            "name",
            "unit",
            "total_quantity",
            "benchmark_quantity",
            "is_below_benchmark",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "total_quantity", "is_below_benchmark", "created_at", "updated_at"]

    def validate_benchmark_quantity(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Benchmark quantity cannot be negative.")
        return value


class KitchenInventoryLogSerializer(serializers.ModelSerializer):
    """
    Serializer for daily kitchen inventory logs submitted by kitchen staff.

    Staff enter:
      - item            : FK to the inventory item
      - date            : defaults to today
      - received_quantity : new stock added today  (increases total)
      - consumed_quantity : quantity used today     (decreases total)
      - notes           : optional remarks

    Read-only extras:
      - item_name / item_unit  : for display
      - net_change             : received - consumed (positive = gain)
      - updated_by_username    : who submitted this log
    """

    item_name = serializers.CharField(source="item.name", read_only=True)
    item_unit = serializers.CharField(source="item.unit", read_only=True)
    net_change = serializers.DecimalField(
        max_digits=10, decimal_places=3, read_only=True
    )
    updated_by_username = serializers.CharField(
        source="updated_by.username", read_only=True
    )
    is_below_benchmark = serializers.BooleanField(read_only=True)

    class Meta:
        model = KitchenInventoryLog
        fields = [
            "id",
            "item",
            "item_name",
            "item_unit",
            "date",
            "received_quantity",
            "consumed_quantity",
            "net_change",
            "is_below_benchmark",
            "notes",
            "updated_by",
            "updated_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "item_name",
            "item_unit",
            "net_change",
            "is_below_benchmark",
            "updated_by",
            "updated_by_username",
            "created_at",
            "updated_at",
        ]

    def validate_received_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError("Received quantity cannot be negative.")
        return value

    def validate_consumed_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError("Consumed quantity cannot be negative.")
        return value

    def validate(self, attrs):
        # Warn if more is consumed than is currently in stock (optional guard)
        item = attrs.get("item") or (self.instance.item if self.instance else None)
        consumed = attrs.get(
            "consumed_quantity",
            getattr(self.instance, "consumed_quantity", 0),
        )
        received = attrs.get(
            "received_quantity",
            getattr(self.instance, "received_quantity", 0),
        )
        if item:
            projected = item.total_quantity + received - consumed
            if projected < 0:
                raise serializers.ValidationError(
                    {
                        "consumed_quantity": (
                            f"Cannot consume {consumed} {item.unit}. "
                            f"Current stock is {item.total_quantity} {item.unit}. "
                            f"This would result in negative stock."
                        )
                    }
                )
        return attrs

    def create(self, validated_data):
        validated_data["updated_by"] = self.context["request"].user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data["updated_by"] = self.context["request"].user
        return super().update(instance, validated_data)
