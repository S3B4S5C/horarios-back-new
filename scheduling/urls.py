from django.urls import include, path
from .views import (
    asignacion_docentes_proponer_view, calendarios_list_view, calendarios_create_view, calendarios_update_view, calendarios_delete_view,
    bloques_list_view, bloques_create_view, bloques_update_view, bloques_delete_view, clases_proponer_view,
    disponibilidad_list_view, disponibilidad_create_view, disponibilidad_update_view, disponibilidad_delete_view,
    disponibilidad_import_csv_view
)

from .views_conflictos import conflictos_detectar_view, conflictos_list_view, conflictos_resolver_view
from .views_cargas import cargas_docentes_view
from .views_aulas import asignar_aulas_view
from .views_grid import grid_semana_view
from .views_dragdrop import dnd_mover_clase_view
from .views_substitucion import clase_set_substituto_view, clases_por_calendario_list_view
from .views_export import export_pdf_view

from rest_framework.routers import SimpleRouter
from .crud_views import CalendarioViewSet

router = SimpleRouter()
router.register(r"calendarios", CalendarioViewSet, basename="calendarios")


urlpatterns = [
    # HU008
    path("calendarios/", calendarios_list_view),
    path("calendarios/create/", calendarios_create_view),
    path("calendarios/<int:pk>/update/", calendarios_update_view),
    path("calendarios/<int:pk>/delete/", calendarios_delete_view),

    path("bloques/", bloques_list_view),
    path("bloques/create/", bloques_create_view),
    path("bloques/<int:pk>/update/", bloques_update_view),
    path("bloques/<int:pk>/delete/", bloques_delete_view),

    # HU009
    path("disponibilidad/", disponibilidad_list_view),
    path("disponibilidad/create/", disponibilidad_create_view),
    path("disponibilidad/<int:pk>/update/", disponibilidad_update_view),
    path("disponibilidad/<int:pk>/delete/", disponibilidad_delete_view),
    path("disponibilidad/import-csv/", disponibilidad_import_csv_view),

    # HU011
    path("asignacion/docentes/proponer/", asignacion_docentes_proponer_view),
    path("asignacion/clases/proponer/", clases_proponer_view),

    # HU012
    path("conflictos/detectar/", conflictos_detectar_view),
    path("conflictos/", conflictos_list_view),
    path("conflictos/<int:pk>/resolver/", conflictos_resolver_view),

    # HU013
    path("cargas/docentes/", cargas_docentes_view),

    # HU014
    path("aulas/asignar/", asignar_aulas_view),

        # HU015
    path("grid/semana/", grid_semana_view),

    # HU016
    path("dnd/mover/", dnd_mover_clase_view),

    path("export/pdf/", export_pdf_view),
    path("clasesPrev/<int:pk>/substituto/", clase_set_substituto_view, name="clase-set-substituto"),
    path("clasesPrev/", clases_por_calendario_list_view, name="clases-por-calendario"),
]
