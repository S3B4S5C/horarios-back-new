from rest_framework import serializers
from notifications.models import Notificacion

class NotificacionModelSerializer(serializers.ModelSerializer):
    clase = serializers.IntegerField(source="clase_id", allow_null=True)
    class Meta:
        model = Notificacion
        fields = ["id","titulo","mensaje","leida","creada_en","clase"]
