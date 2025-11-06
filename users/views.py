from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiExample
from horarios import settings
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import (
    RegisterSerializer, LoginSerializer, User, UserSerializer, AuthResponseSerializer,
    AssignRoleSerializer, DocenteSerializer, DocenteCreateUpdateSerializer
)
from .permissions import IsManagerOrStaff
from users.models import Docente

def _tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


@extend_schema(
    tags=["auth"],
    request=RegisterSerializer,
    responses={201: AuthResponseSerializer},
    examples=[
        OpenApiExample(
            "Registro docente",
            value={
                "username": "doc1",
                "email": "doc1@uni.edu",
                "password": "Secreta123",
                "role": "DOCENTE",
                "nombre_completo": "Dra. Ana Pérez",
                "especialidad": "Bioquímica Clínica"
            },
        ),
        OpenApiExample(
            "Registro estudiante",
            value={
                "username": "est1",
                "email": "est1@uni.edu",
                "password": "Secreta123",
                "role": "ESTUDIANTE",
                "nombre_completo": "Luis Flores",
                "matricula": "2025-0001"
            },
        ),
    ],
)
@api_view(["POST"])
@permission_classes([AllowAny])
def register_view(request):
    """
    Crea un usuario, asigna **rol único** en UserProfile y,
    si el rol es DOCENTE/ESTUDIANTE, crea su perfil específico.
    Retorna tokens (JWT) y el usuario completo.
    """
    ser = RegisterSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    user = ser.save()
    data = {
        "user": UserSerializer(user).data,
        "tokens": _tokens_for_user(user),
    }
    return Response(data, status=status.HTTP_201_CREATED)


def _lock_key(identifier): return f"auth:lock:{identifier}"
def _fail_key(identifier): return f"auth:fail:{identifier}"

@extend_schema(
    tags=["auth"],
    request=LoginSerializer,
    responses={
        200: AuthResponseSerializer,
        401: {"type": "object", "properties": {"detail": {"type": "string"}, "intentos_restantes": {"type": "integer"}}},
        423: {"type": "object", "properties": {"detail": {"type": "string"}}},
    },
    examples=[
        OpenApiExample("Login con username", value={"username": "doc1", "password": "Secreta123"}),
        OpenApiExample("Login con email", value={"email": "doc1@uni.edu", "password": "Secreta123"}),
        OpenApiExample("Cuenta/IP bloqueada (423)", response_only=True, value={"detail": "Cuenta/IP bloqueada 15 min."}),
        OpenApiExample("Credenciales inválidas (401)", response_only=True, value={"detail": "Credenciales inválidas.", "intentos_restantes": 3}),
    ],
)
@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    """
    Autentica con **username** o **email** y retorna tokens (JWT)
    + el usuario autenticado con todos sus datos (profile, docente/estudiante).

    Seguridad:
    - Bloqueo temporal por múltiples intentos fallidos (423 Locked).
    - Contador de fallos por identificador de login (username/email) o IP como fallback.
    """
    identifier = request.data.get("username") or request.data.get("email") or request.META.get("REMOTE_ADDR")

    # ¿Bloqueado actualmente?
    if cache.get(_lock_key(identifier)):
        return Response({"detail": f"Cuenta/IP bloqueada {settings.LOCKOUT_MINUTES} min."}, status=423)

    ser = LoginSerializer(data=request.data)
    if not ser.is_valid():
        # incrementar fallos
        fails = cache.get(_fail_key(identifier), 0) + 1
        cache.set(_fail_key(identifier), fails, settings.LOCKOUT_MINUTES * 60)
        # ¿alcanzó el límite? → bloquear
        if fails >= settings.MAX_FAILED_ATTEMPTS:
            cache.set(_lock_key(identifier), True, settings.LOCKOUT_MINUTES * 60)
            return Response({"detail": f"Cuenta/IP bloqueada {settings.LOCKOUT_MINUTES} min."}, status=423)
        # aún no bloqueado → 401 con intentos restantes
        return Response(
            {"detail": "Credenciales inválidas.", "intentos_restantes": settings.MAX_FAILED_ATTEMPTS - fails},
            status=401,
        )

    # éxito: limpiar contadores/bloqueo
    cache.delete(_fail_key(identifier))
    cache.delete(_lock_key(identifier))

    user = ser.validated_data["user"]
    data = {
        "user": UserSerializer(user).data,
        "tokens": _tokens_for_user(user),
    }
    return Response(data, status=status.HTTP_200_OK)

# ===== HU002: asignación de rol único =====
@extend_schema(
    tags=["users"],
    request=AssignRoleSerializer,
    responses={200: UserSerializer},
    examples=[OpenApiExample("Asignar DOCENTE", value={"user_id": 10, "role": "DOCENTE"})],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def assign_role_view(request):
    ser = AssignRoleSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    user = ser.save()
    return Response(UserSerializer(user).data)


# ===== HU003: CRUD Docentes =====
@extend_schema(tags=["docentes"], responses={200: DocenteSerializer(many=True)})
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def docentes_list_view(request):
    qs = Docente.objects.all().order_by("nombre_completo")
    activo = request.query_params.get("activo")
    if activo in {"true", "false"}:
        qs = qs.filter(activo=(activo == "true"))
    return Response(DocenteSerializer(qs, many=True).data)

@extend_schema(
    tags=["docentes"],
    request=DocenteCreateUpdateSerializer,
    responses={201: DocenteSerializer},
    examples=[OpenApiExample("Crear docente existente", value={
        "user": 12, "nombre_completo": "Dra. Ana Pérez", "especialidad":"Bioquímica Clínica",
        "carga_min_semanal": 6, "carga_max_semanal": 12, "activo": True
    })],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def docentes_create_view(request):
    ser = DocenteCreateUpdateSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    obj = ser.save()
    return Response(DocenteSerializer(obj).data, status=201)

@extend_schema(
    tags=["docentes"],
    request=DocenteCreateUpdateSerializer,
    responses={200: DocenteSerializer},
)
@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def docentes_update_view(request, pk: int):
    try:
        obj = Docente.objects.get(pk=pk)
    except Docente.DoesNotExist:
        return Response({"detail": "No encontrado."}, status=404)
    ser = DocenteCreateUpdateSerializer(instance=obj, data=request.data, partial=(request.method == "PATCH"))
    ser.is_valid(raise_exception=True)
    obj = ser.save()
    return Response(DocenteSerializer(obj).data)

@extend_schema(tags=["docentes"], responses={204: None})
@api_view(["DELETE"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def docentes_delete_view(request, pk: int):
    try:
        obj = Docente.objects.get(pk=pk)
    except Docente.DoesNotExist:
        return Response({"detail": "No encontrado."}, status=404)
    obj.delete()
    return Response(status=204)


# ===== HU005: Menú contextual por rol =====
DEFAULT_MENU_BY_ROLE = {
    "VICERRECTORADO": ["periodos", "demanda", "planta", "reportes"],
    "RECTOR": ["reportes"],
    "JEFE_CARRERA": ["docentes", "asignaturas", "grupos", "horario", "conflictos", "reportes"],
    "DOCENTE": ["mi_horario", "disponibilidad", "notificaciones"],
    "ESTUDIANTE": ["mi_horario", "inscripciones", "notificaciones"],
}

@extend_schema(tags=["users"], responses={200: dict})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_menu_view(request):
    profile = getattr(request.user, "profile", None)
    role = getattr(profile, "role", None)
    # si guardaste permisos JSON por usuario, los fusionas aquí
    menu = DEFAULT_MENU_BY_ROLE.get(role, [])
    user_perms = getattr(profile, "permisos", {}) if profile else {}
    return Response({"role": role, "menu": menu, "permisos": user_perms})


@extend_schema(tags=["users"], responses={200: dict})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_all_users_view(request):
    return Response(UserSerializer(User.objects.all(), many=True).data)