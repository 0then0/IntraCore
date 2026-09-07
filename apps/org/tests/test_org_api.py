from datetime import date
from io import StringIO

import pytest
from django.core.exceptions import ValidationError
from django.core.management import CommandError, call_command
from django.db import IntegrityError, transaction
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.employees.models import Employee
from apps.org.models import Department

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


def create_user(django_user_model, *, username: str):
    return django_user_model.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="password",
    )


def create_employee(
    django_user_model,
    *,
    login: str,
    department: Department | None = None,
    manager: Employee | None = None,
    hrbp: Employee | None = None,
    first_name: str = "First",
    last_name: str = "Last",
    email: str | None = None,
    is_active: bool = True,
    phone: str = "+79990000000",
    is_phone_visible: bool = True,
    birthdate: date | None = date(1990, 5, 20),
    is_birthdate_visible: bool = True,
) -> Employee:
    user = create_user(django_user_model, username=login)

    return Employee.objects.create(
        user=user,
        email=email or f"{login}@example.com",
        login=login,
        first_name=first_name,
        last_name=last_name,
        department=department,
        manager=manager,
        hrbp=hrbp,
        phone=phone,
        is_phone_visible=is_phone_visible,
        birthdate=birthdate,
        is_birthdate_visible=is_birthdate_visible,
        hired_at=date(2020, 1, 10),
        is_active=is_active,
    )


def authenticate(api_client, django_user_model):
    viewer = create_employee(
        django_user_model,
        login="viewer",
        first_name="Viewer",
        last_name="Person",
    )
    api_client.force_authenticate(user=viewer.user)

    return viewer


def test_departments_list_returns_paginated_shape(api_client, django_user_model):
    root = Department.objects.create(code="engineering", name="Engineering")
    child = Department.objects.create(
        code="platform",
        name="Platform",
        parent=root,
    )
    create_employee(django_user_model, login="active", department=child)
    create_employee(
        django_user_model,
        login="inactive",
        department=child,
        is_active=False,
    )
    authenticate(api_client, django_user_model)

    response = api_client.get(reverse("org-department-list"))

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["count"] == 2
    platform = next(item for item in data["results"] if item["code"] == "platform")
    assert platform == {
        "code": "platform",
        "name": "Platform",
        "parent": {"code": "engineering", "name": "Engineering"},
        "employee_count": 1,
    }


def test_org_structure_returns_nested_departments(api_client, django_user_model):
    root = Department.objects.create(code="engineering", name="Engineering")
    child = Department.objects.create(
        code="platform",
        name="Platform",
        parent=root,
    )
    Department.objects.create(code="backend", name="Backend", parent=child)
    create_employee(django_user_model, login="root-employee", department=root)
    create_employee(django_user_model, login="child-employee", department=child)
    authenticate(api_client, django_user_model)

    response = api_client.get(reverse("org-structure"))

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data == [
        {
            "code": "engineering",
            "name": "Engineering",
            "employee_count": 1,
            "children": [
                {
                    "code": "platform",
                    "name": "Platform",
                    "employee_count": 1,
                    "children": [
                        {
                            "code": "backend",
                            "name": "Backend",
                            "employee_count": 0,
                            "children": [],
                        },
                    ],
                },
            ],
        },
    ]


def test_org_employees_searches_by_name_and_email(api_client, django_user_model):
    authenticate(api_client, django_user_model)
    create_employee(
        django_user_model,
        login="ada",
        first_name="Ada",
        last_name="Lovelace",
        email="ada.lovelace@example.com",
    )
    create_employee(
        django_user_model,
        login="grace",
        first_name="Grace",
        last_name="Hopper",
        email="grace.hopper@example.com",
    )

    name_response = api_client.get(reverse("org-employee-list"), {"search": "Ada"})
    email_response = api_client.get(
        reverse("org-employee-list"),
        {"search": "hopper@example.com"},
    )

    assert name_response.status_code == status.HTTP_200_OK
    assert email_response.status_code == status.HTTP_200_OK
    assert [item["login"] for item in name_response.json()["results"]] == ["ada"]
    assert [item["login"] for item in email_response.json()["results"]] == ["grace"]


def test_org_employees_filter_by_direct_department(api_client, django_user_model):
    engineering = Department.objects.create(code="engineering", name="Engineering")
    people = Department.objects.create(code="people", name="People")
    authenticate(api_client, django_user_model)
    create_employee(django_user_model, login="engineer", department=engineering)
    create_employee(django_user_model, login="hrbp", department=people)

    response = api_client.get(
        reverse("org-employee-list"),
        {"department": "engineering"},
    )

    assert response.status_code == status.HTTP_200_OK
    assert [item["login"] for item in response.json()["results"]] == ["engineer"]


def test_org_employees_are_paginated(api_client, django_user_model):
    authenticate(api_client, django_user_model)
    create_employee(django_user_model, login="employee-1", last_name="Alpha")
    create_employee(django_user_model, login="employee-2", last_name="Beta")
    create_employee(django_user_model, login="employee-3", last_name="Gamma")

    response = api_client.get(reverse("org-employee-list"), {"page_size": 2})

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["count"] == 4
    assert len(data["results"]) == 2
    assert data["next"] is not None


def test_org_employee_list_includes_manager_and_hrbp(api_client, django_user_model):
    manager = create_employee(django_user_model, login="manager")
    hrbp = create_employee(django_user_model, login="hrbp")
    authenticate(api_client, django_user_model)
    employee = create_employee(
        django_user_model,
        login="employee",
        manager=manager,
        hrbp=hrbp,
    )

    response = api_client.get(
        reverse("org-employee-list"),
        {"search": employee.email},
    )

    assert response.status_code == status.HTTP_200_OK
    employee_data = response.json()["results"][0]
    assert employee_data["manager"]["id"] == str(manager.employee_uuid)
    assert employee_data["hrbp"]["id"] == str(hrbp.employee_uuid)


def test_org_employee_nested_manager_hidden_birthdate_stays_hidden(
    api_client,
    django_user_model,
):
    manager = create_employee(
        django_user_model,
        login="manager",
        phone="+79991112233",
        is_phone_visible=False,
        birthdate=date(1975, 3, 1),
        is_birthdate_visible=False,
    )
    authenticate(api_client, django_user_model)
    employee = create_employee(
        django_user_model,
        login="employee",
        manager=manager,
        first_name="Employee",
        last_name="Target",
    )

    response = api_client.get(
        reverse("org-employee-list"),
        {"search": employee.email},
    )

    assert response.status_code == status.HTTP_200_OK
    manager_data = response.json()["results"][0]["manager"]
    assert manager_data["phone"] is None
    assert manager_data["birthdate"] is None


def test_org_employee_list_rejects_invalid_query_params(api_client, django_user_model):
    authenticate(api_client, django_user_model)

    response = api_client.get(reverse("org-employee-list"), {"search": "a" * 101})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "search" in response.json()


def test_anonymous_user_cannot_read_org_endpoints(api_client):
    department_response = api_client.get(reverse("org-department-list"))
    structure_response = api_client.get(reverse("org-structure"))
    employees_response = api_client.get(reverse("org-employee-list"))

    assert department_response.status_code == status.HTTP_401_UNAUTHORIZED
    assert structure_response.status_code == status.HTTP_401_UNAUTHORIZED
    assert employees_response.status_code == status.HTTP_401_UNAUTHORIZED


def test_org_employee_list_uses_bounded_queries(
    api_client,
    django_user_model,
    django_assert_num_queries,
):
    engineering = Department.objects.create(code="engineering", name="Engineering")
    manager = create_employee(
        django_user_model, login="manager", department=engineering
    )
    hrbp = create_employee(django_user_model, login="hrbp", department=engineering)
    authenticate(api_client, django_user_model)
    create_employee(
        django_user_model,
        login="employee-1",
        department=engineering,
        manager=manager,
        hrbp=hrbp,
    )
    create_employee(
        django_user_model,
        login="employee-2",
        department=engineering,
        manager=manager,
        hrbp=hrbp,
    )

    with django_assert_num_queries(3):
        response = api_client.get(reverse("org-employee-list"), {"page_size": 10})

    assert response.status_code == status.HTTP_200_OK


def test_org_structure_uses_single_query(
    api_client,
    django_user_model,
    django_assert_num_queries,
):
    root = Department.objects.create(code="engineering", name="Engineering")
    Department.objects.create(code="platform", name="Platform", parent=root)
    authenticate(api_client, django_user_model)

    with django_assert_num_queries(1):
        response = api_client.get(reverse("org-structure"))

    assert response.status_code == status.HTTP_200_OK


def test_openapi_schema_contains_org_paths(api_client):
    response = api_client.get(reverse("schema"))

    assert response.status_code == status.HTTP_200_OK
    schema = response.content.decode()
    assert "/api/org/departments/" in schema
    assert "/api/org/structure/" in schema
    assert "/api/org/employees/" in schema


def test_seed_org_data_command_is_idempotent():
    stdout = StringIO()

    call_command(
        "seed_org_data",
        employees=5,
        departments=3,
        batch_size=2,
        stdout=stdout,
    )
    call_command(
        "seed_org_data",
        employees=5,
        departments=3,
        batch_size=2,
        stdout=stdout,
    )

    assert Department.objects.filter(code__startswith="seed-dept-").count() == 3
    seed_employees = Employee.objects.filter(
        external_id__startswith="seed-employee-",
    )
    assert seed_employees.count() == 5
    assert seed_employees.exclude(manager__isnull=True).exists()
    assert seed_employees.exclude(hrbp__isnull=True).exists()


def test_department_cannot_be_its_own_parent():
    department = Department.objects.create(code="engineering", name="Engineering")
    department.parent = department

    with pytest.raises(ValidationError) as error:
        department.full_clean()

    assert "parent" in error.value.message_dict


def test_department_clean_rejects_multi_department_cycle():
    parent = Department.objects.create(code="parent", name="Parent")
    child = Department.objects.create(code="child", name="Child", parent=parent)
    parent.parent = child

    with pytest.raises(ValidationError) as error:
        parent.full_clean()

    assert "parent" in error.value.message_dict


def test_database_rejects_department_cycle_when_model_validation_is_bypassed():
    parent = Department.objects.create(code="parent", name="Parent")
    child = Department.objects.create(code="child", name="Child", parent=parent)

    with pytest.raises(IntegrityError), transaction.atomic():
        Department.objects.filter(pk=parent.pk).update(parent=child)


def test_seed_org_data_rejects_email_or_login_collision():
    Employee.objects.create(
        external_id="custom-id",
        email="seed.employee.00000@seed.intracore.local",
        login="custom-login",
        first_name="Existing",
        last_name="Employee",
    )

    with pytest.raises(CommandError, match="Seed employee email or login conflicts"):
        call_command("seed_org_data", employees=1, departments=1)
