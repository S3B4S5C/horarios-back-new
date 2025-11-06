import re
from rest_framework import serializers
from academics.models import Asignatura, Carrera, Grupo, Periodo
from django.db import transaction, models
from django.db.utils import IntegrityError

class PeriodoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Periodo
        fields = ["id", "gestion", "numero", "fecha_inicio", "fecha_fin"]


class AsignaturaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asignatura
        fields = [
            "id", "carrera", "codigo", "nombre",
            "horas_teoria_semana", "horas_practica_semana",
            "tipo_ambiente_teoria", "tipo_ambiente_practica"
        ]

    def validate(self, attrs):
        ht = attrs.get("horas_teoria_semana", getattr(
            self.instance, "horas_teoria_semana", 0))
        hp = attrs.get("horas_practica_semana", getattr(
            self.instance, "horas_practica_semana", 0))
        if ht < 0 or hp < 0:
            raise serializers.ValidationError(
                "Las horas semanales no pueden ser negativas.")
        if ht == 0 and hp == 0:
            raise serializers.ValidationError(
                "Teoría y práctica no pueden ser ambas 0.")
        return attrs


class CarreraSerializer(serializers.ModelSerializer):
    class Meta:
        model = Carrera
        fields = ["id", "sigla", "nombre", "jefe"]


class GrupoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Grupo
        fields = ["id", "asignatura", "periodo", "turno",
                  "docente", "codigo", "capacidad", "estado"]
        extra_kwargs = {
            'docente': {'allow_null': True, 'required': False},
            'codigo':  {'required': False, 'allow_blank': True},
        }

    def validate_capacidad(self, val):
        if val <= 0:
            raise serializers.ValidationError("La capacidad debe ser > 0.")
        return val

    def validate(self, attrs):
        # Solo validamos duplicado si vino 'codigo'
        asignatura = attrs.get("asignatura", getattr(
            self.instance, "asignatura", None))
        periodo = attrs.get("periodo", getattr(self.instance, "periodo", None))
        codigo = attrs.get("codigo", getattr(self.instance, "codigo", None))
        if asignatura and periodo and codigo:
            qs = Grupo.objects.filter(
                asignatura=asignatura, periodo=periodo, codigo=codigo)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    "Ya existe un grupo con esa asignatura/periodo/código.")
        return attrs

    @staticmethod
    def _letra_turno(turno_id: int) -> str:
        return {1: "A", 2: "B", 3: "C"}.get(turno_id, "X")

    @staticmethod
    def _pk_of(value):
        """
        Devuelve el pk si 'value' es instancia de modelo; si no, intenta cast a int.
        """
        if isinstance(value, models.Model):
            return value.pk
        if isinstance(value, dict) and "id" in value:
            return value["id"]
        return int(value)

    def _siguiente_codigo(self, asignatura, periodo, turno) -> str:
        """
        Calcula el siguiente código secuencial para (asignatura, periodo, turno).
        """
        turno_id = self._pk_of(turno)  # <-- sin int() anticipado
        prefix = self._letra_turno(turno_id)

        existentes = list(
            Grupo.objects.select_for_update()
            .filter(
                asignatura=asignatura,
                periodo=periodo,
                turno_id=turno_id,               # filtra por el mismo turno
                codigo__startswith=prefix
            )
            .values_list("codigo", flat=True)
        )

        max_n = 0
        pat = re.compile(rf"^{prefix}(\d+)$")
        for c in existentes:
            m = pat.match(c or "")
            if m:
                max_n = max(max_n, int(m.group(1)))
        return f"{prefix}{max_n + 1}"

    def create(self, validated_data):
        if not validated_data.get("codigo"):
            asig = validated_data["asignatura"]
            per  = validated_data["periodo"]
            tur  = validated_data["turno"]
            for _ in range(2):
                try:
                    with transaction.atomic():
                        validated_data["codigo"] = self._siguiente_codigo(asig, per, tur)
                        return super().create(validated_data)
                except IntegrityError:
                    continue
        return super().create(validated_data)


class SugerenciaGruposResponseSerializer(serializers.Serializer):
    asignatura = serializers.IntegerField()
    periodo = serializers.IntegerField()
    turno = serializers.IntegerField()
    preinscritos = serializers.IntegerField()
    grupos_sugeridos = serializers.IntegerField()
    codigos_sugeridos = serializers.ListField(child=serializers.CharField())


class GrupoBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Grupo
        fields = ["id", "asignatura", "periodo", "turno",
                  "docente", "codigo", "capacidad", "estado"]
        extra_kwargs = {
            'docente': {'allow_null': True, 'required': False}
        }


class GrupoBulkItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Grupo
        fields = ["asignatura", "periodo", "turno",
                  "docente", "codigo", "capacidad", "estado"]


class GrupoBulkCreateRequestSerializer(serializers.Serializer):
    items = GrupoBulkItemSerializer(many=True)
