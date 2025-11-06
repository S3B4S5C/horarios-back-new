from hashlib import md5
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from users.permissions import IsTeacherOrManager
from scheduling.models import Clase, Bloque, Calendario, DiaSemana
from academics.models import Grupo
from .serializers import GridRequestSerializer, GridResponseSerializer

def _color_hex_from_text(txt: str) -> str:
    h = md5((txt or "x").encode()).hexdigest()[:6]
    return f"#{h}"

@extend_schema(
    tags=["grid"],
    request=GridRequestSerializer,
    responses={200: GridResponseSerializer},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsTeacherOrManager])
def grid_semana_view(request):
    """Devuelve la grilla 5×N (o 6×N) con celdas por clase, filtrable por docente/grupo/aula."""
    ser = GridRequestSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    periodo_id = ser.validated_data["periodo"]
    calendario_id = ser.validated_data["calendario"]
    docente_id = ser.validated_data.get("docente")
    grupo_id = ser.validated_data.get("grupo")
    ambiente_id = ser.validated_data.get("ambiente")
    bmin = ser.validated_data.get("bloque_min")
    bmax = ser.validated_data.get("bloque_max")

    bloques_qs = Bloque.objects.filter(calendario_id=calendario_id).order_by("orden")
    if bmin: bloques_qs = bloques_qs.filter(orden__gte=bmin)
    if bmax: bloques_qs = bloques_qs.filter(orden__lte=bmax)
    bloques = list(bloques_qs)

    qs = Clase.objects.select_related(
        "bloque_inicio","docente","ambiente","grupo__asignatura"
    ).filter(grupo__periodo_id=periodo_id, bloque_inicio__calendario_id=calendario_id)\
     .exclude(estado="cancelado")

    # visibilidad: si es DOCENTE, restringir a sus clases
    role = getattr(getattr(request.user, "profile", None), "role", None)
    if role == "DOCENTE":
        qs = qs.filter(docente__user=request.user)

    if docente_id: qs = qs.filter(docente_id=docente_id)
    if grupo_id: qs = qs.filter(grupo_id=grupo_id)
    if ambiente_id: qs = qs.filter(ambiente_id=ambiente_id)

    dias = [DiaSemana.LUNES, DiaSemana.MARTES, DiaSemana.MIERCOLES, DiaSemana.JUEVES, DiaSemana.VIERNES]

    celdas = []
    for c in qs:
        asig = c.grupo.asignatura
        celdas.append({
            "day_of_week": int(c.day_of_week),
            "bloque_inicio_orden": c.bloque_inicio.orden,
            "bloques_duracion": c.bloques_duracion,
            "clase_id": c.id,
            "grupo_id": c.grupo_id,
            "asignatura_id": asig.id,
            "docente_id": c.docente_id,
            "ambiente_id": c.ambiente_id,
            "asignatura": asig.nombre,
            "grupo_codigo": c.grupo.codigo,
            "docente": c.docente.nombre_completo if c.docente_id else "",
            "ambiente": str(c.ambiente) if c.ambiente_id else None,
            "tipo": c.tipo,
            "color": _color_hex_from_text(asig.codigo or asig.nombre),
        })

    return Response({
        "calendario": calendario_id,
        "periodo": periodo_id,
        "dias": [int(d) for d in dias],
        "bloques": [
            {"id": b.id, "orden": b.orden, "hora_inicio": b.hora_inicio, "hora_fin": b.hora_fin, "duracion_min": b.duracion_min}
            for b in bloques
        ],
        "celdas": celdas
    })
