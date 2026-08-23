from django_filters import rest_framework as filters

from blog.models import Blog


class BlogFilter(filters.FilterSet):
    search = filters.CharFilter(field_name="title", lookup_expr="icontains")
    title = filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Blog
        fields = ["search", "title"]
