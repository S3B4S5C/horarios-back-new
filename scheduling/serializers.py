from rest_framework import serializers
from datetime import datetime
from scheduling.models import Calendario, Bloque, Clase, ConflictoHorario, DisponibilidadDocente
from users.models import Docente

class CalendarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Calendario
        fields = ["id", "periodo", "nombre", "duracion_bloque_min"]

    def validate_duracion_bloque_min(self, v):
        if v <= 0:
            raise serializers.ValidationError("duracion_bloque_min debe ser > 0 (p.ej., 45).")
        return v

class BloqueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bloque
        fields = ["id", "calendario", "orden", "hora_inicio", "hora_fin", "duracion_min"]

    def validate(self, attrs):
        h1 = attrs.get("hora_inicio", getattr(self.instance, "hora_inicio", None))
        h2 = attrs.get("hora_fin", getattr(self.instance, "hora_fin", None))
        mins = attrs.get("duracion_min", getattr(self.instance, "duracion_min", None))
        cal = attrs.get("calendario", getattr(self.instance, "calendario", None))

        if h1 and h2 and h2 <= h1:
            raise serializers.ValidationError("hora_fin debe ser mayor que hora_inicio.")
        if mins is None or mins <= 0:
            raise serializers.ValidationError("duracion_min debe ser > 0.")
        if cal and mins % cal.duracion_bloque_min != 0:
            raise serializers.ValidationError("duracion_min debe ser múltiplo de duracion_bloque_min del calendario.")
        # (Opcional) Validar que (h2-h1) coincida con duracion_min
        if h1 and h2:
            dt1 = datetime.combine(datetime.today(), h1)
            dt2 = datetime.combine(datetime.today(), h2)
            diff = int((dt2 - dt1).total_seconds() // 60)
            if diff != mins:
                raise serializers.ValidationError("duracion_min no coincide con la diferencia entre hora_inicio y hora_fin.")
        return attrs

class DisponibilidadDocenteSerializer(serializers.ModelSerializer):
    class Meta:
        model = DisponibilidadDocente
        fields = ["id", "docente", "calendario", "day_of_week", "bloque_inicio", "bloques_duracion", "preferencia"]

    def validate_bloques_duracion(self, v):
        if v <= 0:
            raise serializers.ValidationError("bloques_duracion debe ser >= 1.")
        return v

    def validate(self, attrs):
        # Evitar solapes: rango [orden, orden+dur-1]
        docente = attrs.get("docente", getattr(self.instance, "docente", None))
        cal = attrs.get("calendario", getattr(self.instance, "calendario", None))
        day = attrs.get("day_of_week", getattr(self.instance, "day_of_week", None))
        b0 = attrs.get("bloque_inicio", getattr(self.instance, "bloque_inicio", None))
        dur = attrs.get("bloques_duracion", getattr(self.instance, "bloques_duracion", 1))
        if not (docente and cal and day and b0 and dur):
            return attrs
        start = b0.orden
        end = start + dur - 1
        qs = DisponibilidadDocente.objects.filter(docente=docente, calendario=cal, day_of_week=day)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        qs = qs.select_related("bloque_inicio")
        for d in qs:
            s2 = d.bloque_inicio.orden
            e2 = s2 + d.bloques_duracion - 1
            if not (end < s2 or e2 < start):
                raise serializers.ValidationError("La disponibilidad se solapa con otra existente.")
        return attrs


class PropuestaDocenteRequestSerializer(serializers.Serializer):
    periodo = serializers.IntegerField()
    calendario = serializers.IntegerField()
    asignatura = serializers.IntegerField(required=False)
    turno = serializers.IntegerField(required=False)
    persistir = serializers.BooleanField(default=False)  # si True, actualiza grupo.docente
    prefer_especialidad = serializers.BooleanField(default=True)  # filtra por especialidad si es posible

class GrupoDocenteSugerenciaSerializer(serializers.Serializer):
    grupo = serializers.IntegerField()
    docente_sugerido = serializers.IntegerField(allow_null=True)
    motivo = serializers.CharField()

class PropuestaDocenteResponseSerializer(serializers.Serializer):
    sugerencias = GrupoDocenteSugerenciaSerializer(many=True)


class PropuestaClasesRequestSerializer(serializers.Serializer):
    periodo = serializers.IntegerField()
    calendario = serializers.IntegerField()
    asignatura = serializers.IntegerField(required=False)
    turno = serializers.IntegerField(required=False)
    reusar_docente_de_grupo = serializers.BooleanField(default=True)  # usa grupo.docente
    persistir = serializers.BooleanField(default=False)               # crea Clase con estado "propuesto"
    max_bloques_por_sesion = serializers.IntegerField(required=False, default=2)  # p.ej. 2×45'=90min

class ClasePreviewSerializer(serializers.Serializer):
    grupo = serializers.IntegerField()
    tipo = serializers.ChoiceField(choices=["T", "P"])
    day_of_week = serializers.IntegerField()
    bloque_inicio = serializers.IntegerField()
    bloques_duracion = serializers.IntegerField()
    docente = serializers.IntegerField()
    ambiente = serializers.IntegerField(allow_null=True)
    docente_substito = serializers.IntegerField(allow_null=True)

class PropuestaClasesResponseSerializer(serializers.Serializer):
    creadas = serializers.IntegerField()
    previsualizacion = ClasePreviewSerializer(many=True)
    omitidas = serializers.ListField(child=serializers.CharField())


# ====== HU012: Conflictos ======

class DetectarConflictosRequestSerializer(serializers.Serializer):
    periodo = serializers.IntegerField()
    calendario = serializers.IntegerField(required=False)
    persistir = serializers.BooleanField(default=True)  # crea registros en ConflictoHorario

class ConflictoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConflictoHorario
        fields = ["id", "tipo", "clase_a", "clase_b", "resuelto", "nota", "detectado_en"]


# ====== HU013: Cargas (horas académicas de 45') ======

class CargaDocenteItemSerializer(serializers.Serializer):
    docente = serializers.IntegerField()
    nombre = serializers.CharField()
    horas_45 = serializers.FloatField()
    carga_min_semanal = serializers.IntegerField()
    carga_max_semanal = serializers.IntegerField()
    estado = serializers.ChoiceField(choices=["BAJO", "OK", "EXCESO"])
    clases = serializers.IntegerField()

class CargaDocenteResponseSerializer(serializers.Serializer):
    periodo = serializers.IntegerField()
    calendario = serializers.IntegerField()
    items = CargaDocenteItemSerializer(many=True)


# ====== HU014: Asignación de aulas ======

class AsignarAulasRequestSerializer(serializers.Serializer):
    periodo = serializers.IntegerField()
    calendario = serializers.IntegerField()
    clase_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    prefer_edificio = serializers.IntegerField(required=False)
    force = serializers.BooleanField(default=False)  # reasignar aunque ya tenga ambiente

class AsignarAulasItemSerializer(serializers.Serializer):
    clase = serializers.IntegerField()
    ambiente_anterior = serializers.IntegerField(allow_null=True)
    ambiente_nuevo = serializers.IntegerField(allow_null=True)
    estado = serializers.ChoiceField(choices=["asignado", "sin_candidatos", "omitido", "conflicto"])

class AsignarAulasResponseSerializer(serializers.Serializer):
    asignaciones = AsignarAulasItemSerializer(many=True)


# ===== HU015: Grilla =====

class GridRequestSerializer(serializers.Serializer):
    periodo = serializers.IntegerField()
    calendario = serializers.IntegerField()
    docente = serializers.IntegerField(required=False)
    grupo = serializers.IntegerField(required=False)
    ambiente = serializers.IntegerField(required=False)
    # zoom/paginación por bloques (opcional)
    bloque_min = serializers.IntegerField(required=False)
    bloque_max = serializers.IntegerField(required=False)

class GridBloqueSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    orden = serializers.IntegerField()
    hora_inicio = serializers.TimeField()
    hora_fin = serializers.TimeField()
    duracion_min = serializers.IntegerField()

class GridCellSerializer(serializers.Serializer):
    day_of_week = serializers.IntegerField()
    bloque_inicio_orden = serializers.IntegerField()
    bloques_duracion = serializers.IntegerField()
    clase_id = serializers.IntegerField()
    grupo_id = serializers.IntegerField()
    asignatura_id = serializers.IntegerField()
    docente_id = serializers.IntegerField()
    ambiente_id = serializers.IntegerField(allow_null=True)
    asignatura = serializers.CharField()
    grupo_codigo = serializers.CharField()
    docente = serializers.CharField()
    ambiente = serializers.CharField(allow_null=True)
    tipo = serializers.CharField()  # "T" o "P"
    color = serializers.CharField() # hex sugerido por asignatura

class GridResponseSerializer(serializers.Serializer):
    calendario = serializers.IntegerField()
    periodo = serializers.IntegerField()
    dias = serializers.ListField(child=serializers.IntegerField())  # [1..5/6]
    bloques = GridBloqueSerializer(many=True)
    celdas = GridCellSerializer(many=True)


# ===== HU016/HU017: Edición de clase =====

class ClaseDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Clase
        fields = ["id","grupo","tipo","day_of_week","bloque_inicio","bloques_duracion","ambiente","docente","estado"]

class DragDropMoveRequestSerializer(serializers.Serializer):
    clase = serializers.IntegerField()
    new_day_of_week = serializers.IntegerField()
    new_bloque_inicio = serializers.IntegerField()
    new_bloques_duracion = serializers.IntegerField(required=False, default=1)
    motivo = serializers.CharField(required=False, allow_blank=True)
    dry_run = serializers.BooleanField(default=False)

class DragDropMoveResponseSerializer(serializers.Serializer):
    updated = serializers.BooleanField()
    clase = ClaseDetailSerializer()
    conflictos = serializers.ListField(child=serializers.DictField(), required=False)


class SubstitucionSuggestRequestSerializer(serializers.Serializer):
    clase = serializers.IntegerField()

class SubstitucionSuggestItemSerializer(serializers.Serializer):
    docente_id = serializers.IntegerField()
    nombre = serializers.CharField()
    carga_actual_bloques = serializers.IntegerField()

class SubstitucionSuggestResponseSerializer(serializers.Serializer):
    candidatos = SubstitucionSuggestItemSerializer(many=True)


class SubstitucionApplyRequestSerializer(serializers.Serializer):
    clase_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    grupo = serializers.IntegerField(required=False)
    nuevo_docente = serializers.IntegerField()
    motivo = serializers.CharField(required=False, allow_blank=True)

class SubstitucionApplyItemSerializer(serializers.Serializer):
    clase = serializers.IntegerField()
    status = serializers.ChoiceField(choices=["ok","conflicto","no_disp","error"])
    detalle = serializers.CharField()

class SubstitucionApplyResponseSerializer(serializers.Serializer):
    aplicados = serializers.IntegerField()
    items = SubstitucionApplyItemSerializer(many=True)


# ===== HU018: Notificaciones (salidas) =====

class NotificacionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    titulo = serializers.CharField()
    mensaje = serializers.CharField()
    leida = serializers.BooleanField()
    creada_en = serializers.DateTimeField()
    clase = serializers.IntegerField(allow_null=True)

class PrefsSerializer(serializers.Serializer):
    in_app = serializers.BooleanField(default=True)
    email = serializers.BooleanField(default=False)  # placeholder
    push = serializers.BooleanField(default=False)   # placeholder


class ClaseSubstitutoUpdateSerializer(serializers.Serializer):
    docente_substituto = serializers.IntegerField(allow_null=True, required=True)

    def validate_docente_substituto(self, value):
        if value is None:
            return None
        if not Docente.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Docente sustituto inválido.")
        return value


class ClasePreviewSerializer(serializers.ModelSerializer):
    """
    Lista compacta para la UI de sustituciones.
    Ojo: usamos el nombre de campo correcto 'docente_substituto' (con 'ti').
    """
    class Meta:
        model = Clase
        fields = [
            "id",
            "grupo",            # id
            "tipo",             # "T" / "P"
            "day_of_week",
            "bloque_inicio",    # id
            "bloques_duracion",
            "docente",          # id o null
            "ambiente",         # id o null
            "docente_substituto" # id o null
        ]