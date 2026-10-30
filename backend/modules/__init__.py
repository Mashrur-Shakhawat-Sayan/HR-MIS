"""Business modules. Importing this package registers every API route.

Each module is self-contained and documents its own endpoints at the top of the file.
"""
from . import (admin, attendance, auth, claims, dashboard, employees, leave, lifecycle,  # noqa: F401
               loans, organization, payroll, reports, system, talent)
