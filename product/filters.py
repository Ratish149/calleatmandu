from django.db.models import Q
from django_filters import rest_framework as filters

from product.models import Category, Product, Subcategory


class CategoryFilter(filters.FilterSet):
    name = filters.CharFilter(lookup_expr="icontains")
    search = filters.CharFilter(method="filter_search")

    class Meta:
        model = Category
        fields = ["name", "search"]

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(name__icontains=value)


class SubcategoryFilter(filters.FilterSet):
    name = filters.CharFilter(lookup_expr="icontains")
    category = filters.CharFilter(field_name="category__slug")
    search = filters.CharFilter(method="filter_search")

    class Meta:
        model = Subcategory
        fields = ["name", "category", "search"]

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(category__name__icontains=value)
        )


class ProductFilter(filters.FilterSet):
    name = filters.CharFilter(lookup_expr="icontains")
    type = filters.ChoiceFilter(choices=Product.ProductType.choices)
    category = filters.CharFilter(field_name="category__slug")
    sub_category = filters.CharFilter(field_name="sub_category__slug")
    is_best_seller = filters.BooleanFilter()
    offer = filters.CharFilter(method="filter_by_offer")
    search = filters.CharFilter(method="filter_search")

    class Meta:
        model = Product
        fields = [
            "name",
            "type",
            "category",
            "sub_category",
            "is_best_seller",
            "offer",
            "search",
        ]

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(description__icontains=value)
        )

    def filter_by_offer(self, queryset, name, value):
        from offer.models import Offer

        try:
            offer_obj = Offer.objects.get(slug=value)
        except Offer.DoesNotExist:
            return queryset.none()

        if offer_obj.offer_type == Offer.OfferType.BUY_X_GET_Y:
            bogo_product_ids = [
                pid
                for pid in [offer_obj.buy_product_id, offer_obj.get_product_id]
                if pid
            ]
            q_filter = Q(id__in=bogo_product_ids) | Q(offers=offer_obj)

            if offer_obj.scope == Offer.ScopeType.CATEGORY and offer_obj.category_id:
                q_filter |= Q(category_id=offer_obj.category_id)
            elif (
                offer_obj.scope == Offer.ScopeType.SUBCATEGORY
                and offer_obj.subcategory_id
            ):
                q_filter |= Q(sub_category_id=offer_obj.subcategory_id)
            elif offer_obj.scope == Offer.ScopeType.CART:
                if not bogo_product_ids:
                    return queryset

            return queryset.filter(q_filter).distinct()

        if offer_obj.scope == Offer.ScopeType.PRODUCT:
            return queryset.filter(offers=offer_obj).distinct()
        elif offer_obj.scope == Offer.ScopeType.CATEGORY and offer_obj.category_id:
            return queryset.filter(category_id=offer_obj.category_id)
        elif (
            offer_obj.scope == Offer.ScopeType.SUBCATEGORY and offer_obj.subcategory_id
        ):
            return queryset.filter(sub_category_id=offer_obj.subcategory_id)
        elif offer_obj.scope == Offer.ScopeType.CART:
            return queryset
        else:
            q_filter = Q()
            if offer_obj.products.exists():
                q_filter |= Q(offers=offer_obj)
            if offer_obj.category_id:
                q_filter |= Q(category_id=offer_obj.category_id)
            if offer_obj.subcategory_id:
                q_filter |= Q(sub_category_id=offer_obj.subcategory_id)

            if q_filter:
                return queryset.filter(q_filter).distinct()
            return queryset
