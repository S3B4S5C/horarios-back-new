from rest_framework.permissions import BasePermission

ALLOWED_MANAGER_ROLES = {"VICERRECTORADO", "RECTOR", "JEFE_CARRERA"}

class IsManagerOrStaff(BasePermission):
    """
    Permite acciones de administración si es superuser/staff o tiene rol de gestión.
    """
    def has_permission(self, request, view):
        u = request.user
        if not u or not u.is_authenticated:
            return False
        if u.is_superuser or u.is_staff:
            return True
        role = getattr(getattr(u, "profile", None), "role", None)
        return role in ALLOWED_MANAGER_ROLES

class IsManagerOrStaff(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        if not u or not u.is_authenticated:
            return False
        if u.is_superuser or u.is_staff:
            return True
        role = getattr(getattr(u, "profile", None), "role", None)
        return role in ALLOWED_MANAGER_ROLES

class IsTeacherOrManager(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        if not u or not u.is_authenticated:
            return False
        if u.is_superuser or u.is_staff:
            return True
        role = getattr(getattr(u, "profile", None), "role", None)
        return role in (ALLOWED_MANAGER_ROLES | {"DOCENTE"})