


import math
from academics.models import Asignatura
from scheduling.models import Calendario, Clase, DiaSemana, DisponibilidadDocente
from users.models import Docente


def _rango(bloque, dur):
    s = bloque.orden
    e = s + dur - 1
    return s, e

def _solapan(b1, d1, b2, d2):
    s1, e1 = b1, b1 + d1 - 1
    s2, e2 = b2, b2 + d2 - 1
    return not (e1 < s2 or e2 < s1)

def _bloques_requeridos(asig: Asignatura, cal: Calendario):
    m = cal.duracion_bloque_min or 45
    req_t = math.ceil((asig.horas_teoria_semana * 60) / m) if asig.horas_teoria_semana else 0
    req_p = math.ceil((asig.horas_practica_semana * 60) / m) if asig.horas_practica_semana else 0
    return req_t, req_p

def _carga_actual_en_bloques(docente_id: int, periodo_id: int):
    # Suma bloques por clases (no canceladas) del docente en el periodo
    qs = Clase.objects.filter(docente_id=docente_id, grupo__periodo_id=periodo_id).exclude(estado="cancelado")
    return qs.aggregate(total=sum("bloques_duracion"))["total"] or 0

def _dia_ints():
    return [DiaSemana.LUNES, DiaSemana.MARTES, DiaSemana.MIERCOLES, DiaSemana.JUEVES, DiaSemana.VIERNES]

def _candidatos_docentes(asig: Asignatura, prefer_especialidad=True):
    qs = Docente.objects.filter(activo=True)
    if prefer_especialidad and asig and asig.nombre:
        # match simple por substring en especialidad
        qs = qs.filter(especialidad__icontains=asig.nombre.split()[0])
    return list(qs)

def _ventanas_disponibles(docente: Docente, calendario: Calendario, day):
    # retorna lista de (bloque_inicio.orden, dur) para ese día
    ds = DisponibilidadDocente.objects.filter(docente=docente, calendario=calendario, day_of_week=day)\
                                      .select_related("bloque_inicio").order_by("bloque_inicio__orden")
    return [(d.bloque_inicio.orden, d.bloques_duracion, d.bloque_inicio_id) for d in ds]

def _hay_clase_en(ambiente_id, day, start_orden, dur):
    qs = Clase.objects.filter(ambiente_id=ambiente_id, day_of_week=day)
    for c in qs:
        if _solapan(start_orden, dur, c.bloque_inicio.orden, c.bloques_duracion):
            return True
    return False

def _hay_clase_para_docente(docente_id, day, start_orden, dur):
    qs = Clase.objects.filter(docente_id=docente_id, day_of_week=day)
    for c in qs:
        if _solapan(start_orden, dur, c.bloque_inicio.orden, c.bloques_duracion):
            return True
    return False