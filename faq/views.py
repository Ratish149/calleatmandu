from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import AllowAny, IsAuthenticated

from faq.models import Faq
from faq.serializers import FaqSerializer


class FaqListCreateAPIView(ListCreateAPIView):
    """
    GET  /api/faqs/   — List all FAQs (supports search & filter, public access)
    POST /api/faqs/   — Create a new FAQ (authenticated users only)
    """

    queryset = Faq.objects.all()
    serializer_class = FaqSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ["question", "answer"]

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]


class FaqRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    """
    GET    /api/faqs/<pk>/   — Retrieve a FAQ by ID (public access)
    PUT    /api/faqs/<pk>/   — Update a FAQ by ID (authenticated users only)
    PATCH  /api/faqs/<pk>/   — Partial update a FAQ by ID (authenticated users only)
    DELETE /api/faqs/<pk>/   — Delete a FAQ by ID (authenticated users only)
    """

    queryset = Faq.objects.all()
    serializer_class = FaqSerializer

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]
