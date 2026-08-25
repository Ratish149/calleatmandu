from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import AllowAny

from common.permissions import IsStaffOrOperationalRole
from common.utils import CustomPagination
from contact.models import Contact
from contact.serializers import ContactSerializer


class ContactListCreateAPIView(ListCreateAPIView):
    """
    GET  /api/contacts/   — List all contact submissions (staff/operational roles only)
    POST /api/contacts/   — Create a new contact submission (public)
    """

    queryset = Contact.objects.all()
    serializer_class = ContactSerializer
    pagination_class = CustomPagination

    def get_permissions(self):
        if self.request.method == "POST":
            return [AllowAny()]
        return [IsStaffOrOperationalRole()]


class ContactRetrieveUpdateDestroyAPIView(RetrieveUpdateDestroyAPIView):
    """
    GET    /api/contacts/<pk>/   — Retrieve a contact submission by ID (staff/operational roles only)
    PUT    /api/contacts/<pk>/   — Update a contact submission by ID (staff/operational roles only)
    PATCH  /api/contacts/<pk>/   — Partial update a contact submission by ID (staff/operational roles only)
    DELETE /api/contacts/<pk>/   — Delete a contact submission by ID (staff/operational roles only)
    """

    queryset = Contact.objects.all()
    serializer_class = ContactSerializer
    permission_classes = [IsStaffOrOperationalRole]
