from datetime import datetime, timedelta
from typing import Any, Dict, List

from django.utils import timezone
from rest_framework import serializers

from academics.models import Asignatura
from scheduling.models import Clase


# ----------------- MINI / AUX -----------------

class HorasDetalleSerializer(serializers.Serializer):
    bloques = serializers.IntegerField()
    minutos = serializers.IntegerField()
    horas = serializers.FloatField()


class AsignaturaMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asignatura
        fields = ("id", "codigo", "nombre")


# ----------------- PLANIFICACION -----------------

class GrupoPlanificacionSerializer(serializers.Serializer):
    # Identificación de grupo y mini asignatura
    grupo = serializers.IntegerField()
    codigo = serializers.CharField(allow_null=True)
    periodo = serializers.IntegerField()
    turno = serializers.IntegerField()
    asignatura = AsignaturaMiniSerializer()

    # Requeridos y programado
    requeridos = serializers.SerializerMethodField()
    programado = serializers.SerializerMethodField()
    estado = serializers.SerializerMethodField()

    def _minutos_a_horas(self, minutos: int) -> float:
        return round(minutos / 60.0, 2)

    def get_requeridos(self, obj) -> Dict[str, Any]:
        teo_h = float(getattr(obj.asignatura, "horas_teoria_semana", 0) or 0)
        pra_h = float(getattr(obj.asignatura, "horas_practica_semana", 0) or 0)
        return {
            "teoria_horas_semana": teo_h,
            "practica_horas_semana": pra_h,
        }

    def get_programado(self, obj) -> Dict[str, Any]:
        mt = int(getattr(obj, "minutos_teo", 0) or 0)
        mp = int(getattr(obj, "minutos_pra", 0) or 0)
        bt = int(getattr(obj, "bloques_teo", 0) or 0)
        bp = int(getattr(obj, "bloques_pra", 0) or 0)
        return {
            "teoria": {"bloques": bt, "minutos": mt, "horas": self._minutos_a_horas(mt)},
            "practica": {"bloques": bp, "minutos": mp, "horas": self._minutos_a_horas(mp)},
        }

    def get_estado(self, obj) -> Dict[str, str]:
        tolerancia_min = int(self.context.get("tolerancia_min", 0) or 0)

        req_teo_h = float(getattr(obj.asignatura, "horas_teoria_semana", 0) or 0)
        req_pra_h = float(getattr(obj.asignatura, "horas_practica_semana", 0) or 0)
        req_teo_min = int(req_teo_h * 60)
        req_pra_min = int(req_pra_h * 60)

        prog_teo_min = int(getattr(obj, "minutos_teo", 0) or 0)
        prog_pra_min = int(getattr(obj, "minutos_pra", 0) or 0)

        def cmp(prog, req):
            if prog < req - tolerancia_min:
                return "BAJO"
            if prog > req + tolerancia_min:
                return "EXCESO"
            return "OK"

        return {"teoria": cmp(prog_teo_min, req_teo_min), "practica": cmp(prog_pra_min, req_pra_min)}


# ----------------- CLASES: DETAIL + LABELS -----------------

class ClaseDetailSerializer(serializers.ModelSerializer):
    """Detalle base de clase."""
    class Meta:
        model = Clase
        fields = (
            "id",
            "grupo",
            "tipo",
            "day_of_week",
            "bloque_inicio",
            "bloques_duracion",
            "ambiente",
            "docente",
            "estado",
        )


class ClaseLabelsSerializer(serializers.Serializer):
    asignatura = serializers.CharField()
    grupo = serializers.CharField(allow_null=True)
    docente = serializers.CharField(allow_null=True, required=False)
    ambiente = serializers.CharField(allow_null=True)
    bloque_inicio_orden = serializers.IntegerField()
    rango_hora = serializers.CharField()


class ClaseWithLabelsSerializer(ClaseDetailSerializer):
    """
    Extiende el detalle de Clase agregando un objeto `labels` con metadatos
    (asignatura, grupo, docente, ambiente, orden y rango horario).
    """
    labels = serializers.SerializerMethodField()

    class Meta(ClaseDetailSerializer.Meta):
        # >>> FIX PRINCIPAL: incluir 'labels' en fields <<<
        fields = ClaseDetailSerializer.Meta.fields + ("labels",)

    def get_labels(self, obj) -> Dict[str, Any]:
        asig = obj.grupo.asignatura
        grupo_codigo = obj.grupo.codigo
        docente = obj.docente.nombre_completo if obj.docente_id else None
        ambiente = obj.ambiente.codigo if obj.ambiente_id else None

        orden = obj.bloque_inicio.orden
        ini = obj.bloque_inicio.hora_inicio  # datetime.time
        dur_total_min = obj.bloque_inicio.duracion_min * obj.bloques_duracion

        dt_ini = datetime.combine(timezone.now().date(), ini)
        dt_fin = dt_ini + timedelta(minutes=dur_total_min)
        rango = f"{dt_ini.strftime('%H:%M')}–{dt_fin.strftime('%H:%M')}"

        return {
            "asignatura": f"{asig.codigo} · {asig.nombre}",
            "grupo": (grupo_codigo or None),
            "docente": docente,
            "ambiente": ambiente,
            "bloque_inicio_orden": orden,
            "rango_hora": rango,
        }


# ----------------- BULK: REQUEST -----------------

class ClaseCreateItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Clase
        fields = (
            "grupo",
            "tipo",
            "day_of_week",
            "bloque_inicio",
            "bloques_duracion",
            "ambiente",
            "docente",   # opcional
            "estado",
        )
        # >>> docente NO es requerido y permite null <<<
        extra_kwargs = {
            "docente": {"required": False, "allow_null": True},
        }


class ClaseBulkCreateRequestSerializer(serializers.Serializer):
    items = ClaseCreateItemSerializer(many=True)


class ClaseBulkUpdateItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    set = serializers.DictField(child=serializers.JSONField())

    def validate_set(self, value):
        allowed = {
            "grupo", "tipo", "day_of_week", "bloque_inicio",
            "bloques_duracion", "ambiente", "docente", "estado",
        }
        for k in value.keys():
            if k not in allowed:
                raise serializers.ValidationError(f"Campo no permitido: {k}")
        return value


class ClaseBulkUpdateRequestSerializer(serializers.Serializer):
    updates = ClaseBulkUpdateItemSerializer(many=True)


class ClaseBulkDeleteRequestSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)


# ----------------- BULK: RESPONSE ENVELOPES (para documentación) -----------------

class BulkCreateResponseSerializer(serializers.Serializer):
    created = serializers.IntegerField()
    items = ClaseDetailSerializer(many=True)
    conflicts = serializers.ListField(child=serializers.DictField())


class BulkUpdateResponseSerializer(serializers.Serializer):
    updated = serializers.IntegerField()
    items = ClaseDetailSerializer(many=True)
    errors = serializers.ListField(child=serializers.DictField())


class BulkDeleteResponseSerializer(serializers.Serializer):
    deleted = serializers.IntegerField()
    not_found = serializers.ListField(child=serializers.IntegerField())
