from django.http import JsonResponse
from django.views import View


class HealthView(View):
    http_method_names = ["get"]

    def get(self, request):
        return JsonResponse({"status": "ok"})
