from rest_framework import serializers

from apps.onboarding.models import OnboardingItem


class OnboardingItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OnboardingItem
        fields = (
            "code",
            "title",
            "body",
            "release_date",
            "audience",
        )
