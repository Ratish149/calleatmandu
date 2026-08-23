import json

from rest_framework import serializers

from product.models import Category, Product, ProductExtra, ProductImage, Subcategory

# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug"]
        read_only_fields = ["id", "slug"]


# ---------------------------------------------------------------------------
# Subcategory
# ---------------------------------------------------------------------------


class SubcategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Subcategory
        fields = ["id", "name", "slug", "category"]
        read_only_fields = ["id", "slug"]


# ---------------------------------------------------------------------------
# ProductExtra
# ---------------------------------------------------------------------------


class ProductExtraSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductExtra
        fields = ["id", "name", "additional_price"]
        read_only_fields = ["id"]


class ProductExtraCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductExtra
        fields = ["id", "product", "name", "additional_price"]
        read_only_fields = ["id"]


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
        fields = ["id", "image"]
        read_only_fields = ["id"]


# ---------------------------------------------------------------------------
# Product — list
# ---------------------------------------------------------------------------


class ProductListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""

    category_name = serializers.CharField(source="category.name", read_only=True)
    sub_category_name = serializers.CharField(
        source="sub_category.name", read_only=True
    )

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "price",
            "type",
            "thumbnail_image",
            "category",
            "category_name",
            "sub_category",
            "sub_category_name",
            "is_best_seller",
            "prepare_time",
        ]
        read_only_fields = ["id", "slug"]


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

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "price",
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
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]


# ---------------------------------------------------------------------------
# Product — create (write)
# ---------------------------------------------------------------------------


class ProductCreateSerializer(serializers.ModelSerializer):
    """
    Accepts a product, its extras, and additional images in a single request.

    multipart/form-data fields:
      name, description, price, type, thumbnail_image, category, sub_category, is_best_seller, prepare_time — standard fields
      extras      — JSON string, e.g. '[{"name":"Extra Cheese","additional_price":50}]'
      images      — one or more image files (send multiple 'images' fields)
    """

    extras = serializers.CharField(
        required=False,
        default="[]",
        help_text='JSON array, e.g. [{"name":"Extra Cheese","additional_price":50}]',
    )
    images = serializers.ListField(
        child=serializers.ImageField(),
        required=False,
        default=list,
    )

    class Meta:
        model = Product
        fields = [
            "name",
            "description",
            "price",
            "type",
            "thumbnail_image",
            "category",
            "sub_category",
            "is_best_seller",
            "prepare_time",
            "extras",
            "images",
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
