from django.db import models


class Edificio(models.Model):
    codigo = models.CharField(max_length=30, unique=True)
    nombre = models.CharField(max_length=120)
    ubicacion = models.CharField(max_length=160, blank=True)

    class Meta:
        verbose_name = "Edificio"
        verbose_name_plural = "Edificios"
        indexes = [models.Index(fields=["codigo"])]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class TipoAmbiente(models.Model):
    nombre = models.CharField(max_length=80, unique=True)  # Aula, Laboratorio, Auditorio...
    descripcion = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Tipo de Ambiente"
        verbose_name_plural = "Tipos de Ambiente"

    def __str__(self):
        return self.nombre


class Ambiente(models.Model):
    edificio = models.ForeignKey(Edificio, on_delete=models.CASCADE, related_name="ambientes")
    tipo_ambiente = models.ForeignKey(TipoAmbiente, on_delete=models.PROTECT, related_name="ambientes")
    codigo = models.CharField(max_length=30)  # ej: A-101
    nombre = models.CharField(max_length=120, blank=True)
    capacidad = models.PositiveIntegerField()

    class Meta:
        verbose_name = "Ambiente"
        verbose_name_plural = "Ambientes"
        constraints = [
            models.UniqueConstraint(fields=["edificio", "codigo"], name="ambiente_codigo_unico_por_edificio")
        ]
        indexes = [models.Index(fields=["tipo_ambiente"]), models.Index(fields=["capacidad"])]

    def __str__(self):
        return f"{self.edificio.codigo}-{self.codigo} ({self.tipo_ambiente})"
