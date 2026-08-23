from django_filters import rest_framework as filters

from product.models import Product


class ProductFilter(filters.FilterSet):
    name = filters.CharFilter(lookup_expr="icontains")
    type = filters.ChoiceFilter(choices=Product.ProductType.choices)
    category = filters.CharFilter(field_name="category__slug")
    sub_category = filters.CharFilter(field_name="sub_category__slug")
    is_best_seller = filters.BooleanFilter()

    class Meta:
        model = Product
        fields = [
            "name",
            "type",
            "category",
            "sub_category",
            "is_best_seller",
        ]
