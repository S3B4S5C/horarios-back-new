from django.contrib.auth import get_user_model, authenticate
from rest_framework import serializers
from users.models import UserProfile, Docente, Estudiante

User = get_user_model()


# ===== NESTED =====

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ["role", "permisos"]


class DocenteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Docente
        fields = ["id", "user","nombre_completo", "especialidad", "carga_min_semanal", "carga_max_semanal", "activo"]


class EstudianteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Estudiante
        fields = ["id", "nombre_completo", "matricula"]


class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    docente = DocenteSerializer(read_only=True)
    estudiante = EstudianteSerializer(read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "date_joined",
                  "is_active", "profile", "docente", "estudiante"]


# ===== AUTH I/O =====

class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


class AuthResponseSerializer(serializers.Serializer):
    user = UserSerializer()
    tokens = TokenPairSerializer()


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField()
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=6)
    role = serializers.ChoiceField(choices=[c[0] for c in UserProfile._meta.get_field("role").choices])

    # datos opcionales por rol
    nombre_completo = serializers.CharField(required=False, allow_blank=True)
    especialidad = serializers.CharField(required=False, allow_blank=True)  # si DOCENTE
    matricula = serializers.CharField(required=False, allow_blank=True)     # si ESTUDIANTE

    def validate(self, attrs):
        if User.objects.filter(username=attrs["username"]).exists():
            raise serializers.ValidationError({"username": "Ya está en uso."})
        if User.objects.filter(email=attrs["email"]).exists():
            raise serializers.ValidationError({"email": "Ya está en uso."})
        return attrs

    def create(self, data):
        role = data.pop("role")
        nombre_completo = data.pop("nombre_completo", "").strip()
        especialidad = data.pop("especialidad", "").strip()
        matricula = data.pop("matricula", "").strip()

        password = data.pop("password")
        user = User.objects.create(**data)
        user.set_password(password)
        user.save()

        UserProfile.objects.create(user=user, role=role)

        if role == "DOCENTE":
            Docente.objects.create(
                user=user,
                nombre_completo=nombre_completo or user.get_full_name() or user.username,
                especialidad=especialidad,
            )
        elif role == "ESTUDIANTE":
            Estudiante.objects.create(
                user=user,
                nombre_completo=nombre_completo or user.get_full_name() or user.username,
                matricula=matricula or f"MAT-{user.id}",
            )
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        username = attrs.get("username")
        email = attrs.get("email")
        password = attrs["password"]

        user = None
        if username:
            user = authenticate(username=username, password=password)
        elif email:
            try:
                u = User.objects.get(email=email)
                user = authenticate(username=u.username, password=password)
            except User.DoesNotExist:
                user = None

        if user is None:
            raise serializers.ValidationError("Credenciales inválidas.")
        if not user.is_active:
            raise serializers.ValidationError("Usuario inactivo.")
        attrs["user"] = user
        return attrs


# ===== HU002: asignación de rol único =====

class AssignRoleSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    role = serializers.ChoiceField(choices=[c[0] for c in UserProfile._meta.get_field("role").choices])
    permisos = serializers.DictField(required=False)  # opcional, menú por rol para este usuario

    def validate(self, attrs):
        try:
            user = User.objects.get(pk=attrs["user_id"])
        except User.DoesNotExist:
            raise serializers.ValidationError({"user_id": "Usuario no encontrado."})
        attrs["user_obj"] = user
        return attrs

    def save(self, **kwargs):
        user = self.validated_data["user_obj"]
        role = self.validated_data["role"]
        permisos = self.validated_data.get("permisos", None)

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = role
        if permisos is not None:
            profile.permisos = permisos
        profile.save()
        return user


# ===== HU003: CRUD Docente =====

class DocenteCreateUpdateSerializer(serializers.ModelSerializer):
    """Para create/update (validaciones estrictas)."""
    class Meta:
        model = Docente
        fields = ["id", "user", "nombre_completo", "especialidad", "carga_min_semanal", "carga_max_semanal", "activo"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        minc = attrs.get("carga_min_semanal", getattr(self.instance, "carga_min_semanal", 0))
        maxc = attrs.get("carga_max_semanal", getattr(self.instance, "carga_max_semanal", 0))
        if maxc < minc:
            raise serializers.ValidationError("La carga máxima no puede ser menor a la mínima.")
        # Garantiza que el user tenga rol DOCENTE
        user = attrs.get("user", getattr(self.instance, "user", None))
        if user:
            profile = getattr(user, "profile", None)
            if not profile or profile.role != "DOCENTE":
                raise serializers.ValidationError("El usuario asociado debe tener rol DOCENTE.")
        return attrs
