from rest_framework import serializers
from facilities.models import Edificio, TipoAmbiente, Ambiente

class EdificioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Edificio
        fields = ["id", "codigo", "nombre", "ubicacion"]

class TipoAmbienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoAmbiente
        fields = ["id", "nombre", "descripcion"]

class AmbienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ambiente
        fields = ["id", "edificio", "tipo_ambiente", "codigo", "nombre", "capacidad"]

    def validate_capacidad(self, value):
        if value <= 0:
            raise serializers.ValidationError("La capacidad debe ser > 0.")
        return value

    def validate(self, attrs):
        edificio = attrs.get("edificio", getattr(self.instance, "edificio", None))
        codigo = attrs.get("codigo", getattr(self.instance, "codigo", None))
        if edificio and codigo:
            qs = Ambiente.objects.filter(edificio=edificio, codigo=codigo)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError("Ya existe un ambiente con ese código en el edificio.")
        return attrs
