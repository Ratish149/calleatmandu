from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import AllowAny, IsAuthenticated

from common.utils import CustomPagination
from contact.models import Contact
from contact.serializers import ContactSerializer


class ContactListCreateAPIView(ListCreateAPIView):
    """
    GET  /api/contacts/   — List all contact submissions (authenticated users only)
    POST /api/contacts/   — Create a new contact submission (public)
    """

    queryset = Contact.objects.all()
    serializer_class = ContactSerializer
    pagination_class = CustomPagination

    def get_permissions(self):
        if self.request.method == "POST":
            return [AllowAny()]
        return [IsAuthenticated()]


class ContactRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    """
    GET    /api/contacts/<pk>/   — Retrieve a contact submission by ID (authenticated)
    PUT    /api/contacts/<pk>/   — Update a contact submission by ID (authenticated)
    PATCH  /api/contacts/<pk>/   — Partial update a contact submission by ID (authenticated)
    DELETE /api/contacts/<pk>/   — Delete a contact submission by ID (authenticated)
    """

    queryset = Contact.objects.all()
    serializer_class = ContactSerializer
    permission_classes = [IsAuthenticated]
