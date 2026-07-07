from django.urls import path

from apps.employees.views import (
    AdminEmployeeDetailView,
    AdminPhotoModerationApproveView,
    AdminPhotoModerationListView,
    AdminPhotoModerationRejectView,
    EmployeeDetailView,
    ProfileMeView,
    ProfilePhotoUploadView,
)

urlpatterns = [
    path("profile/me/", ProfileMeView.as_view(), name="profile-me"),
    path(
        "profile/me/photo/",
        ProfilePhotoUploadView.as_view(),
        name="profile-photo-upload",
    ),
    path("employees/<uuid:id>/", EmployeeDetailView.as_view(), name="employee-detail"),
    path(
        "admin/employees/<uuid:id>/",
        AdminEmployeeDetailView.as_view(),
        name="admin-employee-detail",
    ),
    path(
        "admin/photo-moderation/",
        AdminPhotoModerationListView.as_view(),
        name="admin-photo-moderation-list",
    ),
    path(
        "admin/photo-moderation/<uuid:employee_id>/approve/",
        AdminPhotoModerationApproveView.as_view(),
        name="admin-photo-moderation-approve",
    ),
    path(
        "admin/photo-moderation/<uuid:employee_id>/reject/",
        AdminPhotoModerationRejectView.as_view(),
        name="admin-photo-moderation-reject",
    ),
]
