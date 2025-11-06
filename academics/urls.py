from django.urls import path, include

from academics.views_clases import ClasesBulkCreateAPIView, ClasesBulkDeleteAPIView, ClasesBulkUpdateAPIView, ClasesDeGrupoListAPIView, GrupoPlanificacionListAPIView
from .views import (
    asignaturas_list_view, asignaturas_create_view,
    asignaturas_detail_view, asignaturas_update_view, asignaturas_delete_view, carreras_list_view
)
from academics.views_grupos import GrupoViewSet
from rest_framework.routers import SimpleRouter
from .crud_views import PeriodoViewSet

grupo_list = GrupoViewSet.as_view({"get": "list"})
grupo_create = GrupoViewSet.as_view({"post": "create_one"})
grupo_bulk = GrupoViewSet.as_view({"post": "bulk_create"})
grupo_update = GrupoViewSet.as_view(
    {"put": "update_one", "patch": "update_one"})
grupo_delete = GrupoViewSet.as_view({"delete": "delete_one"})

router = SimpleRouter()
router.register(r"periodos", PeriodoViewSet, basename="periodos")


urlpatterns = [
    path("asignaturas/", asignaturas_list_view, name="asignaturas-list"),
    path("asignaturas/create/", asignaturas_create_view, name="asignaturas-create"),
    path("asignaturas/<int:pk>/", asignaturas_detail_view,
         name="asignaturas-detail"),
    path("asignaturas/<int:pk>/update/",
         asignaturas_update_view, name="asignaturas-update"),
    path("asignaturas/<int:pk>/delete/",
         asignaturas_delete_view, name="asignaturas-delete"),
    path('carreras/', carreras_list_view, name='carreras-list'),
    path("grupos/", grupo_list, name="grupo-list"),
    path("grupos/create/", grupo_create, name="grupo-create"),
    path("grupos/bulk-create/", grupo_bulk, name="grupo-bulk-create"),
    path("grupos/<int:pk>/update/", grupo_update, name="grupo-update"),
    path("grupos/<int:pk>/delete/", grupo_delete, name="grupo-delete"),
    
    path("grupos/planificacion/", GrupoPlanificacionListAPIView.as_view()),
    path("clases/bulk-create/", ClasesBulkCreateAPIView.as_view()),
    path("grupos/<int:id>/clases/", ClasesDeGrupoListAPIView.as_view()),
    path("clases/bulk-update/", ClasesBulkUpdateAPIView.as_view()),
    path("clases/bulk-delete/", ClasesBulkDeleteAPIView.as_view()),
    path("", include(router.urls)),
]
