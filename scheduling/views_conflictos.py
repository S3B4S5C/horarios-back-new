from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter

from users.permissions import IsManagerOrStaff
from scheduling.models import Clase, ConflictoHorario, Bloque
from .serializers import DetectarConflictosRequestSerializer, ConflictoSerializer

def _overlap(a_start, a_dur, b_start, b_dur):
    a_end = a_start + a_dur - 1
    b_end = b_start + b_dur - 1
    return not (a_end < b_start or b_end < a_start)

def _conflictos_en_queryset(qs):
    hallados = []
    por_dia = {}
    for c in qs.select_related("bloque_inicio", "docente", "ambiente", "grupo"):
        por_dia.setdefault(c.day_of_week, []).append(c)

    for day, clases in por_dia.items():
        n = len(clases)
        for i in range(n):
            ci = clases[i]
            for j in range(i+1, n):
                cj = clases[j]
                if _overlap(ci.bloque_inicio.orden, ci.bloques_duracion,
                            cj.bloque_inicio.orden, cj.bloques_duracion):
                    if ci.docente_id and ci.docente_id == cj.docente_id:
                        hallados.append(("DOCENTE", ci, cj))
                    if ci.ambiente_id and cj.ambiente_id and ci.ambiente_id == cj.ambiente_id:
                        hallados.append(("AMBIENTE", ci, cj))
                    if ci.grupo_id == cj.grupo_id:
                        hallados.append(("GRUPO", ci, cj))
    return hallados

@extend_schema(
    tags=["conflictos"],
    request=DetectarConflictosRequestSerializer,
    responses={200: ConflictoSerializer(many=True)},
)
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def conflictos_detectar_view(request):
    ser = DetectarConflictosRequestSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    periodo_id = ser.validated_data["periodo"]
    calendario_id = ser.validated_data.get("calendario")
    persistir = ser.validated_data["persistir"]

    qs = Clase.objects.filter(grupo__periodo_id=periodo_id).exclude(estado="cancelado")
    if calendario_id:
        qs = qs.filter(bloque_inicio__calendario_id=calendario_id)

    hallados = _conflictos_en_queryset(qs)
    resp = []
    for tipo, a, b in hallados:
        if persistir:
            obj = ConflictoHorario.objects.create(tipo=tipo, clase_a=a, clase_b=b, resuelto=False, nota="")
        else:
            obj = ConflictoHorario(tipo=tipo, clase_a=a, clase_b=b, resuelto=False)  # fake instance
            obj.id = None
        resp.append({"id": obj.id, "tipo": tipo, "clase_a": a.id, "clase_b": b.id,
                     "resuelto": False, "nota": "", "detectado_en": getattr(obj, "detectado_en", None)})
    return Response(resp)

@extend_schema(tags=["conflictos"], responses={200: ConflictoSerializer(many=True)})
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def conflictos_list_view(request):
    qs = ConflictoHorario.objects.all().order_by("-detectado_en")
    tipo = request.query_params.get("tipo")
    res = request.query_params.get("resuelto")
    if tipo: qs = qs.filter(tipo=tipo)
    if res in {"true","false"}: qs = qs.filter(resuelto=(res=="true"))
    return Response(ConflictoSerializer(qs, many=True).data)

@extend_schema(tags=["conflictos"], responses={200: ConflictoSerializer})
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def conflictos_resolver_view(request, pk: int):
    try:
        c = ConflictoHorario.objects.get(pk=pk)
    except ConflictoHorario.DoesNotExist:
        return Response({"detail": "No encontrado."}, status=404)
    nota = request.data.get("nota", "")
    c.resuelto = True
    c.nota = nota
    c.save(update_fields=["resuelto","nota"])
    return Response(ConflictoSerializer(c).data)
