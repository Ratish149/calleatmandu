from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import AllowAny

from blog.filters import BlogFilter
from blog.models import Blog
from blog.serializers import BlogSerializer
from common.utils import CustomPagination


class BlogListCreateAPIView(ListCreateAPIView):
    """
    GET  /api/blogs/   — List all blogs (supports search & filter)
    POST /api/blogs/   — Create a new blog
    """

    queryset = Blog.objects.all()
    serializer_class = BlogSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = BlogFilter
    pagination_class = CustomPagination

    search_fields = ["title", "short_description", "content"]


class BlogRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    """
    GET    /api/blogs/<slug>/   — Retrieve a blog by slug
    PUT    /api/blogs/<slug>/   — Update a blog by slug
    PATCH  /api/blogs/<slug>/   — Partial update a blog by slug
    DELETE /api/blogs/<slug>/   — Delete a blog by slug
    """

    queryset = Blog.objects.all()
    serializer_class = BlogSerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"
