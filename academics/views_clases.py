import calendar
from typing import List, Dict, Any

from django.db import transaction, IntegrityError
from django.db.models import Sum, F, Case, When, IntegerField
from django.db.models.functions import Coalesce
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
# from rest_framework.permissions import IsAuthenticated

from drf_spectacular.utils import (
    extend_schema, OpenApiParameter, OpenApiTypes, OpenApiResponse
)

from academics.models import Grupo
from scheduling.models import Calendario, Clase
from .clases_serializers import (
    GrupoPlanificacionSerializer,
    ClaseDetailSerializer,
    ClaseWithLabelsSerializer,
    ClaseBulkCreateRequestSerializer,
    ClaseBulkUpdateRequestSerializer,
    ClaseBulkDeleteRequestSerializer,
    BulkCreateResponseSerializer,
    BulkUpdateResponseSerializer,
    BulkDeleteResponseSerializer,
)


class GrupoPlanificacionListAPIView(APIView):
    # permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        periodo = request.query_params.get("periodo")
        asignatura = request.query_params.get("asignatura")
        turno = request.query_params.get("turno")
        calendario = request.query_params.get("calendario")
        tolerancia_min = int(request.query_params.get("tolerancia_min") or 0)

        qs = Grupo.objects.select_related("asignatura", "periodo", "turno").all()

        # Filtros opcionales (id o código/nombre)
        if periodo:
            qs = qs.filter(periodo_id=periodo)

        if asignatura:
            if asignatura.isdigit():
                qs = qs.filter(asignatura_id=int(asignatura))
            else:
                qs = qs.filter(asignatura__codigo=str(asignatura))

        if turno:
            if turno.isdigit():
                qs = qs.filter(turno_id=int(turno))
            else:
                qs = qs.filter(turno__nombre__iexact=str(turno))

        if calendario:
            try:
                cal = Calendario.objects.only("periodo_id").get(pk=int(calendario))
            except (ValueError, Calendario.DoesNotExist):
                return Response({"detail": "calendario inválido."}, status=400)
            qs = qs.filter(periodo_id=cal.periodo_id)


        # Filtros adicionales
        if tolerancia_min:
            qs = qs.filter(clases__bloque_inicio__duracion_min__gte=tolerancia_min)

        # Agregaciones por tipo T/P
        # minutos = sum(bloques_duracion * bloque_inicio.duracion_min)
        minutos_expr = F("clases__bloque_inicio__duracion_min") * F("clases__bloques_duracion")

        qs = qs.annotate(
            bloques_teo=Coalesce(Sum(Case(
                When(clases__tipo="T", then=F("clases__bloques_duracion")),
                default=0, output_field=IntegerField()
            )), 0),
            bloques_pra=Coalesce(Sum(Case(
                When(clases__tipo="P", then=F("clases__bloques_duracion")),
                default=0, output_field=IntegerField()
            )), 0),
            minutos_teo=Coalesce(Sum(Case(
                When(clases__tipo="T", then=minutos_expr),
                default=0, output_field=IntegerField()
            )), 0),
            minutos_pra=Coalesce(Sum(Case(
                When(clases__tipo="P", then=minutos_expr),
                default=0, output_field=IntegerField()
            )), 0),
        )

        # Construcción de objetos ligeros para serializer
        payload = []
        for g in qs:
            payload.append(type("GRow", (), {
                "id": g.id,
                "codigo": g.codigo,
                "periodo_id": g.periodo_id,
                "turno_id": g.turno_id,
                "asignatura": g.asignatura,
                "minutos_teo": g.minutos_teo,
                "minutos_pra": g.minutos_pra,
                "bloques_teo": g.bloques_teo,
                "bloques_pra": g.bloques_pra,
            })())

        # Serializar
        serializer_input = []
        for row in payload:
            serializer_input.append({
                "grupo": row.id,
                "codigo": row.codigo,
                "periodo": row.periodo_id,
                "turno": row.turno_id,
                "asignatura": {
                    "id": row.asignatura.id,
                    "codigo": row.asignatura.codigo,
                    "nombre": row.asignatura.nombre,
                },
                "minutos_teo": row.minutos_teo,
                "minutos_pra": row.minutos_pra,
                "bloques_teo": row.bloques_teo,
                "bloques_pra": row.bloques_pra,
            })

        from types import SimpleNamespace
        rows = [SimpleNamespace(**d) for d in serializer_input]

        ser = GrupoPlanificacionSerializer(
            rows, many=True, context={"tolerancia_min": tolerancia_min}
        )
        return Response(ser.data, status=status.HTTP_200_OK)


class ClasesDeGrupoListAPIView(APIView):
    """
    Lista todas las clases de un grupo dado. Con `expand=labels` incluye metadatos legibles.
    """
    # permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Clases de un grupo",
        description=(
            "Retorna el listado de clases del grupo `id`. "
            "Si se pasa `expand=labels`, cada clase incluye un objeto `labels` con "
            "`asignatura`, `grupo`, `docente`, `ambiente`, `bloque_inicio_orden` y `rango_hora`."
        ),
        parameters=[
            OpenApiParameter(name="id", type=OpenApiTypes.INT, location=OpenApiParameter.PATH,
                             description="ID del grupo"),
            OpenApiParameter(name="expand", type=OpenApiTypes.STR, required=False,
                             description="Usar `labels` para incluir metadatos legibles (labels)"),
        ],
        responses={
            200: OpenApiResponse(response=ClaseDetailSerializer(many=True),
                                 description="Listado de clases (sin labels). "
                                             "Con `expand=labels` se devuelven también labels."),
        },
        tags=["Scheduling"],
        operation_id="clases_de_grupo_list",
    )
    def get(self, request, id: int, *args, **kwargs):
        expand = request.query_params.get("expand")
        qs = (
            Clase.objects.filter(grupo_id=id)
            .select_related("grupo__asignatura", "bloque_inicio", "ambiente", "docente")
            .order_by("day_of_week", "bloque_inicio__orden")
        )
        if expand == "labels":
            ser = ClaseWithLabelsSerializer(qs, many=True)
        else:
            ser = ClaseDetailSerializer(qs, many=True)
        return Response(ser.data, status=status.HTTP_200_OK)


class ClasesBulkCreateAPIView(APIView):
    """
    Crea múltiples clases en bloque. **`docente` es opcional** (se admite omitir o `null`).
    """
    # permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Creación masiva de clases",
        description=(
            "Crea varias clases en una sola operación. "
            "Respeta la restricción única (grupo, day_of_week, bloque_inicio). "
            "**Campo `docente` es opcional** y puede omitirse si el grupo no tiene docente."
        ),
        request=ClaseBulkCreateRequestSerializer,
        responses={
            201: BulkCreateResponseSerializer,
            409: OpenApiResponse(response=BulkCreateResponseSerializer,
                                 description="Ninguna clase creada. Conflictos/errores reportados."),
        },
        tags=["Scheduling"],
        operation_id="clases_bulk_create",
    )
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        ser = ClaseBulkCreateRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        items = ser.validated_data["items"]

        created_objs = []
        conflicts = []

        for idx, data in enumerate(items):
            try:
                obj = Clase.objects.create(**data)
                created_objs.append(obj)
            except IntegrityError as e:
                conflicts.append({"index": idx, "detail": str(e), "data": data})

        resp = {
            "created": len(created_objs),
            "items": ClaseDetailSerializer(created_objs, many=True).data,
            "conflicts": conflicts,
        }

        if len(created_objs) == 0 and conflicts:
            return Response(resp, status=status.HTTP_409_CONFLICT)
        return Response(resp, status=status.HTTP_201_CREATED)


class ClasesBulkUpdateAPIView(APIView):
    """
    Actualiza múltiples clases en bloque (parcial, vía `updates[].set`).
    """
    # permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Actualización masiva de clases",
        request=ClaseBulkUpdateRequestSerializer,
        responses={
            200: BulkUpdateResponseSerializer,
            409: OpenApiResponse(response=BulkUpdateResponseSerializer,
                                 description="Ninguna clase actualizada. Errores reportados."),
        },
        tags=["Scheduling"],
        operation_id="clases_bulk_update",
    )
    @transaction.atomic
    def put(self, request, *args, **kwargs):
        ser = ClaseBulkUpdateRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        updates: List[Dict[str, Any]] = ser.validated_data["updates"]

        updated = []
        errors = []

        for up in updates:
            cid = up["id"]
            fields = up["set"]
            try:
                obj = Clase.objects.select_for_update().get(id=cid)
            except Clase.DoesNotExist:
                errors.append({"id": cid, "detail": "Clase no encontrada"})
                continue

            for k, v in fields.items():
                setattr(obj, k, v)

            try:
                obj.save()
                updated.append(obj)
            except IntegrityError as e:
                errors.append({"id": cid, "detail": str(e)})

        resp = {
            "updated": len(updated),
            "items": ClaseDetailSerializer(updated, many=True).data,
            "errors": errors,
        }

        if len(updated) == 0 and errors:
            return Response(resp, status=status.HTTP_409_CONFLICT)
        return Response(resp, status=status.HTTP_200_OK)


class ClasesBulkDeleteAPIView(APIView):
    """
    Elimina múltiples clases en bloque.
    """
    # permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Eliminación masiva de clases",
        request=ClaseBulkDeleteRequestSerializer,
        responses={200: BulkDeleteResponseSerializer},
        tags=["Scheduling"],
        operation_id="clases_bulk_delete",
    )
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        ser = ClaseBulkDeleteRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ids: List[int] = ser.validated_data["ids"]

        existing_ids = set(Clase.objects.filter(id__in=ids).values_list("id", flat=True))
        not_found = [i for i in ids if i not in existing_ids]

        deleted_count, _ = Clase.objects.filter(id__in=existing_ids).delete()

        resp = {"deleted": deleted_count, "not_found": not_found}
        return Response(resp, status=status.HTTP_200_OK)
