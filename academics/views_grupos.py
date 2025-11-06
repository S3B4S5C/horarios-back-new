from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiParameter

# o ajusta al permiso que uses para gestión
from scheduling.models import Calendario
from users.permissions import IsManagerOrStaff
from academics.models import Grupo, Asignatura, Turno
from .serializers import GrupoSerializer, GrupoBulkCreateRequestSerializer, GrupoBulkItemSerializer


class GrupoViewSet(viewsets.ViewSet):
    """
    ViewSet liviano con acciones personalizadas para rutas /create, /bulk-create, /{id}/update, /{id}/delete.
    La lista soporta filtros ?asignatura= (id o código), ?asignatura_id=, ?turno= (nombre) o ?turno_id= y ?calendario=.
    """
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in {"create_one", "bulk_create", "update_one", "delete_one"}:
            return [IsAuthenticated(), IsManagerOrStaff()]
        return [IsAuthenticated()]

    @extend_schema(
        tags=["grupos"],
        parameters=[
            OpenApiParameter(
                name="asignatura", location=OpenApiParameter.QUERY,
                description="ID o código de asignatura", required=False, type=str
            ),
            OpenApiParameter(
                name="asignatura_id", location=OpenApiParameter.QUERY,
                description="ID de asignatura", required=False, type=int
            ),
            OpenApiParameter(
                name="turno", location=OpenApiParameter.QUERY,
                description="Nombre de turno (Mañana/Tarde/Noche)", required=False, type=str
            ),
            OpenApiParameter(
                name="turno_id", location=OpenApiParameter.QUERY,
                description="ID de turno", required=False, type=int
            ),
            OpenApiParameter(  # <-- NUEVO
                name="calendario", location=OpenApiParameter.QUERY,
                description="ID de calendario (filtra por su período)", required=False, type=int
            ),
        ],
        responses={200: GrupoSerializer(many=True)},
    )
    def list(self, request):
        qs = Grupo.objects.all().select_related("asignatura", "periodo", "turno", "docente")

        asignatura = request.query_params.get("asignatura")
        asignatura_id = request.query_params.get("asignatura_id")
        turno = request.query_params.get("turno")
        turno_id = request.query_params.get("turno_id")
        calendario = request.query_params.get("calendario")  # <-- NUEVO
        periodo = request.query_params.get("periodo")

        # -- filtros por asignatura --
        if asignatura_id:
            qs = qs.filter(asignatura_id=asignatura_id)
        elif asignatura:
            if asignatura.isdigit():
                qs = qs.filter(asignatura_id=int(asignatura))
            else:
                qs = qs.filter(asignatura__codigo__iexact=asignatura)

        # -- filtros por turno --
        if turno_id:
            qs = qs.filter(turno_id=turno_id)
        elif turno:
            qs = qs.filter(turno__nombre__iexact=turno)

        # -- filtro por calendario (por período del calendario) --
        if calendario:
            try:
                cal = Calendario.objects.only("periodo_id").get(pk=int(calendario))
            except (ValueError, Calendario.DoesNotExist):
                return Response({"detail": "calendario inválido."}, status=400)
            qs = qs.filter(periodo_id=cal.periodo_id)
        if periodo:
            qs = qs.filter(periodo_id=periodo)
            
        data = GrupoSerializer(qs.order_by("asignatura__codigo", "codigo"), many=True).data
        return Response(data)

    @extend_schema(
        tags=["grupos"],
        request=GrupoSerializer,
        responses={201: GrupoSerializer},
        examples=[
            OpenApiExample("Crear grupo (sin código explícito)", value={
                "asignatura": 1, "periodo": 1, "turno": 2, "docente": None, "capacidad": 35, "estado": "borrador"
            }),
        ],
    )
    @action(detail=False, methods=["post"], url_path="create")
    def create_one(self, request):
        ser = GrupoSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        return Response(GrupoSerializer(obj).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["grupos"],
        request=GrupoBulkCreateRequestSerializer,
        responses={201: GrupoSerializer(many=True)},
        examples=[
            OpenApiExample("Bulk create", value={
                "items": [
                    {"asignatura": 1, "periodo": 1, "turno": 1, "docente": 1,
                        "codigo": "A1", "capacidad": 35, "estado": "borrador"},
                    {"asignatura": 1, "periodo": 1, "turno": 1, "docente": 2,
                        "codigo": "A2", "capacidad": 35, "estado": "borrador"},
                ]
            }),
        ],
    )
    @action(detail=False, methods=["post"], url_path="bulk-create")
    def bulk_create(self, request):
        ser = GrupoBulkCreateRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        items = ser.validated_data["items"]
        created = []
        # validación previa de duplicados por (asignatura, periodo, codigo)
        combos = set()
        for it in items:
            asig_id = it["asignatura"].id if hasattr(
                it["asignatura"], "id") else it["asignatura"]
            per_id = it["periodo"].id if hasattr(
                it["periodo"], "id") else it["periodo"]
            cod = it.get("codigo")  # puede no venir
            if cod:
                key = (asig_id, per_id, cod)
                if key in combos:
                    return Response({"detail": f"Duplicado en payload (asignatura, periodo, codigo): {key}"}, status=400)
                combos.add(key)

        with transaction.atomic():
            for it in items:
                s = GrupoSerializer(data=it)
                s.is_valid(raise_exception=True)
                created.append(s.save())

        return Response(GrupoSerializer(created, many=True).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["grupos"],
        request=GrupoSerializer,
        responses={200: GrupoSerializer, 404: dict},
        examples=[
            OpenApiExample("Actualizar grupo", value={
                "asignatura": 1, "periodo": 1, "turno": 1, "docente": 2, "codigo": "A1", "capacidad": 40, "estado": "confirmado"
            }),
        ],
    )
    @action(detail=True, methods=["put", "patch"], url_path="update")
    def update_one(self, request, pk=None):
        try:
            obj = Grupo.objects.get(pk=pk)
        except Grupo.DoesNotExist:
            return Response({"detail": "No encontrado."}, status=404)
        partial = request.method.lower() == "patch"
        ser = GrupoSerializer(instance=obj, data=request.data, partial=partial)
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        return Response(GrupoSerializer(obj).data)

    @extend_schema(
        tags=["grupos"],
        responses={204: None, 404: dict},
    )
    @action(detail=True, methods=["delete"], url_path="delete")
    def delete_one(self, request, pk=None):
        try:
            obj = Grupo.objects.get(pk=pk)
        except Grupo.DoesNotExist:
            return Response({"detail": "No encontrado."}, status=404)
        obj.delete()
        return Response(status=204)
