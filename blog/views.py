from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import AllowAny, IsAuthenticated

from blog.filters import BlogFilter
from blog.models import Blog
from blog.serializers import BlogListSerializer, BlogSerializer
from common.utils import CustomPagination


class BlogListCreateAPIView(ListCreateAPIView):
    """
    GET  /api/blogs/   — List all blogs (supports search & filter, public access)
    POST /api/blogs/   — Create a new blog (authenticated users only)
    """

    queryset = Blog.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = BlogFilter
    pagination_class = CustomPagination

    search_fields = ["title", "short_description", "content"]

    def get_serializer_class(self):
        if self.request.method == "GET":
            return BlogListSerializer
        return BlogSerializer

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]


class BlogRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    """
    GET    /api/blogs/<slug>/   — Retrieve a blog by slug (public access)
    PUT    /api/blogs/<slug>/   — Update a blog by slug (authenticated users only)
    PATCH  /api/blogs/<slug>/   — Partial update a blog by slug (authenticated users only)
    DELETE /api/blogs/<slug>/   — Delete a blog by slug (authenticated users only)
    """

    queryset = Blog.objects.all()
    serializer_class = BlogSerializer
    lookup_field = "slug"

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]
