from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiExample

from users.permissions import IsManagerOrStaff
from .models import Calendario
from .serializers import CalendarioSerializer


class CalendarioViewSet(mixins.ListModelMixin,
                        mixins.RetrieveModelMixin,
                        viewsets.GenericViewSet):
    """
    ViewSet liviano con acciones personalizadas:
      - POST   /calendarios/create/
      - PUT    /calendarios/{id}/update/
      - PATCH  /calendarios/{id}/update/
      - DELETE /calendarios/{id}/delete/
    Listado soporta filtros ?periodo= (id exacto) y búsqueda por nombre (?search=)
    """
    queryset = Calendario.objects.select_related("periodo").all().order_by("-id")
    serializer_class = CalendarioSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["periodo"]
    search_fields = ["nombre"]
    ordering_fields = ["id", "nombre", "duracion_bloque_min", "periodo"]

    @extend_schema(
        methods=["POST"],
        request=CalendarioSerializer,
        responses={201: CalendarioSerializer},
        examples=[OpenApiExample("CrearCalendario",
                                 value={"periodo": 1, "nombre": "Semestral",
                                        "duracion_bloque_min": 45})],
        tags=["calendarios"],
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
        request=CalendarioSerializer,
        responses={200: CalendarioSerializer},
        tags=["calendarios"],
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
        tags=["calendarios"],
    )
    @action(detail=True, methods=["delete"], url_path="delete",
            permission_classes=[IsAuthenticated, IsManagerOrStaff])
    def delete_custom(self, request, pk=None, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
