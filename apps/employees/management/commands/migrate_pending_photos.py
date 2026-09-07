from django.core.files import File
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError

from apps.employees.models import Employee
from apps.employees.storage import PrivatePendingPhotoStorage


class Command(BaseCommand):
    help = "Copy legacy pending photos from public media to private storage."

    def add_arguments(self, parser):
        parser.add_argument(
            "--delete-source",
            action="store_true",
            help="Delete each public source file only after a successful copy.",
        )

    def handle(self, *args, **options):
        private_storage = PrivatePendingPhotoStorage()
        copied_count = 0
        deleted_count = 0
        employees = Employee.objects.exclude(pending_photo="").order_by("pk")

        for employee in employees.iterator():
            name = employee.pending_photo.name

            if not private_storage.private_exists(name) and not default_storage.exists(
                name,
            ):
                raise CommandError(
                    f"Public source file is missing for employee {employee.pk}.",
                )

        for employee in employees.iterator():
            name = employee.pending_photo.name

            if not private_storage.private_exists(name):
                with default_storage.open(name, "rb") as source_file:
                    private_storage.save(name, File(source_file, name=name))
                copied_count += 1

            if options["delete_source"] and default_storage.exists(name):
                default_storage.delete(name)
                deleted_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Pending photo migration complete: {copied_count} copied, "
                f"{deleted_count} public source files deleted.",
            ),
        )
