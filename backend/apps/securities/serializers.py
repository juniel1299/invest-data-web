from rest_framework import serializers

from .models import Security


class SecuritySerializer(serializers.ModelSerializer):
    class Meta:
        model = Security
        fields = ["ticker", "name", "name_ko", "exchange"]
