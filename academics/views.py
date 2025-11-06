import math, re
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiParameter

from users.permissions import IsManagerOrStaff
from academics.models import Asignatura, Carrera
from academics.serializers import AsignaturaSerializer, CarreraSerializer
from users.permissions import IsManagerOrStaff
from academics.models import Grupo, Preinscripcion, Turno, Asignatura, Periodo
from academics.serializers import GrupoSerializer, SugerenciaGruposResponseSerializer


@extend_schema(tags=["asignaturas"], responses={200: AsignaturaSerializer(many=True)})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def asignaturas_list_view(request):
    qs = Asignatura.objects.all().order_by("carrera__sigla", "codigo")
    carrera_id = request.query_params.get("carrera")
    if carrera_id:
        qs = qs.filter(carrera_id=carrera_id)
    return Response(AsignaturaSerializer(qs, many=True).data)


@extend_schema(
    tags=["asignaturas"],
    request=AsignaturaSerializer,
    responses={201: AsignaturaSerializer},
    examples=[OpenApiExample("Crear asignatura", value={
        "carrera": 1, "codigo": "BIO101", "nombre": "Bioquímica I",
        "horas_teoria_semana": 4, "horas_practica_semana": 2
    })],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def asignaturas_create_view(request):
    ser = AsignaturaSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    obj = ser.save()
    return Response(AsignaturaSerializer(obj).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["asignaturas"], responses={200: AsignaturaSerializer})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def asignaturas_detail_view(request, pk: int):
    try:
        obj = Asignatura.objects.get(pk=pk)
    except Asignatura.DoesNotExist:
        return Response({"detail": "No encontrado."}, status=404)
    return Response(AsignaturaSerializer(obj).data)


@extend_schema(tags=["asignaturas"], request=AsignaturaSerializer, responses={200: AsignaturaSerializer})
@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def asignaturas_update_view(request, pk: int):
    try:
        obj = Asignatura.objects.get(pk=pk)
    except Asignatura.DoesNotExist:
        return Response({"detail": "No encontrado."}, status=404)
    ser = AsignaturaSerializer(instance=obj, data=request.data, partial=(request.method == "PATCH"))
    ser.is_valid(raise_exception=True)
    obj = ser.save()
    return Response(AsignaturaSerializer(obj).data)


@extend_schema(tags=["asignaturas"], responses={204: None})
@api_view(["DELETE"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def asignaturas_delete_view(request, pk: int):
    try:
        obj = Asignatura.objects.get(pk=pk)
    except Asignatura.DoesNotExist:
        return Response({"detail": "No encontrado."}, status=404)
    obj.delete()
    return Response(status=204)

def _prefix_por_turno(nombre_turno: str) -> str:
    n = (nombre_turno or "").lower()
    if "mañana" in n: return "A"
    if "tarde" in n:  return "B"
    if "noche" in n:  return "C"
    return "G"  # genérico

def _proximo_indice_existente(asignatura_id, periodo_id, prefix):
    existentes = Grupo.objects.filter(asignatura_id=asignatura_id, periodo_id=periodo_id, codigo__startswith=prefix)\
                              .values_list("codigo", flat=True)
    nums = []
    for c in existentes:
        m = re.match(rf"^{prefix}(\d+)$", c)
        if m: nums.append(int(m.group(1)))
    return (max(nums) if nums else 0) + 1

@extend_schema(
    tags=["grupos"],
    parameters=[
        OpenApiParameter("asignatura", int, OpenApiParameter.QUERY, required=True),
        OpenApiParameter("periodo", int, OpenApiParameter.QUERY, required=True),
        OpenApiParameter("turno", int, OpenApiParameter.QUERY, required=True),
    ],
    responses={200: SugerenciaGruposResponseSerializer},
)
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def grupos_sugerir_view(request):
    asig = int(request.query_params.get("asignatura"))
    per = int(request.query_params.get("periodo"))
    tur = int(request.query_params.get("turno"))

    pre_count = Preinscripcion.objects.filter(asignatura_id=asig, periodo_id=per, turno_id=tur).count()
    sugeridos = max(1, math.ceil(pre_count / 25)) if pre_count else 1

    turno = Turno.objects.get(pk=tur)
    prefix = _prefix_por_turno(turno.nombre)
    start_idx = _proximo_indice_existente(asig, per, prefix)
    codigos = [f"{prefix}{i}" for i in range(start_idx, start_idx + sugeridos)]

    data = {
        "asignatura": asig, "periodo": per, "turno": tur,
        "preinscritos": pre_count, "grupos_sugeridos": sugeridos,
        "codigos_sugeridos": codigos,
    }
    return Response(data)

@extend_schema(
    tags=["grupos"],
    request=GrupoSerializer,
    responses={201: GrupoSerializer},
    examples=[OpenApiExample("Crear grupo A1", value={
        "asignatura": 1, "periodo": 1, "turno": 1, "docente": 10,
        "codigo": "A1", "capacidad": 40, "estado": "borrador"
    })],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def grupos_create_view(request):
    ser = GrupoSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    obj = ser.save()
    return Response(GrupoSerializer(obj).data, status=201)

@extend_schema(tags=["grupos"], responses={200: GrupoSerializer(many=True)})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def grupos_list_view(request):
    qs = Grupo.objects.select_related("asignatura","periodo","turno","docente").all()
    asig = request.query_params.get("asignatura")
    per = request.query_params.get("periodo")
    tur = request.query_params.get("turno")
    if asig: qs = qs.filter(asignatura_id=asig)
    if per: qs = qs.filter(periodo_id=per)
    if tur: qs = qs.filter(turno_id=tur)
    qs = qs.order_by("asignatura_id","codigo")
    return Response(GrupoSerializer(qs, many=True).data)

@extend_schema(tags=["grupos"], request=GrupoSerializer, responses={200: GrupoSerializer})
@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def grupos_update_view(request, pk: int):
    try:
        obj = Grupo.objects.get(pk=pk)
    except Grupo.DoesNotExist:
        return Response({"detail":"No encontrado."}, status=404)
    ser = GrupoSerializer(instance=obj, data=request.data, partial=(request.method=="PATCH"))
    ser.is_valid(raise_exception=True)
    obj = ser.save()
    return Response(GrupoSerializer(obj).data)

@extend_schema(tags=["grupos"], responses={204: None})
@api_view(["DELETE"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def grupos_delete_view(request, pk: int):
    try:
        obj = Grupo.objects.get(pk=pk)
    except Grupo.DoesNotExist:
        return Response({"detail":"No encontrado."}, status=404)
    obj.delete()
    return Response(status=204)


@extend_schema(tags=["carreras"], responses={200: CarreraSerializer(many=True)})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def carreras_list_view(request):
    return Response(CarreraSerializer(Carrera.objects.all(), many=True).data)