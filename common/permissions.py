from rest_framework.permissions import BasePermission

ALLOWED_STAFF_ROLES = {"admin", "reception", "rider", "kitchen"}


class IsStaffOrOperationalRole(BasePermission):
    """
    Custom permission class that grants access only to authenticated users
    whose role is admin, reception, rider, or kitchen (or superuser/is_staff).
    Restricts access for customer token users and unauthenticated users.
    """

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False

        return (
            user.is_superuser
            or user.is_staff
            or getattr(user, "role", None) in ALLOWED_STAFF_ROLES
        )


# Alias for order specific naming context
IsOrderStaff = IsStaffOrOperationalRole
