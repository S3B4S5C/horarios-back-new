from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiExample

from users.permissions import IsManagerOrStaff
from .models import Periodo
from .serializers import PeriodoSerializer


class PeriodoViewSet(mixins.ListModelMixin,
                     mixins.RetrieveModelMixin,
                     viewsets.GenericViewSet):
    """
    ViewSet liviano con acciones personalizadas:
      - POST   /periodos/create/
      - PUT    /periodos/{id}/update/
      - PATCH  /periodos/{id}/update/
      - DELETE /periodos/{id}/delete/
    Listado soporta filtros ?gestion=&numero=
    """
    queryset = Periodo.objects.all().order_by("-gestion", "-numero")
    serializer_class = PeriodoSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["gestion", "numero"]
    search_fields = ["gestion", "numero"]
    ordering_fields = ["gestion", "numero", "fecha_inicio", "fecha_fin"]

    @extend_schema(
        methods=["POST"],
        request=PeriodoSerializer,
        responses={201: PeriodoSerializer},
        examples=[OpenApiExample("CrearPeriodo",
                                 value={"gestion": 2025, "numero": 1,
                                        "fecha_inicio": "2025-02-10",
                                        "fecha_fin": "2025-06-30"})],
        description="Crea un período académico (único por gestión y número).",
        tags=["periodos"],
    )
    @action(detail=False, methods=["post"], url_path="create",
            permission_classes=[IsAuthenticated, IsManagerOrStaff])
    def create_custom(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        return Response(self.get_serializer(obj).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        methods=["PUT", "PATCH"],
        request=PeriodoSerializer,
        responses={200: PeriodoSerializer},
        tags=["periodos"],
    )
    @action(detail=True, methods=["put", "patch"], url_path="update",
            permission_classes=[IsAuthenticated, IsManagerOrStaff])
    def update_custom(self, request, pk=None, *args, **kwargs):
        instance = self.get_object()
        partial = request.method.lower() == "patch"
        ser = self.get_serializer(instance, data=request.data, partial=partial)
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        return Response(self.get_serializer(obj).data)

    @extend_schema(
        methods=["DELETE"],
        responses={204: None},
        tags=["periodos"],
    )
    @action(detail=True, methods=["delete"], url_path="delete",
            permission_classes=[IsAuthenticated, IsManagerOrStaff])
    def delete_custom(self, request, pk=None, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
