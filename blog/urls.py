from django.urls import path

from blog.views import (
    BlogListCreateAPIView,
    BlogRetrieveUpdateDestroyAPIView,
)

urlpatterns = [
    path("blogs/", BlogListCreateAPIView.as_view(), name="blog-list-create"),
    path(
        "blogs/<slug:slug>/",
        BlogRetrieveUpdateDestroyAPIView.as_view(),
        name="blog-detail",
    ),
]
