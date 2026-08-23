from django.urls import path

from contact.views import (
    ContactListCreateAPIView,
    ContactRetrieveUpdateDestroyAPIView,
)

urlpatterns = [
    path("contacts/", ContactListCreateAPIView.as_view(), name="contact-list-create"),
    path(
        "contacts/<int:pk>/",
        ContactRetrieveUpdateDestroyAPIView.as_view(),
        name="contact-detail",
    ),
]
