from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError

from apps.employees.models import Employee
from apps.org.models import Department

DEFAULT_DEPARTMENT_COUNT = 40
DEFAULT_EMPLOYEE_COUNT = 10_000
DEFAULT_BATCH_SIZE = 1_000
SEED_EMAIL_DOMAIN = "seed.intracore.local"


class Command(BaseCommand):
    help = "Create nested departments and employees for org performance testing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--employees",
            type=int,
            default=DEFAULT_EMPLOYEE_COUNT,
            help="Number of seed employees to ensure.",
        )
        parser.add_argument(
            "--departments",
            type=int,
            default=DEFAULT_DEPARTMENT_COUNT,
            help="Number of nested seed departments to ensure.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH_SIZE,
            help="bulk_create and bulk_update batch size.",
        )

    def handle(self, *args, **options):
        employee_count = options["employees"]
        department_count = options["departments"]
        batch_size = options["batch_size"]

        if employee_count < 1:
            raise CommandError("--employees must be greater than zero.")
        if department_count < 1:
            raise CommandError("--departments must be greater than zero.")
        if batch_size < 1:
            raise CommandError("--batch-size must be greater than zero.")

        departments = self._ensure_departments(department_count)
        created_count = self._ensure_employees(
            employee_count=employee_count,
            departments=departments,
            batch_size=batch_size,
        )
        updated_count = self._ensure_employee_relations(batch_size=batch_size)

        self.stdout.write(
            self.style.SUCCESS(
                "Seed data ready: "
                f"{len(departments)} departments, "
                f"{employee_count} target employees, "
                f"{created_count} employees created, "
                f"{updated_count} employee relations updated.",
            ),
        )

    def _ensure_departments(self, department_count: int) -> list[Department]:
        departments_by_number = {}

        for number in range(department_count):
            code = _department_code(number)
            parent = None
            if number > 0:
                parent = departments_by_number[(number - 1) // 3]

            department, created = Department.objects.get_or_create(
                code=code,
                defaults={
                    "name": f"Seed Department {number:03d}",
                    "parent": parent,
                },
            )
            if not created and (
                department.name != f"Seed Department {number:03d}"
                or department.parent_id != _department_parent_id(parent)
            ):
                department.name = f"Seed Department {number:03d}"
                department.parent = parent
                department.save(update_fields=["name", "parent", "updated_at"])

            departments_by_number[number] = department

        return [departments_by_number[number] for number in range(department_count)]

    def _ensure_employees(
        self,
        *,
        employee_count: int,
        departments: list[Department],
        batch_size: int,
    ) -> int:
        expected_external_ids = [
            _employee_external_id(number) for number in range(employee_count)
        ]
        existing_external_ids = set(
            Employee.objects.filter(
                external_id__in=expected_external_ids,
            ).values_list("external_id", flat=True),
        )
        employees_to_create = []
        created_count = 0

        for number in range(employee_count):
            external_id = _employee_external_id(number)
            if external_id in existing_external_ids:
                continue

            department = departments[number % len(departments)]
            employees_to_create.append(
                Employee(
                    external_id=external_id,
                    email=f"seed.employee.{number:05d}@{SEED_EMAIL_DOMAIN}",
                    login=f"seed.employee.{number:05d}",
                    first_name=f"SeedFirst{number:05d}",
                    last_name=f"SeedLast{number:05d}",
                    middle_name=f"SeedMiddle{number % 100:02d}",
                    position=f"Engineer {number % 12}",
                    department=department,
                    phone=f"+100000{number:05d}",
                    is_phone_visible=number % 4 == 0,
                    birthdate=date(1980, 1, 1) + timedelta(days=number % 7000),
                    is_birthdate_visible=number % 6 == 0,
                    telegram_username=f"seed_employee_{number:05d}",
                    city=f"Seed City {number % 20:02d}",
                    about="Seed employee for org endpoint performance checks.",
                    hobbies="Backend practice data.",
                    education="Seed University",
                    hired_at=date(2018, 1, 1) + timedelta(days=number % 2000),
                    is_active=True,
                ),
            )

            if len(employees_to_create) >= batch_size:
                Employee.objects.bulk_create(employees_to_create, batch_size=batch_size)
                created_count += len(employees_to_create)
                employees_to_create = []

        if employees_to_create:
            Employee.objects.bulk_create(employees_to_create, batch_size=batch_size)
            created_count += len(employees_to_create)

        return created_count

    def _ensure_employee_relations(self, *, batch_size: int) -> int:
        seed_employees = list(
            Employee.objects.filter(
                external_id__startswith="seed-employee-",
            )
            .only("id", "department_id", "external_id", "manager_id", "hrbp_id")
            .order_by("department_id", "external_id"),
        )
        if not seed_employees:
            return 0

        hrbp_id = seed_employees[0].pk
        manager_by_department_id = {}
        employees_to_update = []

        for employee in seed_employees:
            manager_id = manager_by_department_id.setdefault(
                employee.department_id,
                employee.pk,
            )
            next_manager_id = None if employee.pk == manager_id else manager_id
            next_hrbp_id = None if employee.pk == hrbp_id else hrbp_id

            if (
                employee.manager_id == next_manager_id
                and employee.hrbp_id == next_hrbp_id
            ):
                continue

            employee.manager_id = next_manager_id
            employee.hrbp_id = next_hrbp_id
            employees_to_update.append(employee)

        if employees_to_update:
            Employee.objects.bulk_update(
                employees_to_update,
                ["manager", "hrbp"],
                batch_size=batch_size,
            )

        return len(employees_to_update)


def _department_code(number: int) -> str:
    return f"seed-dept-{number:03d}"


def _department_parent_id(parent: Department | None) -> int | None:
    if parent is None:
        return None

    return parent.pk


def _employee_external_id(number: int) -> str:
    return f"seed-employee-{number:05d}"
