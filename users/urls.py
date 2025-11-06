from django.urls import path

from users.views_prefs import notifications_prefs_view
from .views import (
    get_all_users_view, register_view, login_view,
    assign_role_view,
    docentes_list_view, docentes_create_view, docentes_update_view, docentes_delete_view,
    my_menu_view,
)

urlpatterns = [
    # HU001
    path("register/", register_view, name="users-register"),
    path("login/", login_view, name="users-login"),

    # HU002
    path("assign-role/", assign_role_view, name="users-assign-role"),

    # HU003
    path("docentes/", docentes_list_view, name="docentes-list"),
    path("docentes/create/", docentes_create_view, name="docentes-create"),
    path("docentes/<int:pk>/", docentes_update_view, name="docentes-update"),
    path("docentes/<int:pk>/delete/", docentes_delete_view, name="docentes-delete"),

    # HU005
    path("menu/", my_menu_view, name="users-menu"),

    path("notifications/prefs/", notifications_prefs_view),

    path('', get_all_users_view, name='get-all-users'),
]
