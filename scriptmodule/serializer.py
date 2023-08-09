from .models import *
from rest_framework import serializers

from .utils import token_validator


class ScriptSerializer(serializers.ModelSerializer):
    class Meta:
        model = Script
        fields = '__all__'
        # read_only_fields = ['script_uuid', 'created_by', 'updated_on', 'created_on']

    # def create(self, validated_data):
    #     return super().create(validated_data)
