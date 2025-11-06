from django.db import models
from django.utils import timezone
from django.conf import settings


class Notificacion(models.Model):
    """
    Mensaje a usuarios afectados por cambios o confirmaciones de horario.
    """
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notificaciones"
    )
    clase = models.ForeignKey(
        "scheduling.Clase", on_delete=models.SET_NULL, null=True, blank=True, related_name="notificaciones"
    )

    titulo = models.CharField(max_length=160)
    mensaje = models.TextField()
    leida = models.BooleanField(default=False)
    creada_en = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Notificación"
        verbose_name_plural = "Notificaciones"
        ordering = ("-creada_en",)

    def __str__(self):
        return f"{self.titulo} → {self.usuario.username}"
