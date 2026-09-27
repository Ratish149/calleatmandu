from rest_framework.permissions import SAFE_METHODS, BasePermission

from common.permissions import IsStaffOrOperationalRole


class IsStaffOrReadOnly(BasePermission):
    """
    Grants read-only access to all requests (safe methods),
    and restricts write actions to staff/operational roles.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and IsStaffOrOperationalRole().has_permission(request, view)
        )
