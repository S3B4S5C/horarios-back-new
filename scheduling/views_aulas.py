from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiExample

from users.permissions import IsManagerOrStaff
from facilities.models import Ambiente
from scheduling.models import Clase, Calendario
from academics.models import Asignatura
from .serializers import AsignarAulasRequestSerializer, AsignarAulasResponseSerializer

def _tipo_ambiente_para_clase(clase: Clase):
    asig = clase.grupo.asignatura
    if clase.tipo == "T":
        return asig.tipo_ambiente_teoria_id
    return asig.tipo_ambiente_practica_id

def _candidatos_ambiente(clase: Clase, prefer_edificio=None):
    tipo_id = _tipo_ambiente_para_clase(clase)
    if not tipo_id:
        return Ambiente.objects.none()
    qs = Ambiente.objects.filter(tipo_ambiente_id=tipo_id, capacidad__gte=clase.grupo.capacidad)
    if prefer_edificio:
        # primero preferidos, luego el resto
        prefer = qs.filter(edificio_id=prefer_edificio)
        otros = qs.exclude(edificio_id=prefer_edificio)
        return list(prefer) + list(otros)
    return list(qs.order_by("capacidad"))

@extend_schema(
    tags=["aulas"],
    request=AsignarAulasRequestSerializer,
    responses={200: AsignarAulasResponseSerializer},
    examples=[OpenApiExample("Asignar aulas automáticamente", value={
        "periodo": 1, "calendario": 1, "force": False
    })],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def asignar_aulas_view(request):
    ser = AsignarAulasRequestSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    periodo_id = ser.validated_data["periodo"]
    calendario_id = ser.validated_data["calendario"]
    prefer_edificio = ser.validated_data.get("prefer_edificio")
    force = ser.validated_data["force"]
    ids = ser.validated_data.get("clase_ids")

    qs = (Clase.objects
      .filter(grupo__periodo_id=periodo_id,
              bloque_inicio__calendario_id=calendario_id)
      .exclude(estado="cancelado"))
    if ids:
        qs = qs.filter(id__in=ids)

    res = []
    for c in qs.select_related("grupo__asignatura","docente","bloque_inicio","ambiente"):
        if c.ambiente_id and not force:
            res.append({"clase": c.id, "ambiente_anterior": c.ambiente_id, "ambiente_nuevo": c.ambiente_id, "estado": "omitido"})
            continue
        candidatos = _candidatos_ambiente(c, prefer_edificio=prefer_edificio)
        elegido = None
        for a in candidatos:
            choques = (Clase.objects
                .filter(ambiente=a,
                        day_of_week=c.day_of_week,
                        bloque_inicio__calendario_id=calendario_id)
                .exclude(id=c.id)
                .select_related("bloque_inicio"))
            conflicto = any(
                not ( (c.bloque_inicio.orden + c.bloques_duracion -1) < (x.bloque_inicio.orden) or
                      (x.bloque_inicio.orden + x.bloques_duracion -1) < (c.bloque_inicio.orden) )
                for x in choques.select_related("bloque_inicio")
            )
            if not conflicto:
                elegido = a
                break

        if elegido:
            prev = c.ambiente_id
            c.ambiente = elegido
            c.save(update_fields=["ambiente"])
            res.append({"clase": c.id, "ambiente_anterior": prev, "ambiente_nuevo": elegido.id, "estado": "asignado"})
        else:
            res.append({"clase": c.id, "ambiente_anterior": c.ambiente_id, "ambiente_nuevo": None, "estado": "sin_candidatos"})

    return Response({"asignaciones": res})
