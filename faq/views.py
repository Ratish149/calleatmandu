from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import AllowAny

from faq.models import Faq
from faq.serializers import FaqSerializer


class FaqListCreateAPIView(ListCreateAPIView):
    """
    GET  /api/faqs/   — List all FAQs (supports search & filter)
    POST /api/faqs/   — Create a new FAQ
    """

    queryset = Faq.objects.all()
    serializer_class = FaqSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ["question", "answer"]


class FaqRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    """
    GET    /api/faqs/<pk>/   — Retrieve a FAQ by ID
    PUT    /api/faqs/<pk>/   — Update a FAQ by ID
    PATCH  /api/faqs/<pk>/   — Partial update a FAQ by ID
    DELETE /api/faqs/<pk>/   — Delete a FAQ by ID
    """

    queryset = Faq.objects.all()
    serializer_class = FaqSerializer
    permission_classes = [AllowAny]
