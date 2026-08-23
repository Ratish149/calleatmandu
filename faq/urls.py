from django.urls import path

from faq.views import (
    FaqListCreateAPIView,
    FaqRetrieveUpdateDestroyAPIView,
)

urlpatterns = [
    path("faqs/", FaqListCreateAPIView.as_view(), name="faq-list-create"),
    path("faqs/<int:pk>/", FaqRetrieveUpdateDestroyAPIView.as_view(), name="faq-detail"),
]
