from rest_framework import serializers

from apps.org.models import Department


class DepartmentBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = (
            "code",
            "name",
        )
