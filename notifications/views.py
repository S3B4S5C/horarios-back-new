from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter

from notifications.models import Notificacion
from .serializers import NotificacionModelSerializer

@extend_schema(
    tags=["notificaciones"],
    parameters=[OpenApiParameter("unread", bool, OpenApiParameter.QUERY)],
    responses={200: NotificacionModelSerializer(many=True)}
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def notificaciones_list_view(request):
    qs = Notificacion.objects.filter(usuario=request.user).order_by("-creada_en")
    unread = request.query_params.get("unread")
    if unread in {"true","false"}:
        qs = qs.filter(leida=(unread!="true"))
    return Response(NotificacionModelSerializer(qs, many=True).data)

@extend_schema(tags=["notificaciones"], responses={200: NotificacionModelSerializer})
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def notificaciones_marcar_leida_view(request, pk: int):
    try:
        n = Notificacion.objects.get(pk=pk, usuario=request.user)
    except Notificacion.DoesNotExist:
        return Response({"detail":"No encontrada."}, status=404)
    n.leida = True
    n.save(update_fields=["leida"])
    return Response(NotificacionModelSerializer(n).data)
