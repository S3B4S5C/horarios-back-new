from django.db import models
from django.conf import settings


class Carrera(models.Model):
    sigla = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=160)
    # Jefe de carrera (usuario estándar con role=JEFE_CARRERA)
    jefe = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="carreras_dirigidas"
    )

    class Meta:
        verbose_name = "Carrera"
        verbose_name_plural = "Carreras"

    def __str__(self):
        return f"{self.sigla} - {self.nombre}"


class TipoAmbiente(models.Model):
    """Se deja aquí para que Asignatura pueda referenciarlo sin importar orden de apps."""
    nombre = models.CharField(max_length=80, unique=True)  # Aula, Lab, Auditorio...
    descripcion = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Tipo de Ambiente"
        verbose_name_plural = "Tipos de Ambiente"

    def __str__(self):
        return self.nombre


class Asignatura(models.Model):
    carrera = models.ForeignKey(Carrera, on_delete=models.CASCADE, related_name="asignaturas")
    codigo = models.CharField(max_length=30)
    nombre = models.CharField(max_length=180)
    horas_teoria_semana = models.PositiveSmallIntegerField(default=0)
    horas_practica_semana = models.PositiveSmallIntegerField(default=0)
    # Compatibilidad de ambientes (opcional)
    tipo_ambiente_teoria = models.ForeignKey(
        "academics.TipoAmbiente", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="asignaturas_teoria"
    )
    tipo_ambiente_practica = models.ForeignKey(
        "academics.TipoAmbiente", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="asignaturas_practica"
    )

    class Meta:
        verbose_name = "Asignatura"
        verbose_name_plural = "Asignaturas"
        constraints = [
            models.UniqueConstraint(fields=["carrera", "codigo"], name="asignatura_codigo_unico_por_carrera")
        ]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class Periodo(models.Model):
    gestion = models.PositiveIntegerField(help_text="Año, p.ej. 2025")
    numero = models.PositiveSmallIntegerField(help_text="1 o 2")
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()

    class Meta:
        verbose_name = "Periodo Académico"
        verbose_name_plural = "Periodos Académicos"
        constraints = [
            models.UniqueConstraint(fields=["gestion", "numero"], name="periodo_gestion_numero_unico")
        ]

    def __str__(self):
        return f"{self.gestion}/{self.numero}"


class Turno(models.Model):
    nombre = models.CharField(max_length=40, unique=True)  # Mañana / Tarde / Noche

    class Meta:
        verbose_name = "Turno"
        verbose_name_plural = "Turnos"

    def __str__(self):
        return self.nombre


class Grupo(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        CONFIRMADO = "confirmado", "Confirmado"
        CERRADO = "cerrado", "Cerrado"

    asignatura = models.ForeignKey(Asignatura, on_delete=models.CASCADE, related_name="grupos")
    periodo = models.ForeignKey(Periodo, on_delete=models.CASCADE, related_name="grupos")
    turno = models.ForeignKey(Turno, on_delete=models.PROTECT, related_name="grupos")
    docente = models.ForeignKey("users.Docente", on_delete=models.PROTECT, related_name="grupos", null = True, blank = True)
    codigo = models.CharField(max_length=10, null=True, blank=True)
    capacidad = models.PositiveIntegerField(default=40)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.BORRADOR)

    class Meta:
        verbose_name = "Grupo"
        verbose_name_plural = "Grupos"
        constraints = [
            models.UniqueConstraint(fields=["asignatura", "periodo", "codigo"], name="grupo_unico_por_asig_periodo_cod")
        ]
        indexes = [models.Index(fields=["periodo", "asignatura", "turno"])]

    def __str__(self):
        return f"{self.asignatura.codigo}-{self.codigo} ({self.periodo} · {self.turno})"


class Preinscripcion(models.Model):
    """
    Demanda previa por asignatura/turno antes de crear grupos efectivos.
    Sirve para aplicar la regla 1 grupo por cada 25 preinscritos.
    """
    periodo = models.ForeignKey(Periodo, on_delete=models.CASCADE, related_name="preinscripciones")
    asignatura = models.ForeignKey(Asignatura, on_delete=models.CASCADE, related_name="preinscripciones")
    turno = models.ForeignKey(Turno, on_delete=models.PROTECT, related_name="preinscripciones")
    estudiante = models.ForeignKey("users.Estudiante", on_delete=models.CASCADE, related_name="preinscripciones")
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Preinscripción"
        verbose_name_plural = "Preinscripciones"
        constraints = [
            models.UniqueConstraint(
                fields=["periodo", "asignatura", "turno", "estudiante"], name="preinscripcion_unica"
            )
        ]
        indexes = [models.Index(fields=["periodo", "asignatura", "turno"])]

    def __str__(self):
        return f"Pre-{self.estudiante} {self.asignatura.codigo} ({self.turno})"


class Inscripcion(models.Model):
    """Inscripción real del estudiante a un grupo confirmado."""
    grupo = models.ForeignKey(Grupo, on_delete=models.CASCADE, related_name="inscripciones")
    estudiante = models.ForeignKey("users.Estudiante", on_delete=models.CASCADE, related_name="inscripciones")
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Inscripción"
        verbose_name_plural = "Inscripciones"
        constraints = [
            models.UniqueConstraint(fields=["grupo", "estudiante"], name="inscripcion_unica")
        ]
        indexes = [models.Index(fields=["estudiante"]), models.Index(fields=["grupo"])]

    def __str__(self):
        return f"{self.estudiante} → {self.grupo}"
