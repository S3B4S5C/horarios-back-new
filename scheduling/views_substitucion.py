# scheduling/views_substitucion.py
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from users.permissions import IsManagerOrStaff
from scheduling.models import Clase
from users.models import Docente
from notifications.models import Notificacion  # ajusta si tu app es diferente (e.g., api.notifications.models)

from .serializers import (
    ClaseSubstitutoUpdateSerializer,
    ClasePreviewSerializer,
)

def _dia_humano(num):
    return {1:"Lunes",2:"Martes",3:"Miércoles",4:"Jueves",5:"Viernes",6:"Sábado",7:"Domingo"}.get(num, f"Día {num}")

@extend_schema(
    tags=["sustitucion"],
    request=ClaseSubstitutoUpdateSerializer,
    responses={200: ClasePreviewSerializer},
    examples=[
        OpenApiExample(
            "Asignar sustituto",
            value={"docente_substituto": 12},
        ),
        OpenApiExample(
            "Quitar sustituto",
            value={"docente_substituto": None},
        ),
    ],
)
@api_view(["PATCH"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def clase_set_substituto_view(request, pk: int):
    """
    Cambia el docente sustituto de la clase. Si es null, no hay sustituto.
    Crea notificaciones: al docente titular y (si aplica) al nuevo sustituto.
    """
    try:
        clase = Clase.objects.select_related(
            "grupo__asignatura", "docente__user", "docente_substituto__user", "bloque_inicio"
        ).get(pk=pk)
    except Clase.DoesNotExist:
        return Response({"detail": "Clase no encontrada."}, status=404)

    ser = ClaseSubstitutoUpdateSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    new_sub_id = ser.validated_data["docente_substituto"]

    # old_sub = clase.docente_substituto
    # old_sub_id = old_sub.id if old_sub else None

    # Asignar nuevo sustituto
    new_sub = None
    if new_sub_id is not None:
        new_sub = Docente.objects.get(pk=new_sub_id)

    clase.docente_substituto = new_sub
    clase.save(update_fields=["docente_substituto"])

    # Notificaciones
    # Detalles legibles
    asig = clase.grupo.asignatura
    asignatura_txt = f"{asig.codigo} · {asig.nombre}"
    tipo_txt = "Teoría" if clase.tipo == "T" else "Práctica"
    dia_txt = _dia_humano(clase.day_of_week)
    bloque_txt = f"Bloque #{clase.bloque_inicio.orden} ×{clase.bloques_duracion}"

    # Titular (si existe)
    if clase.docente_id and hasattr(clase.docente, "user") and clase.docente.user_id:
        titulo = "Actualización de sustitución en tu clase"
        if new_sub is None:
            mensaje = (f"Se eliminó el docente sustituto de tu clase: {asignatura_txt} "
                       f"({tipo_txt}), {dia_txt}, {bloque_txt}.")
        else:
            mensaje = (f"Se asignó a {new_sub.nombre_completo} como sustituto en tu clase: "
                       f"{asignatura_txt} ({tipo_txt}), {dia_txt}, {bloque_txt}.")
        Notificacion.objects.create(
            usuario=clase.docente.user,
            clase=clase,
            titulo=titulo,
            mensaje=mensaje,
        )

    # Nuevo sustituto (si aplica)
    if new_sub is not None and hasattr(new_sub, "user") and new_sub.user_id:
        titulo = "Te asignaron como sustituto"
        titular_txt = clase.docente.nombre_completo if clase.docente_id else "(sin titular)"
        mensaje = (f"Fuiste asignado como sustituto en la clase de {asignatura_txt} "
                   f"({tipo_txt}), {dia_txt}, {bloque_txt}. Titular: {titular_txt}.")
        Notificacion.objects.create(
            usuario=new_sub.user,
            clase=clase,
            titulo=titulo,
            mensaje=mensaje,
        )

    # (Opcional) Si quieres notificar al sustituto anterior cuando se lo reemplaza:
    # if old_sub_id and new_sub_id != old_sub_id and old_sub and old_sub.user_id:
    #     Notificacion.objects.create(...)

    return Response(ClasePreviewSerializer(clase).data, status=200)


@extend_schema(
    tags=["sustitucion"],
    parameters=[
        OpenApiParameter(name="calendario", required=True, type=int),
        OpenApiParameter(name="docente", required=False, type=int, description="Filtra por docente (titular o sustituto)"),
        OpenApiParameter(name="has_substituto", required=False, type=OpenApiTypes.BOOL),
        OpenApiParameter(name="grupo", required=False, type=int),
        OpenApiParameter(name="asignatura", required=False, type=int),
    ],
    responses={200: ClasePreviewSerializer(many=True)},
    description="Lista clases por calendario con filtros opcionales. "
                "El filtro 'docente' aplica a titular O sustituto.",
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def clases_por_calendario_list_view(request):
    calendario = request.query_params.get("calendario")
    if not calendario:
        return Response({"detail": "Parámetro 'calendario' es requerido."}, status=400)

    qs = (Clase.objects.select_related(
            "grupo__asignatura", "docente", "docente_substituto", "bloque_inicio"
        )
        .filter(bloque_inicio__calendario_id=calendario)
        .exclude(estado="cancelado")
        .order_by("day_of_week", "bloque_inicio__orden", "grupo__asignatura__codigo")
    )

    docente = request.query_params.get("docente")
    if docente:
        qs = qs.filter(Q(docente_id=docente) | Q(docente_substituto_id=docente))

    has_sub = request.query_params.get("has_substituto")
    if has_sub is not None:
        val = str(has_sub).lower() in ("1", "true", "t", "yes", "y", "si", "sí")
        qs = qs.filter(docente_substituto__isnull=not val)

    grupo = request.query_params.get("grupo")
    if grupo:
        qs = qs.filter(grupo_id=grupo)

    asignatura = request.query_params.get("asignatura")
    if asignatura:
        qs = qs.filter(grupo__asignatura_id=asignatura)

    data = ClasePreviewSerializer(qs, many=True).data
    return Response(data, status=200)
