from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from users.models import UserProfile
from scheduling.serializers import PrefsSerializer  # reutilizamos

@extend_schema(tags=["users"], request=PrefsSerializer, responses={200: PrefsSerializer})
@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def notifications_prefs_view(request):
    ser = PrefsSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    profile = request.user.profile
    perms = dict(profile.permisos or {})
    perms["notifications"] = ser.validated_data
    profile.permisos = perms
    profile.save(update_fields=["permisos"])
    return Response(perms["notifications"])
