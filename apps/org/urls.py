from django.urls import path

from apps.org.views import (
    DepartmentListView,
    DepartmentStructureView,
    OrgEmployeeListView,
)

urlpatterns = [
    path("departments/", DepartmentListView.as_view(), name="org-department-list"),
    path("structure/", DepartmentStructureView.as_view(), name="org-structure"),
    path("employees/", OrgEmployeeListView.as_view(), name="org-employee-list"),
]
