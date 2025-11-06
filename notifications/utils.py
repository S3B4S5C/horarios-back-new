from notifications.models import Notificacion
from academics.models import Inscripcion
from django.contrib.auth import get_user_model

User = get_user_model()

def notify_cambio_clase(clase, titulo: str, motivo: str = "", docente_anterior=None):
    """Crea notificaciones in-app para usuarios afectados."""
    grupo = clase.grupo
    # estudiantes del grupo
    estudiantes = Inscripcion.objects.filter(grupo=grupo).select_related("estudiante__user")
    for ins in estudiantes:
        Notificacion.objects.create(
            usuario=ins.estudiante.user, clase=clase,
            titulo=titulo, mensaje=_build_msg(clase, motivo)
        )
    # docente actual
    if getattr(clase, "docente", None) and clase.docente.user_id:
        Notificacion.objects.create(
            usuario=clase.docente.user, clase=clase,
            titulo=titulo, mensaje=_build_msg(clase, motivo)
        )
    # docente anterior (si cambió)
    if docente_anterior and docente_anterior.user_id:
        Notificacion.objects.create(
            usuario=docente_anterior.user, clase=clase,
            titulo=titulo, mensaje=_build_msg(clase, motivo)
        )

def _build_msg(clase, motivo):
    g = clase.grupo
    return (
        f"{g.asignatura.codigo}-{g.codigo} "
        f"{clase.get_tipo_display()} • {clase.get_day_of_week_display()} "
        f"#{clase.bloque_inicio.orden} x{clase.bloques_duracion} "
        f"• Aula: {clase.ambiente or 'por asignar'}"
        + (f" • Motivo: {motivo}" if motivo else "")
    )
