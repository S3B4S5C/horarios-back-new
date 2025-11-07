import math
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiParameter
import csv, io
from django.db.models import Sum, F
from academics.models import Asignatura, Grupo
from scheduling.helpers import _bloques_requeridos, _dia_ints, _hay_clase_para_docente, _ventanas_disponibles
from users.models import Docente
from users.permissions import IsManagerOrStaff, IsTeacherOrManager
from scheduling.models import Calendario, Bloque, Clase, DiaSemana, DisponibilidadDocente
from scheduling.serializers import CalendarioSerializer, BloqueSerializer, DisponibilidadDocenteSerializer, PropuestaClasesRequestSerializer, PropuestaClasesResponseSerializer, PropuestaDocenteRequestSerializer, PropuestaDocenteResponseSerializer
from django.db.models.functions import Coalesce

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from academics.models import Grupo
from scheduling.models import Clase, Bloque, Calendario, DisponibilidadDocente


# ---- HU008: Calendario y Bloques ----
@extend_schema(tags=["calendarios"], responses={200: CalendarioSerializer(many=True)})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def calendarios_list_view(request):
    qs = Calendario.objects.select_related("periodo").all().order_by("-periodo__gestion","-periodo__numero","id")
    periodo_id = request.query_params.get("periodo")
    if periodo_id:
        qs = qs.filter(periodo_id=periodo_id)
    return Response(CalendarioSerializer(qs, many=True).data)

@extend_schema(tags=["calendarios"], request=CalendarioSerializer, responses={201: CalendarioSerializer})
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def calendarios_create_view(request):
    ser = CalendarioSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    obj = ser.save()
    return Response(CalendarioSerializer(obj).data, status=201)

@extend_schema(tags=["calendarios"], request=CalendarioSerializer, responses={200: CalendarioSerializer})
@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def calendarios_update_view(request, pk: int):
    try:
        obj = Calendario.objects.get(pk=pk)
    except Calendario.DoesNotExist:
        return Response({"detail": "No encontrado."}, status=404)
    ser = CalendarioSerializer(instance=obj, data=request.data, partial=(request.method=="PATCH"))
    ser.is_valid(raise_exception=True)
    obj = ser.save()
    return Response(CalendarioSerializer(obj).data)

@extend_schema(tags=["calendarios"], responses={204: None})
@api_view(["DELETE"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def calendarios_delete_view(request, pk: int):
    try:
        obj = Calendario.objects.get(pk=pk)
    except Calendario.DoesNotExist:
        return Response({"detail": "No encontrado."}, status=404)
    obj.delete()
    return Response(status=204)

@extend_schema(
    tags=["bloques"],
    parameters=[OpenApiParameter("calendario", int, OpenApiParameter.QUERY)],
    responses={200: BloqueSerializer(many=True)}
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def bloques_list_view(request):
    qs = Bloque.objects.select_related("calendario").all().order_by("calendario_id","orden")
    cal_id = request.query_params.get("calendario")
    if cal_id:
        qs = qs.filter(calendario_id=cal_id)
    return Response(BloqueSerializer(qs, many=True).data)

@extend_schema(tags=["bloques"], request=BloqueSerializer, responses={201: BloqueSerializer})
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def bloques_create_view(request):
    ser = BloqueSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    obj = ser.save()
    return Response(BloqueSerializer(obj).data, status=201)

@extend_schema(tags=["bloques"], request=BloqueSerializer, responses={200: BloqueSerializer})
@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def bloques_update_view(request, pk: int):
    try:
        obj = Bloque.objects.get(pk=pk)
    except Bloque.DoesNotExist:
        return Response({"detail":"No encontrado."}, status=404)
    ser = BloqueSerializer(instance=obj, data=request.data, partial=(request.method=="PATCH"))
    ser.is_valid(raise_exception=True)
    obj = ser.save()
    return Response(BloqueSerializer(obj).data)

@extend_schema(tags=["bloques"], responses={204: None})
@api_view(["DELETE"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def bloques_delete_view(request, pk: int):
    try:
        obj = Bloque.objects.get(pk=pk)
    except Bloque.DoesNotExist:
        return Response({"detail":"No encontrado."}, status=404)
    obj.delete()
    return Response(status=204)

# ---- HU009: Disponibilidad Docente ----
@extend_schema(
    tags=["disponibilidad"],
    parameters=[
        OpenApiParameter("calendario", int, OpenApiParameter.QUERY),
        OpenApiParameter("docente", int, OpenApiParameter.QUERY),
        OpenApiParameter("day", int, OpenApiParameter.QUERY),
    ],
    responses={200: DisponibilidadDocenteSerializer(many=True)}
)
@api_view(["GET"])
def disponibilidad_list_view(request):
    qs = DisponibilidadDocente.objects.select_related("docente","calendario","bloque_inicio").all()
    # visibilidad: docentes ven sólo las suyas
    if getattr(getattr(request.user, "profile", None), "role", None) == "DOCENTE":
        qs = qs.filter(docente__user=request.user)
    # filtros
    cal = request.query_params.get("calendario"); doc = request.query_params.get("docente"); day = request.query_params.get("day")
    if cal: qs = qs.filter(calendario_id=cal)
    if doc: qs = qs.filter(docente_id=doc)
    if day: qs = qs.filter(day_of_week=day)
    qs = qs.order_by("docente_id","day_of_week","bloque_inicio__orden")
    return Response(DisponibilidadDocenteSerializer(qs, many=True).data)

@extend_schema(tags=["disponibilidad"], request=DisponibilidadDocenteSerializer, responses={201: DisponibilidadDocenteSerializer})
@api_view(["POST"])
def disponibilidad_create_view(request):
    data = request.data.copy()
    # Si es docente, forzar su propio docente_id
    if getattr(getattr(request.user, "profile", None), "role", None) == "DOCENTE":
        data["docente"] = getattr(request.user, "docente", None).id
    ser = DisponibilidadDocenteSerializer(data=data)
    ser.is_valid(raise_exception=True)
    obj = ser.save()
    return Response(DisponibilidadDocenteSerializer(obj).data, status=201)

@extend_schema(tags=["disponibilidad"], request=DisponibilidadDocenteSerializer, responses={200: DisponibilidadDocenteSerializer})
@api_view(["PUT", "PATCH"])
def disponibilidad_update_view(request, pk: int):
    try:
        obj = DisponibilidadDocente.objects.get(pk=pk)
    except DisponibilidadDocente.DoesNotExist:
        return Response({"detail":"No encontrado."}, status=404)
    # docentes sólo pueden tocar la suya
    if getattr(getattr(request.user, "profile", None), "role", None) == "DOCENTE" and obj.docente.user_id != request.user.id:
        return Response({"detail":"Prohibido."}, status=403)
    ser = DisponibilidadDocenteSerializer(instance=obj, data=request.data, partial=(request.method=="PATCH"))
    ser.is_valid(raise_exception=True)
    obj = ser.save()
    return Response(DisponibilidadDocenteSerializer(obj).data)

@extend_schema(tags=["disponibilidad"], responses={204: None})
@api_view(["DELETE"])
def disponibilidad_delete_view(request, pk: int):
    try:
        obj = DisponibilidadDocente.objects.get(pk=pk)
    except DisponibilidadDocente.DoesNotExist:
        return Response({"detail":"No encontrado."}, status=404)
    if getattr(getattr(request.user, "profile", None), "role", None) == "DOCENTE" and obj.docente.user_id != request.user.id:
        return Response({"detail":"Prohibido."}, status=403)
    obj.delete()
    return Response(status=204)

# ---- HU009 extra: carga masiva CSV (opcional) ----
@extend_schema(
    tags=["disponibilidad"],
    request=None,  # file multipart
    responses={201: dict},
    examples=[OpenApiExample("CSV ejemplo (cabeceras)", value="docente,calendario,day_of_week,bloque_inicio,bloques_duracion,preferencia\n12,1,1,3,2,1")],
)
@api_view(["POST"])
@parser_classes([MultiPartParser])
def disponibilidad_import_csv_view(request):
    """
    Carga CSV con columnas:
    docente,calendario,day_of_week,bloque_inicio,bloques_duracion,preferencia
    """
    if "file" not in request.FILES:
        return Response({"detail": "Adjunta 'file' CSV."}, status=400)
    f = request.FILES["file"]
    text = io.TextIOWrapper(f.file, encoding="utf-8")
    reader = csv.DictReader(text)
    created, errors = 0, []
    with transaction.atomic():
        for i, row in enumerate(reader, start=2):
            ser = DisponibilidadDocenteSerializer(data=row)
            if ser.is_valid():
                ser.save(); created += 1
            else:
                errors.append({"row": i, "errors": ser.errors})
    return Response({"created": created, "errors": errors}, status=201)




# ================= HU011: Asignación automática de docentes =================

TimeCell = Tuple[int, int]

def _bloque_maps(calendario_id: int):
    """
    Retorna ayudas para expandir duraciones por orden de bloque.
    """
    bloques = list(Bloque.objects.filter(calendario_id=calendario_id).order_by("orden").only("id", "orden"))
    id_by_idx = [b.id for b in bloques]
    idx_by_id = {b.id: i for i, b in enumerate(bloques)}
    return id_by_idx, idx_by_id

def _expand_por_duracion(bloque_inicio_id: int, duracion: int, id_by_idx: List[int], idx_by_id: Dict[int, int]) -> List[int]:
    """
    Expande un bloque_inicio + duracion (en # de bloques) a la lista de bloque_ids consecutivos por ORDEN.
    """
    start_idx = idx_by_id[bloque_inicio_id]
    end_idx = start_idx + duracion
    # recorte defensivo por si alguien configuró duraciones más largas que la grilla
    end_idx = min(end_idx, len(id_by_idx))
    return id_by_idx[start_idx:end_idx]

def _bloques_del_grupo(grupo_id: int, calendario_id: int) -> Set[TimeCell]:
    """
    Devuelve el conjunto de celdas (día, bloque_id) donde el grupo YA tiene clases programadas.
    """
    id_by_idx, idx_by_id = _bloque_maps(calendario_id)
    celdas: Set[TimeCell] = set()
    qs = (Clase.objects.filter(grupo_id=grupo_id)
          .select_related("bloque_inicio")
          .only("day_of_week", "bloque_inicio_id", "bloques_duracion"))
    for c in qs:
        for b_id in _expand_por_duracion(c.bloque_inicio_id, c.bloques_duracion, id_by_idx, idx_by_id):
            celdas.add((int(c.day_of_week), int(b_id)))
    return celdas

def _bloques_disponibles_docente(docente_id: int, calendario_id: int) -> Set[TimeCell]:
    """
    Set de celdas (día, bloque_id) donde el docente marcó disponibilidad.
    """
    id_by_idx, idx_by_id = _bloque_maps(calendario_id)
    disp: Set[TimeCell] = set()
    qs = (DisponibilidadDocente.objects
          .filter(docente_id=docente_id, calendario_id=calendario_id)
          .select_related("bloque_inicio")
          .only("day_of_week", "bloque_inicio_id", "bloques_duracion"))
    for r in qs:
        for b_id in _expand_por_duracion(r.bloque_inicio_id, r.bloques_duracion, id_by_idx, idx_by_id):
            disp.add((int(r.day_of_week), int(b_id)))
    return disp

def _bloques_ocupados_docente_en_periodo(docente_id: int, periodo_id: int) -> Set[TimeCell]:
    """
    Set de celdas ya ocupadas por clases del docente en el período (para evitar choques).
    """
    celdas: Set[TimeCell] = set()
    qs = (Clase.objects
          .filter(docente_id=docente_id, grupo__periodo_id=periodo_id)
          .select_related("bloque_inicio")
          .only("day_of_week", "bloque_inicio_id", "bloques_duracion"))
    # Necesitamos calendario para expandir; tomamos el calendario del primer bloque encontrado
    # Si manejas múltiples calendarios por período, conviene pasar calendario_id desde la view.
    # Aquí expandimos por ORDEN usando el calendario del bloque_inicio.
    # Como Bloque tiene orden por calendario, hacemos un cache local por calendario.
    cache_maps: Dict[int, Tuple[List[int], Dict[int, int]]] = {}

    for c in qs:
        cal_id = c.bloque_inicio.calendario_id
        if cal_id not in cache_maps:
            cache_maps[cal_id] = _bloque_maps(cal_id)
        id_by_idx, idx_by_id = cache_maps[cal_id]
        for b_id in _expand_por_duracion(c.bloque_inicio_id, c.bloques_duracion, id_by_idx, idx_by_id):
            celdas.add((int(c.day_of_week), int(b_id)))
    return celdas

def _carga_actual_en_bloques(docente_id: int, periodo_id: int) -> int:
    """
    Suma de bloques (bloques_duracion) del docente en el período.
    """
    return (Clase.objects
            .filter(docente_id=docente_id, grupo__periodo_id=periodo_id)
            .aggregate(total=Coalesce(Sum("bloques_duracion"), 0))["total"])  # type: ignore

def _carga_max_docente(docente) -> int:
    """
    Recupera la carga máxima semanal del docente.
    Ajusta según tu modelo (si está en el propio Docente u otra tabla).
    """
    # Ejemplo: return docente.carga_max_semanal or 999999
    return getattr(docente, "carga_max_semanal", 999999) or 999999

def _es_especialista(docente, asignatura) -> bool:
    """
    Devuelve True si el docente es especialista de la asignatura.
    Ajusta según tus modelos (áreas/competencias).
    """
    # Implementación de ejemplo: por ahora False si no hay relación.
    try:
        areas = set(getattr(docente, "areas_especialidad", []) or [])
        asig_area = getattr(asignatura, "area", None)
        return asig_area in areas if asig_area else False
    except Exception:
        return False

@dataclass
class Candidato:
    docente_id: int
    score: float
    cobertura_bloques: int
    total_bloques_grupo: int
    carga_actual: int
    motivo: str

# -------------------------------------------------------------------
# Backtracking para asignación óptima (max suma de score)
# -------------------------------------------------------------------

def _mejor_asignacion_por_backtracking(
    grupos: List[Grupo],
    calendario_id: int,
    periodo_id: int,
    prefer_esp: bool,
) -> Dict[int, Candidato]:
    """
    Resuelve asignación óptima: cada grupo -> 0 o 1 docente, maximizando score de cobertura,
    evitando choques con clases ya asignadas a docentes y respetando cargas máximas.
    """
    # Pre-cálculos por grupo
    group_cells: Dict[int, Set[TimeCell]] = {g.id: _bloques_del_grupo(g.id, calendario_id) for g in grupos}
    total_cells_group: Dict[int, int] = {gid: len(cset) for gid, cset in group_cells.items()}

    from .helpers import _candidatos_docentes 

    docentes_cache_disp: Dict[int, Set[TimeCell]] = {}
    docentes_cache_ocup: Dict[int, Set[TimeCell]] = {}
    docentes_cache_carga: Dict[int, int] = {}
    docentes_cache_obj: Dict[int, any] = {}

    candidatos_por_grupo: Dict[int, List[Candidato]] = {}

    for g in grupos:
        asig = g.asignatura
        candidatos_model = list(_candidatos_docentes(asig, prefer_especialidad=prefer_esp))
        cands: List[Candidato] = []
        cset = group_cells[g.id]
        tot = total_cells_group[g.id]

        # Si el grupo no tiene clases programadas aún, el score de cobertura será 0. Igualmente ponderamos especialidad/carga.
        for d in candidatos_model:
            docentes_cache_obj[d.id] = d
            if d.id not in docentes_cache_disp:
                docentes_cache_disp[d.id] = _bloques_disponibles_docente(d.id, calendario_id)
            if d.id not in docentes_cache_ocup:
                docentes_cache_ocup[d.id] = _bloques_ocupados_docente_en_periodo(d.id, periodo_id)
            if d.id not in docentes_cache_carga:
                docentes_cache_carga[d.id] = _carga_actual_en_bloques(d.id, periodo_id)

            disp = docentes_cache_disp[d.id]
            ocup = docentes_cache_ocup[d.id]

            # No dejar choques: si el docente ya tiene clase en alguna celda del grupo, lo penalizamos fuerte
            hay_choque = len(cset & ocup) > 0

            cobertura = len(cset & disp) if tot > 0 else 0
            cobertura_ratio = (cobertura / tot) if tot > 0 else 0.0

            bonus_esp = 0.15 if (prefer_esp and _es_especialista(d, asig)) else 0.0
            # Penalización por choque fuerte
            penal_choque = -1.0 if hay_choque else 0.0
            # Penalización suave por carga alta
            carga = docentes_cache_carga[d.id]
            carga_max = _carga_max_docente(d)
            stress = min(1.0, carga / max(1, carga_max))
            penal_carga = -0.10 * stress

            score = (0.80 * cobertura_ratio) + bonus_esp + penal_choque + penal_carga

            motivo = "cobertura={:.0%}{}".format(
                cobertura_ratio,
                " choque" if hay_choque else ""
            )
            cands.append(Candidato(
                docente_id=d.id,
                score=score,
                cobertura_bloques=cobertura,
                total_bloques_grupo=tot,
                carga_actual=carga,
                motivo=motivo
            ))

        # Si no hay candidatos, igual dejamos lista vacía
        # Ordenamos por score desc y luego menor carga
        cands.sort(key=lambda x: (x.score, -x.cobertura_bloques, -x.total_bloques_grupo, -x.carga_actual), reverse=True)
        candidatos_por_grupo[g.id] = cands

    # Ordenar grupos por “dificultad”: menos candidatos o menor cobertura máxima
    orden_grupos = sorted(
        grupos,
        key=lambda gg: (
            len(candidatos_por_grupo.get(gg.id, [])) or 9999,
            -(candidatos_por_grupo.get(gg.id, [Candidato(0,0,0,0,0,"")])[0].score if candidatos_por_grupo.get(gg.id) else 0)
        )
    )

    # Backtracking state
    best_score = float("-inf")
    best_assign: Dict[int, Candidato] = {}

    # Estados mutables por docente
    cargas_mut: Dict[int, int] = {did: docentes_cache_carga[did] for did in docentes_cache_carga}
    ocup_mut: Dict[int, Set[TimeCell]] = {did: set(docentes_cache_ocup[did]) for did in docentes_cache_ocup}

    # Límite superior para poda: max score restante por grupo
    max_score_por_grupo: Dict[int, float] = {}
    for g in grupos:
        lst = candidatos_por_grupo.get(g.id, [])
        max_score_por_grupo[g.id] = lst[0].score if lst else 0.0

    def upper_bound(idx: int, current: float) -> float:
        ub = current
        for j in range(idx, len(orden_grupos)):
            gid = orden_grupos[j].id
            ub += max_score_por_grupo.get(gid, 0.0)
        return ub

    asignacion_actual: Dict[int, Candidato] = {}

    def bt(i: int, score_actual: float):
        nonlocal best_score, best_assign

        if i == len(orden_grupos):
            if score_actual > best_score:
                best_score = score_actual
                best_assign = dict(asignacion_actual)
            return

        if upper_bound(i, score_actual) <= best_score:
            return  # poda

        g = orden_grupos[i]
        gid = g.id
        candidatos = candidatos_por_grupo.get(gid, [])

        # Opción 1: no asignar a nadie (score 0) — por si todos chocan
        # Probamos al final si no encontramos viable
        assigned_someone = False

        for cand in candidatos:
            d_id = cand.docente_id
            carga_max = _carga_max_docente(docentes_cache_obj[d_id])

            # Regla de choque “duro”: si hay al menos una superposición temporal con ocupaciones actuales -> saltar
            if cand.cobertura_bloques == 0:
                # Permitimos 0 cobertura sólo si no hay alternativas con cobertura > 0
                if any(c.cobertura_bloques > 0 for c in candidatos):
                    continue

            # No forzamos sumar celdas: solo validamos que NO haya choques con ocup_mut
            cset = group_cells[gid]
            if any(cell in ocup_mut[d_id] for cell in cset):
                continue  # choque con clases existentes del docente

            # Control suave de carga: no superar carga_max demasiado (permitimos asignación aunque no sumamos bloques ahora)
            # Como aquí solo “asignamos al grupo” y no creamos clases nuevas, estimamos que la carga potencial podría crecer.
            # Si quieres, puedes sumar un estimado = total_bloques_grupo; aquí lo usamos como control de techo.
            est_inc = total_cells_group[gid]
            if cargas_mut[d_id] + est_inc > carga_max * 1.10:  # pequeño margen
                continue

            # Aplicar
            asignacion_actual[gid] = cand
            cargas_mut[d_id] += 0  # no alteramos carga efectiva; si quieres, usa += est_inc
            # No alteramos ocup_mut porque no creamos nuevas clases, solo sugerimos docente
            assigned_someone = True
            bt(i + 1, score_actual + cand.score)
            # deshacer
            # cargas_mut[d_id] -= 0

            # Poda local: si el score es muy bajo y ya tenemos uno alto, podrías cortar, pero lo dejamos exhaustivo.

        # Opción 2: sin asignación (None) si nadie fue viable
        if not assigned_someone:
            asignacion_actual[gid] = Candidato(docente_id=0, score=0.0, cobertura_bloques=0,
                                               total_bloques_grupo=total_cells_group[gid],
                                               carga_actual=0, motivo="sin_candidato")
            bt(i + 1, score_actual)
            asignacion_actual.pop(gid, None)

    bt(0, 0.0)
    return best_assign

# -------------------------------------------------------------------
# View principal (mantiene request/response)
# -------------------------------------------------------------------

@extend_schema(
    tags=["asignacion-docente"],
    request=PropuestaDocenteRequestSerializer,
    responses={200: PropuestaDocenteResponseSerializer},
    examples=[OpenApiExample("Proponer docentes en período/calendario", value={
        "periodo": 1, "calendario": 1, "asignatura": 5, "turno": 1, "persistir": False
    })],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def asignacion_docentes_proponer_view(request):
    """
    Propuesta óptima de docentes considerando disponibilidad (día/bloques) y choques.
    - Objetivo: maximizar cobertura de bloques de las clases del grupo con disponibilidad del docente.
    - Restricciones: evitar choques con clases ya asignadas al docente y no sobrepasar carga máxima (suave).
    - Preferencias: prioriza especialidad si 'prefer_especialidad' es True y balancea por carga.
    Formato de E/S se mantiene igual.
    """
    ser = PropuestaDocenteRequestSerializer(data=request.data)
    ser.is_valid(raise_exception=True)

    periodo_id = ser.validated_data["periodo"]
    calendario_id = ser.validated_data["calendario"]
    asignatura_id = ser.validated_data.get("asignatura")
    turno_id = ser.validated_data.get("turno")
    persistir = ser.validated_data["persistir"]
    prefer_esp = ser.validated_data["prefer_especialidad"]

    grupos_qs = Grupo.objects.filter(periodo_id=periodo_id).select_related("asignatura", "docente")
    if asignatura_id:
        grupos_qs = grupos_qs.filter(asignatura_id=asignatura_id)
    if turno_id:
        grupos_qs = grupos_qs.filter(turno_id=turno_id)

    grupos = list(grupos_qs)

    # Si NO vamos a persistir, pero el grupo YA tiene docente, devolvemos “ya_asignado”
    if not persistir:
        # Aun así incluimos en la optimización a los grupos sin docente
        grupos_sin_doc = [g for g in grupos if not g.docente_id]
        grupos_con_doc = [g for g in grupos if g.docente_id]

        asignaciones = _mejor_asignacion_por_backtracking(grupos_sin_doc, calendario_id, periodo_id, prefer_esp)
        sugerencias = []

        for g in grupos_con_doc:
            sugerencias.append({"grupo": g.id, "docente_sugerido": g.docente_id, "motivo": "ya_asignado"})

        for g in grupos_sin_doc:
            cand = asignaciones.get(g.id)
            if cand and cand.docente_id:
                sugerencias.append({"grupo": g.id, "docente_sugerido": cand.docente_id, "motivo": cand.motivo})
            else:
                sugerencias.append({"grupo": g.id, "docente_sugerido": None, "motivo": "sin_candidato"})

        return Response({"sugerencias": sugerencias})

    # Si SÍ persistimos, corremos la optimización sobre TODOS y luego guardamos.
    asignaciones = _mejor_asignacion_por_backtracking(grupos, calendario_id, periodo_id, prefer_esp)

    sugerencias = []
    for g in grupos:
        cand = asignaciones.get(g.id)
        if cand and cand.docente_id:
            if g.docente_id != cand.docente_id:
                g.docente_id = cand.docente_id
                g.save(update_fields=["docente"])
            sugerencias.append({"grupo": g.id, "docente_sugerido": cand.docente_id, "motivo": cand.motivo})
        else:
            # No sobrescribimos si ya tenía docente; solo sugerimos None si no hay mejor opción
            sugerencias.append({"grupo": g.id, "docente_sugerido": g.docente_id or None,
                                "motivo": "sin_candidato" if not g.docente_id else "ya_asignado"})

    return Response({"sugerencias": sugerencias})
# ================= HU011: Propuesta de clases (sesiones) =================

@extend_schema(
    tags=["asignacion-clases"],
    request=PropuestaClasesRequestSerializer,
    responses={200: PropuestaClasesResponseSerializer},
    examples=[OpenApiExample("Proponer clases", value={
        "periodo": 1, "calendario": 1, "reusar_docente_de_grupo": True, "persistir": False, "max_bloques_por_sesion": 2
    })],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsManagerOrStaff])
def clases_proponer_view(request):
    ser = PropuestaClasesRequestSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    periodo_id = ser.validated_data["periodo"]
    calendario_id = ser.validated_data["calendario"]
    asignatura_id = ser.validated_data.get("asignatura")
    turno_id = ser.validated_data.get("turno")
    reusar_docente = ser.validated_data["reusar_docente_de_grupo"]
    persistir = ser.validated_data["persistir"]
    max_por_sesion = max(1, ser.validated_data["max_bloques_por_sesion"])

    cal = Calendario.objects.get(pk=calendario_id)
    grupos = Grupo.objects.filter(periodo_id=periodo_id)
    if asignatura_id: grupos = grupos.filter(asignatura_id=asignatura_id)
    if turno_id: grupos = grupos.filter(turno_id=turno_id)

    previews, omitidas = [], []
    creadas = 0

    for g in grupos.select_related("asignatura", "docente"):
        asig = g.asignatura
        req_t, req_p = _bloques_requeridos(asig, cal)
        if req_t == 0 and req_p == 0:
            omitidas.append(f"Grupo {g.id}: sin horas requeridas")
            continue
        docente = g.docente if reusar_docente else None
        if not docente:
            omitidas.append(f"Grupo {g.id}: sin docente asignado")
            continue

        # Intentar colocar sesiones greedily en las primeras ventanas disponibles (Lun-Vie)
        for tipo, req in (("T", req_t), ("P", req_p)):
            bloques_pend = req
            if bloques_pend <= 0:
                continue
            day_candidates = _dia_ints()
            for day in day_candidates:
                if bloques_pend <= 0:
                    break
                ventanas = _ventanas_disponibles(docente, cal, day)
                for (start_orden, dur_disp, bloque_inicio_id) in ventanas:
                    if bloques_pend <= 0:
                        break
                    dur_sesion = min(max_por_sesion, dur_disp, bloques_pend)
                    # Evitar choque con clases del docente
                    if _hay_clase_para_docente(docente.id, day, start_orden, dur_sesion):
                        continue
                    # Creamos preview (ambiente se asigna en HU014)
                    pv = {
                        "grupo": g.id, "tipo": tipo,
                        "day_of_week": int(day), "bloque_inicio": bloque_inicio_id,
                        "bloques_duracion": int(dur_sesion),
                        "docente": docente.id, "ambiente": None,
                    }
                    previews.append(pv)
                    if persistir:
                        Clase.objects.create(
                            grupo=g, tipo=tipo, day_of_week=day,
                            bloque_inicio=Bloque.objects.get(pk=bloque_inicio_id),
                            bloques_duracion=dur_sesion,
                            ambiente_id=None, docente=docente, estado="propuesto"
                        )
                        creadas += 1
                    bloques_pend -= dur_sesion

            if bloques_pend > 0:
                omitidas.append(f"Grupo {g.id} {tipo}: faltaron {bloques_pend} bloque(s) por disponibilidad")

    return Response({"creadas": creadas, "previsualizacion": previews, "omitidas": omitidas})