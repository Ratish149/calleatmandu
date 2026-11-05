from django.db.models import Q
from django_filters import rest_framework as filters

from product.models import Category, KitchenInventoryItem, KitchenInventoryLog, Product, Subcategory


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
    in_stock = filters.BooleanFilter(method="filter_in_stock")
    min_stock = filters.NumberFilter(field_name="stock", lookup_expr="gte")
    min_price = filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = filters.NumberFilter(field_name="price", lookup_expr="lte")
    min_cost_price = filters.NumberFilter(field_name="cost_price", lookup_expr="gte")
    max_cost_price = filters.NumberFilter(field_name="cost_price", lookup_expr="lte")
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
            "in_stock",
            "min_stock",
            "min_price",
            "max_price",
            "min_cost_price",
            "max_cost_price",
            "offer",
            "search",
        ]

    def filter_in_stock(self, queryset, name, value):
        if value is True:
            return queryset.filter(stock__gt=0)
        elif value is False:
            return queryset.filter(stock__lte=0)
        return queryset

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


# ---------------------------------------------------------------------------
# Kitchen Inventory Filters
# ---------------------------------------------------------------------------


class KitchenInventoryItemFilter(filters.FilterSet):
    """
    Filters for KitchenInventoryItem list:
    - search         : search by item name
    - unit           : filter by unit type (kg, ltr, pcs, etc.)
    - below_benchmark: true → only items where total_quantity < benchmark_quantity
    """

    search = filters.CharFilter(
        method="filter_search",
        help_text="Search by item name.",
    )
    unit = filters.ChoiceFilter(
        choices=KitchenInventoryItem.Unit.choices,
        help_text="Filter by unit type.",
    )
    below_benchmark = filters.BooleanFilter(
        method="filter_below_benchmark",
        help_text="true = only items below their benchmark quantity.",
    )

    class Meta:
        model = KitchenInventoryItem
        fields = ["search", "unit", "below_benchmark"]

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(name__icontains=value.strip())

    def filter_below_benchmark(self, queryset, name, value):
        from django.db.models import F

        if value is True:
            return queryset.filter(
                benchmark_quantity__isnull=False,
                total_quantity__lt=F("benchmark_quantity"),
            )
        elif value is False:
            return queryset.exclude(
                benchmark_quantity__isnull=False,
                total_quantity__lt=F("benchmark_quantity"),
            )
        return queryset


class KitchenInventoryLogFilter(filters.FilterSet):
    """
    Filters for KitchenInventoryLog list:
    - item       : filter by item ID
    - start_date : logs from this date (inclusive)
    - end_date   : logs up to this date (inclusive)
    - updated_by : filter by staff user ID
    - search     : search by item name or notes
    """

    item = filters.NumberFilter(
        field_name="item_id",
        help_text="Filter by item ID.",
    )
    start_date = filters.DateFilter(
        field_name="date",
        lookup_expr="gte",
        help_text="Logs from this date (YYYY-MM-DD).",
    )
    end_date = filters.DateFilter(
        field_name="date",
        lookup_expr="lte",
        help_text="Logs up to this date (YYYY-MM-DD).",
    )
    updated_by = filters.NumberFilter(
        field_name="updated_by_id",
        help_text="Filter by the staff user ID who submitted the log.",
    )
    search = filters.CharFilter(
        method="filter_search",
        help_text="Search by item name or notes.",
    )

    class Meta:
        model = KitchenInventoryLog
        fields = ["item", "start_date", "end_date", "updated_by", "search"]

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        val = value.strip()
        return queryset.filter(
            Q(item__name__icontains=val) | Q(notes__icontains=val)
        )
