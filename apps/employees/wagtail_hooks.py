from django.urls import path, reverse
from wagtail import hooks
from wagtail.admin.menu import MenuItem

from apps.employees import wagtail_views


@hooks.register("register_admin_urls")
def register_photo_moderation_urls():
    return [
        path(
            "photo-moderation/",
            wagtail_views.photo_moderation_index,
            name="wagtail-photo-moderation-index",
        ),
        path(
            "photo-moderation/<uuid:employee_id>/approve/",
            wagtail_views.photo_moderation_approve,
            name="wagtail-photo-moderation-approve",
        ),
        path(
            "photo-moderation/<uuid:employee_id>/reject/",
            wagtail_views.photo_moderation_reject,
            name="wagtail-photo-moderation-reject",
        ),
    ]


@hooks.register("register_admin_menu_item")
def register_photo_moderation_menu_item():
    return MenuItem(
        "Photo moderation",
        reverse("wagtail-photo-moderation-index"),
        icon_name="image",
        order=400,
    )
