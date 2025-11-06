from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiExample
from users.permissions import IsManagerOrStaff
from facilities.models import Edificio, TipoAmbiente, Ambiente
from facilities.serializers import EdificioSerializer, TipoAmbienteSerializer, AmbienteSerializer

# ---- HU006: Edificios ----
@extend_schema(tags=["edificios"], responses={200: EdificioSerializer(many=True)})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def edificios_list_view(request):
    qs = Edificio.objects.all().order_by("codigo")
    return Response(EdificioSerializer(qs, many=True).data)

@extend_schema(
    tags=["edificios"], request=EdificioSerializer, responses={201: EdificioSerializer},
    examples=[OpenApiExample("Crear edificio", value={"codigo":"ED-A","nombre":"Bloque A","ubicacion":"Campus Norte"})],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def edificios_create_view(request):
    ser = EdificioSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    obj = ser.save()
    return Response(EdificioSerializer(obj).data, status=201)

@extend_schema(tags=["edificios"], responses={200: EdificioSerializer})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def edificios_detail_view(request, pk: int):
    try:
        obj = Edificio.objects.get(pk=pk)
    except Edificio.DoesNotExist:
        return Response({"detail": "No encontrado."}, status=404)
    return Response(EdificioSerializer(obj).data)

@extend_schema(tags=["edificios"], request=EdificioSerializer, responses={200: EdificioSerializer})
@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def edificios_update_view(request, pk: int):
    try:
        obj = Edificio.objects.get(pk=pk)
    except Edificio.DoesNotExist:
        return Response({"detail": "No encontrado."}, status=404)
    ser = EdificioSerializer(instance=obj, data=request.data, partial=(request.method=="PATCH"))
    ser.is_valid(raise_exception=True)
    obj = ser.save()
    return Response(EdificioSerializer(obj).data)

@extend_schema(tags=["edificios"], responses={204: None})
@api_view(["DELETE"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def edificios_delete_view(request, pk: int):
    try:
        obj = Edificio.objects.get(pk=pk)
    except Edificio.DoesNotExist:
        return Response({"detail": "No encontrado."}, status=404)
    obj.delete()
    return Response(status=204)

# ---- HU007: TipoAmbiente y Ambientes ----
@extend_schema(tags=["tipos-ambiente"], responses={200: TipoAmbienteSerializer(many=True)})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def tipos_ambiente_list_view(request):
    qs = TipoAmbiente.objects.all().order_by("nombre")
    return Response(TipoAmbienteSerializer(qs, many=True).data)

@extend_schema(tags=["tipos-ambiente"], request=TipoAmbienteSerializer, responses={201: TipoAmbienteSerializer})
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def tipos_ambiente_create_view(request):
    ser = TipoAmbienteSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    obj = ser.save()
    return Response(TipoAmbienteSerializer(obj).data, status=201)

@extend_schema(tags=["tipos-ambiente"], request=TipoAmbienteSerializer, responses={200: TipoAmbienteSerializer})
@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def tipos_ambiente_update_view(request, pk: int):
    try:
        obj = TipoAmbiente.objects.get(pk=pk)
    except TipoAmbiente.DoesNotExist:
        return Response({"detail": "No encontrado."}, status=404)
    ser = TipoAmbienteSerializer(instance=obj, data=request.data, partial=(request.method=="PATCH"))
    ser.is_valid(raise_exception=True)
    obj = ser.save()
    return Response(TipoAmbienteSerializer(obj).data)

@extend_schema(tags=["tipos-ambiente"], responses={204: None})
@api_view(["DELETE"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def tipos_ambiente_delete_view(request, pk: int):
    try:
        obj = TipoAmbiente.objects.get(pk=pk)
    except TipoAmbiente.DoesNotExist:
        return Response({"detail": "No encontrado."}, status=404)
    obj.delete()
    return Response(status=204)

@extend_schema(tags=["ambientes"], responses={200: AmbienteSerializer(many=True)})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ambientes_list_view(request):
    qs = Ambiente.objects.select_related("edificio","tipo_ambiente").all().order_by("edificio__codigo","codigo")
    edificio_id = request.query_params.get("edificio")
    tipo_id = request.query_params.get("tipo")
    if edificio_id: qs = qs.filter(edificio_id=edificio_id)
    if tipo_id: qs = qs.filter(tipo_ambiente_id=tipo_id)
    return Response(AmbienteSerializer(qs, many=True).data)

@extend_schema(tags=["ambientes"], request=AmbienteSerializer, responses={201: AmbienteSerializer})
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def ambientes_create_view(request):
    ser = AmbienteSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    obj = ser.save()
    return Response(AmbienteSerializer(obj).data, status=201)

@extend_schema(tags=["ambientes"], request=AmbienteSerializer, responses={200: AmbienteSerializer})
@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def ambientes_update_view(request, pk: int):
    try:
        obj = Ambiente.objects.get(pk=pk)
    except Ambiente.DoesNotExist:
        return Response({"detail": "No encontrado."}, status=404)
    ser = AmbienteSerializer(instance=obj, data=request.data, partial=(request.method=="PATCH"))
    ser.is_valid(raise_exception=True)
    obj = ser.save()
    return Response(AmbienteSerializer(obj).data)

@extend_schema(tags=["ambientes"], responses={204: None})
@api_view(["DELETE"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def ambientes_delete_view(request, pk: int):
    try:
        obj = Ambiente.objects.get(pk=pk)
    except Ambiente.DoesNotExist:
        return Response({"detail": "No encontrado."}, status=404)
    obj.delete()
    return Response(status=204)
