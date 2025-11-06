from django.db import models
from django.conf import settings


class UserRole(models.TextChoices):
    JEFE_CARRERA   = "JEFE_CARRERA", "Jefe de Carrera"
    VICERRECTORADO = "VICERRECTORADO", "Vicerrectorado"
    RECTOR         = "RECTOR", "Rector"
    DOCENTE        = "DOCENTE", "Docente"
    ESTUDIANTE     = "ESTUDIANTE", "Estudiante"


class UserProfile(models.Model):
    """
    Perfil 1:1 del User estándar de Django con rol ÚNICO.
    Permite guardar, si quieres, un JSON simple para menú por rol.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.ESTUDIANTE)
    permisos = models.JSONField(default=dict, blank=True)  # opcional para menú

    class Meta:
        verbose_name = "Perfil de Usuario"
        verbose_name_plural = "Perfiles de Usuario"
        indexes = [models.Index(fields=["role"])]

    def __str__(self):
        return f"{self.user.username} · {self.role}"


class Docente(models.Model):
    """Datos propios del docente (usado para disponibilidad y carga)."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="docente"
    )
    nombre_completo = models.CharField(max_length=180)
    especialidad = models.CharField(max_length=120, blank=True)
    carga_min_semanal = models.PositiveSmallIntegerField(default=0)
    carga_max_semanal = models.PositiveSmallIntegerField(default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Docente"
        verbose_name_plural = "Docentes"
        constraints = [
            models.CheckConstraint(
                name="docente_carga_max_ge_min",
                check=models.Q(carga_max_semanal__gte=models.F("carga_min_semanal")),
            )
        ]

    def __str__(self):
        return self.nombre_completo


class Estudiante(models.Model):
    """Datos propios del estudiante."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="estudiante"
    )
    nombre_completo = models.CharField(max_length=180)
    matricula = models.CharField(max_length=30, unique=True)

    class Meta:
        verbose_name = "Estudiante"
        verbose_name_plural = "Estudiantes"
        indexes = [models.Index(fields=["matricula"])]

    def __str__(self):
        return f"{self.nombre_completo} · {self.matricula}"
