from collections import defaultdict

from django.db.models import Count, Q, QuerySet

from apps.employees.models import Employee
from apps.org.models import Department


def department_list_queryset() -> QuerySet[Department]:
    return (
        Department.objects.select_related("parent")
        .annotate(
            active_employee_count=Count(
                "employee",
                filter=Q(employee__is_active=True),
            ),
        )
        .order_by("name", "code")
    )


def department_structure_queryset() -> QuerySet[Department]:
    return (
        Department.objects.annotate(
            active_employee_count=Count(
                "employee",
                filter=Q(employee__is_active=True),
            ),
        )
        .only("id", "code", "name", "parent_id")
        .order_by("name", "code")
    )


def get_department_structure() -> list[dict]:
    departments = list(department_structure_queryset())
    nodes_by_id = {}
    children_by_parent_id = defaultdict(list)

    for department in departments:
        node = {
            "code": department.code,
            "name": department.name,
            "employee_count": department.active_employee_count,
            "children": [],
        }
        nodes_by_id[department.pk] = node
        children_by_parent_id[department.parent_id].append(node)

    for department in departments:
        nodes_by_id[department.pk]["children"] = children_by_parent_id[department.pk]

    return children_by_parent_id[None]


def org_employee_queryset() -> QuerySet[Employee]:
    return (
        Employee.objects.filter(is_active=True)
        .select_related(
            "department",
            "manager",
            "manager__department",
            "hrbp",
            "hrbp__department",
        )
        .order_by("last_name", "first_name", "employee_uuid")
    )


def filter_org_employees(
    queryset: QuerySet[Employee],
    *,
    search: str = "",
    department: str = "",
) -> QuerySet[Employee]:
    if department:
        queryset = queryset.filter(department__code=department)

    terms = [term for term in search.split() if term]
    for term in terms:
        queryset = queryset.filter(
            Q(first_name__icontains=term)
            | Q(last_name__icontains=term)
            | Q(middle_name__icontains=term)
            | Q(email__icontains=term)
            | Q(login__icontains=term),
        )

    return queryset
