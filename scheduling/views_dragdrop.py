from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from users.permissions import IsManagerOrStaff
from scheduling.models import Clase, Bloque, ConflictoHorario
from .serializers import (
    DragDropMoveRequestSerializer, DragDropMoveResponseSerializer, ClaseDetailSerializer
)
from .views_conflictos import _overlap  # reutilizamos helper
from notifications.utils import notify_cambio_clase  # (lo creamos abajo)

def _validar_conflictos_para(clase, new_day, new_bloque: Bloque, new_dur):
    conflictos = []

    # 1) mismo grupo – ya cubierto por UniqueConstraint, pero lo revisamos antes
    qs_grupo = Clase.objects.filter(grupo=clase.grupo, day_of_week=new_day).exclude(pk=clase.pk)
    for x in qs_grupo.select_related("bloque_inicio"):
        if _overlap(new_bloque.orden, new_dur, x.bloque_inicio.orden, x.bloques_duracion):
            conflictos.append({"tipo":"GRUPO","clase": x.id})

    # 2) docente
    qs_doc = Clase.objects.filter(docente=clase.docente, day_of_week=new_day).exclude(pk=clase.pk)
    for x in qs_doc.select_related("bloque_inicio"):
        if _overlap(new_bloque.orden, new_dur, x.bloque_inicio.orden, x.bloques_duracion):
            conflictos.append({"tipo":"DOCENTE","clase": x.id})

    # 3) ambiente (si ya tiene)
    if clase.ambiente_id:
        qs_amb = Clase.objects.filter(ambiente=clase.ambiente, day_of_week=new_day).exclude(pk=clase.pk)
        for x in qs_amb.select_related("bloque_inicio"):
            if _overlap(new_bloque.orden, new_dur, x.bloque_inicio.orden, x.bloques_duracion):
                conflictos.append({"tipo":"AMBIENTE","clase": x.id})

    return conflictos

@extend_schema(
    tags=["dnd"],
    request=DragDropMoveRequestSerializer,
    responses={200: DragDropMoveResponseSerializer, 409: dict},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def dnd_mover_clase_view(request):
    ser = DragDropMoveRequestSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    clase_id = ser.validated_data["clase"]
    new_day = ser.validated_data["new_day_of_week"]
    new_bloque_id = ser.validated_data["new_bloque_inicio"]
    new_dur = ser.validated_data.get("new_bloques_duracion", 1)
    motivo = ser.validated_data.get("motivo","")
    dry = ser.validated_data["dry_run"]

    try:
        clase = Clase.objects.select_for_update().select_related("bloque_inicio","grupo","docente","ambiente").get(pk=clase_id)
    except Clase.DoesNotExist:
        return Response({"detail":"Clase no encontrada."}, status=404)

    new_bloque = Bloque.objects.get(pk=new_bloque_id)
    if new_bloque.calendario_id != clase.bloque_inicio.calendario_id:
        return Response({"detail":"El bloque pertenece a otro calendario."}, status=400)

    conflictos = _validar_conflictos_para(clase, new_day, new_bloque, new_dur)
    if conflictos:
        return Response({"detail":"Conflictos detectados","conflictos":conflictos}, status=409)

    if dry:
        return Response({"updated": False, "clase": ClaseDetailSerializer(clase).data, "conflictos":[]})

    from scheduling.models import CambioHorario, DiaSemana
    with transaction.atomic():
        before = {
            "old_day_of_week": clase.day_of_week,
            "old_bloque_inicio_id": clase.bloque_inicio_id,
            "old_bloques_duracion": clase.bloques_duracion,
        }
        clase.day_of_week = new_day
        clase.bloque_inicio = new_bloque
        clase.bloques_duracion = new_dur
        clase.save(update_fields=["day_of_week","bloque_inicio","bloques_duracion"])

        CambioHorario.objects.create(
            clase=clase, usuario=request.user, motivo=motivo,
            old_day_of_week=before["old_day_of_week"], old_bloque_inicio_id=before["old_bloque_inicio_id"],
            old_bloques_duracion=before["old_bloques_duracion"],
            new_day_of_week=clase.day_of_week, new_bloque_inicio=clase.bloque_inicio, new_bloques_duracion=clase.bloques_duracion,
            old_ambiente=clase.ambiente, new_ambiente=clase.ambiente,  # sin cambios
            old_docente=clase.docente, new_docente=clase.docente,
        )

    # notificar afectados
    notify_cambio_clase(clase, titulo="Clase reprogramada", motivo=motivo)

    return Response({"updated": True, "clase": ClaseDetailSerializer(clase).data, "conflictos":[]})
