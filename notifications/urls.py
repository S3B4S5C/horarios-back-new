from django.urls import path
from .views import notificaciones_list_view, notificaciones_marcar_leida_view

urlpatterns = [
    path("", notificaciones_list_view),
    path("<int:pk>/read/", notificaciones_marcar_leida_view),
]
