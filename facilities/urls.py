from django.urls import path
from .views import (
  edificios_list_view, edificios_create_view, edificios_detail_view, edificios_update_view, edificios_delete_view,
  tipos_ambiente_list_view, tipos_ambiente_create_view, tipos_ambiente_update_view, tipos_ambiente_delete_view,
  ambientes_list_view, ambientes_create_view, ambientes_update_view, ambientes_delete_view
)

urlpatterns = [
  # HU006
  path("edificios/", edificios_list_view),
  path("edificios/create/", edificios_create_view),
  path("edificios/<int:pk>/", edificios_detail_view),
  path("edificios/<int:pk>/update/", edificios_update_view),
  path("edificios/<int:pk>/delete/", edificios_delete_view),

  # HU007
  path("tipos-ambiente/", tipos_ambiente_list_view),
  path("tipos-ambiente/create/", tipos_ambiente_create_view),
  path("tipos-ambiente/<int:pk>/update/", tipos_ambiente_update_view),
  path("tipos-ambiente/<int:pk>/delete/", tipos_ambiente_delete_view),

  path("ambientes/", ambientes_list_view),
  path("ambientes/create/", ambientes_create_view),
  path("ambientes/<int:pk>/update/", ambientes_update_view),
  path("ambientes/<int:pk>/delete/", ambientes_delete_view),
]
