from rest_framework.permissions import BasePermission

ALLOWED_STAFF_ROLES = {"admin", "reception", "rider", "kitchen", "staff"}


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


class IsAdminRole(BasePermission):
    """
    Custom permission class that grants access only to authenticated users
    whose role is 'admin' or who are Django superusers.
    Restricts access for all other roles (reception, rider, kitchen, staff, customer).
    """

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False

        return bool(user.is_superuser or getattr(user, "role", None) == "admin")


# Alias for order specific naming context
IsOrderStaff = IsStaffOrOperationalRole
