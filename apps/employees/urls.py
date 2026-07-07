from django.urls import path

from apps.employees.views import (
    AdminEmployeeDetailView,
    EmployeeDetailView,
    ProfileMeView,
)

urlpatterns = [
    path("profile/me/", ProfileMeView.as_view(), name="profile-me"),
    path("employees/<uuid:id>/", EmployeeDetailView.as_view(), name="employee-detail"),
    path(
        "admin/employees/<uuid:id>/",
        AdminEmployeeDetailView.as_view(),
        name="admin-employee-detail",
    ),
]
