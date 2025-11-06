from django.db import models
from django.utils import timezone


class Calendario(models.Model):
    """
    Calendario por periodo con bloques; duracion_bloque_min suele ser 45 (horas académicas).
    """

    periodo = models.ForeignKey(
        "academics.Periodo", on_delete=models.CASCADE, related_name="calendarios"
    )
    nombre = models.CharField(max_length=80, default="Calendario")
    duracion_bloque_min = models.PositiveSmallIntegerField(default=45)

    class Meta:
        verbose_name = "Calendario"
        verbose_name_plural = "Calendarios"

    def __str__(self):
        return f"{self.nombre} · {self.periodo}"


class Bloque(models.Model):
    calendario = models.ForeignKey(
        Calendario, on_delete=models.CASCADE, related_name="bloques"
    )
    orden = models.PositiveSmallIntegerField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    duracion_min = models.PositiveSmallIntegerField()

    class Meta:
        verbose_name = "Bloque"
        verbose_name_plural = "Bloques"
        constraints = [
            models.UniqueConstraint(
                fields=["calendario", "orden"], name="bloque_orden_unico_por_calendario"
            )
        ]
        ordering = ("calendario", "orden")
        indexes = [models.Index(fields=["calendario", "orden"])]

    def __str__(self):
        return f"{self.calendario} · #{self.orden} ({self.hora_inicio}-{self.hora_fin})"


class DiaSemana(models.IntegerChoices):
    LUNES = 1, "Lunes"
    MARTES = 2, "Martes"
    MIERCOLES = 3, "Miércoles"
    JUEVES = 4, "Jueves"
    VIERNES = 5, "Viernes"
    SABADO = 6, "Sábado"
    DOMINGO = 7, "Domingo"


class DisponibilidadDocente(models.Model):
    """
    Disponibilidad por docente, día y bloque de un calendario (periodo específico).
    """

    docente = models.ForeignKey(
        "users.Docente", on_delete=models.CASCADE, related_name="disponibilidades"
    )
    calendario = models.ForeignKey(
        Calendario, on_delete=models.CASCADE, related_name="disponibilidades_docente"
    )
    day_of_week = models.PositiveSmallIntegerField(choices=DiaSemana.choices)
    bloque_inicio = models.ForeignKey(
        Bloque, on_delete=models.PROTECT, related_name="disponibilidades_inicio"
    )
    bloques_duracion = models.PositiveSmallIntegerField(default=1)
    preferencia = models.IntegerField(default=0)  # peso para tu optimizador

    class Meta:
        verbose_name = "Disponibilidad Docente"
        verbose_name_plural = "Disponibilidades Docentes"
        constraints = [
            models.UniqueConstraint(
                fields=["docente", "calendario", "day_of_week", "bloque_inicio"],
                name="disp_docente_unica_por_cal_dia_bloque",
            )
        ]
        indexes = [
            models.Index(fields=["docente", "calendario", "day_of_week"]),
            models.Index(fields=["bloque_inicio"]),
        ]

    def __str__(self):
        return f"{self.docente} · {self.get_day_of_week_display()} #{self.bloque_inicio.orden} x{self.bloques_duracion}"


class Clase(models.Model):
    """
    Unidad programada (una sesión). Mueve/drag&drop actualizando day_of_week/bloque_inicio/bloques_duracion.
    """

    class Tipo(models.TextChoices):
        TEORIA = "T", "Teoría"
        PRACTICA = "P", "Práctica"

    class Estado(models.TextChoices):
        PROPUESTO = "propuesto", "Propuesto"
        CONFIRMADO = "confirmado", "Confirmado"
        CANCELADO = "cancelado", "Cancelado"

    grupo = models.ForeignKey(
        "academics.Grupo", on_delete=models.CASCADE, related_name="clases"
    )
    tipo = models.CharField(max_length=1, choices=Tipo.choices)
    day_of_week = models.PositiveSmallIntegerField(choices=DiaSemana.choices)
    bloque_inicio = models.ForeignKey(
        Bloque, on_delete=models.PROTECT, related_name="clases_inicio"
    )
    bloques_duracion = models.PositiveSmallIntegerField(default=1)

    ambiente = models.ForeignKey(
        "facilities.Ambiente", on_delete=models.PROTECT, related_name="clases"
    )
    docente = models.ForeignKey(
        "users.Docente",
        on_delete=models.PROTECT,
        related_name="clases",
        null=True,
        blank=True,
    )

    estado = models.CharField(
        max_length=12, choices=Estado.choices, default=Estado.PROPUESTO
    )
    creado_en = models.DateTimeField(default=timezone.now)
    confirmado_en = models.DateTimeField(null=True, blank=True)

    docente_substituto = models.ForeignKey(
        "users.Docente",
        on_delete=models.PROTECT,
        related_name="clases_substituto",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Clase"
        verbose_name_plural = "Clases"
        indexes = [
            models.Index(fields=["day_of_week", "bloque_inicio"]),
            models.Index(fields=["docente", "day_of_week", "bloque_inicio"]),
            models.Index(fields=["ambiente", "day_of_week", "bloque_inicio"]),
            models.Index(fields=["grupo", "day_of_week", "bloque_inicio"]),
        ]
        constraints = [
            # Evita duplicar exacta misma clase por grupo en mismo bloque/día
            models.UniqueConstraint(
                fields=["grupo", "day_of_week", "bloque_inicio"],
                name="clase_unica_por_grupo_dia_bloque",
            )
        ]

    def __str__(self):
        return f"{self.grupo} {self.get_tipo_display()} · {self.get_day_of_week_display()} #{self.bloque_inicio.orden}"


class CambioHorario(models.Model):
    """
    Historial de reprogramaciones (drag&drop o sustitución).
    """

    clase = models.ForeignKey(Clase, on_delete=models.CASCADE, related_name="cambios")
    usuario = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="cambios_horario",
    )
    motivo = models.CharField(max_length=255, blank=True)

    old_day_of_week = models.PositiveSmallIntegerField(
        choices=DiaSemana.choices, null=True, blank=True
    )
    old_bloque_inicio = models.ForeignKey(
        Bloque,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cambios_old_inicio",
    )
    old_bloques_duracion = models.PositiveSmallIntegerField(null=True, blank=True)
    old_ambiente = models.ForeignKey(
        "facilities.Ambiente",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cambios_old_ambiente",
    )
    old_docente = models.ForeignKey(
        "users.Docente",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cambios_old_docente",
    )

    new_day_of_week = models.PositiveSmallIntegerField(
        choices=DiaSemana.choices, null=True, blank=True
    )
    new_bloque_inicio = models.ForeignKey(
        Bloque,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cambios_new_inicio",
    )
    new_bloques_duracion = models.PositiveSmallIntegerField(null=True, blank=True)
    new_ambiente = models.ForeignKey(
        "facilities.Ambiente",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cambios_new_ambiente",
    )
    new_docente = models.ForeignKey(
        "users.Docente",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cambios_new_docente",
    )

    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Cambio de Horario"
        verbose_name_plural = "Cambios de Horario"
        ordering = ("-fecha",)

    def __str__(self):
        return f"Cambio {self.clase_id} · {self.fecha:%Y-%m-%d %H:%M}"


class ConflictoHorario(models.Model):
    """
    Registro de choques detectados antes de confirmar (docente, ambiente o grupo).
    """

    class Tipo(models.TextChoices):
        DOCENTE = "DOCENTE", "Docente"
        AMBIENTE = "AMBIENTE", "Ambiente"
        GRUPO = "GRUPO", "Grupo"

    tipo = models.CharField(max_length=8, choices=Tipo.choices)
    clase_a = models.ForeignKey(
        Clase, on_delete=models.CASCADE, related_name="conflictos_como_a"
    )
    clase_b = models.ForeignKey(
        Clase, on_delete=models.CASCADE, related_name="conflictos_como_b"
    )
    resuelto = models.BooleanField(default=False)
    nota = models.CharField(max_length=255, blank=True)
    detectado_en = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Conflicto de Horario"
        verbose_name_plural = "Conflictos de Horario"
        indexes = [
            models.Index(fields=["tipo", "resuelto"]),
            models.Index(fields=["clase_a"]),
            models.Index(fields=["clase_b"]),
        ]

    def __str__(self):
        status = "OK" if self.resuelto else "PEND"
        return f"[{status}] {self.tipo} {self.clase_a_id} vs {self.clase_b_id}"
