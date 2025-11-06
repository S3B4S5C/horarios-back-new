from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter

from users.permissions import IsManagerOrStaff
from users.models import Docente
from scheduling.models import Clase, Calendario

from .serializers import CargaDocenteResponseSerializer

@extend_schema(
    tags=["cargas"],
    parameters=[
        OpenApiParameter("periodo", int, OpenApiParameter.QUERY, required=True),
        OpenApiParameter("calendario", int, OpenApiParameter.QUERY, required=True),
    ],
    responses={200: CargaDocenteResponseSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def cargas_docentes_view(request):
    try:
        periodo_id = int(request.query_params["periodo"])
        calendario_id = int(request.query_params["calendario"])
    except (KeyError, ValueError):
        return Response({"detail": "periodo y calendario son requeridos."}, status=400)

    cal = Calendario.objects.get(pk=calendario_id)
    m = cal.duracion_bloque_min or 45

    items = []
    docentes = Docente.objects.filter(activo=True)
    # agrupar clases por docente
    for d in docentes:
        qs = Clase.objects.filter(docente=d, grupo__periodo_id=periodo_id).exclude(estado="cancelado")
        bloques = sum(qs.values_list("bloques_duracion", flat=True)) or 0
        horas_45 = (bloques * m) / 45.0
        estado = "OK"
        if horas_45 < d.carga_min_semanal: estado = "BAJO"
        if horas_45 > d.carga_max_semanal and d.carga_max_semanal > 0: estado = "EXCESO"
        items.append({
            "docente": d.id, "nombre": d.nombre_completo, "horas_45": round(horas_45, 2),
            "carga_min_semanal": d.carga_min_semanal, "carga_max_semanal": d.carga_max_semanal,
            "estado": estado, "clases": qs.count()
        })

    return Response({"periodo": periodo_id, "calendario": calendario_id, "items": items})
