from rest_framework import serializers


class HealthResponseSerializer(serializers.Serializer):
    status = serializers.CharField()


class DetailErrorSerializer(serializers.Serializer):
    detail = serializers.CharField()


class CodeDetailErrorSerializer(serializers.Serializer):
    code = serializers.CharField()
    detail = serializers.CharField()
