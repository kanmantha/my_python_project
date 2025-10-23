# hospital_single.py
"""
Single-file Django app that programmatically ensures a hospital_app package exists
so INSTALLED_APPS can include 'hospital_app' without raising ModuleNotFoundError.
Includes admin and runs migrations programmatically.

Run:
  python -m pip install django
  python hospital_single.py runserver 0.0.0.0:8000
  python hospital_single.py createsuperuser
"""

import os
import sys
import textwrap

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "db.sqlite3")
APP_DIR = os.path.join(BASE_DIR, "hospital_app")

# --- If hospital_app package not present, create it with models and apps ---
if not os.path.isdir(APP_DIR):
    os.makedirs(APP_DIR, exist_ok=True)

# Write __init__.py (keeps simple)
init_path = os.path.join(APP_DIR, "__init__.py")
if not os.path.exists(init_path):
    with open(init_path, "w", encoding="utf-8") as f:
        f.write("# hospital_app package created by hospital_single.py\n")

# Write apps.py defining AppConfig for hospital_app
apps_path = os.path.join(APP_DIR, "apps.py")
apps_contents = textwrap.dedent(
    """
    from django.apps import AppConfig

    class HospitalAppConfig(AppConfig):
        default_auto_field = 'django.db.models.BigAutoField'
        name = 'hospital_app'
        label = 'hospital_app'
    """
)
if not os.path.exists(apps_path):
    with open(apps_path, "w", encoding="utf-8") as f:
        f.write(apps_contents)

# Write models.py for hospital_app (Patient, Appointment)
models_path = os.path.join(APP_DIR, "models.py")
models_contents = textwrap.dedent(
    """
    from django.db import models

    class Patient(models.Model):
        first_name = models.CharField(max_length=120)
        last_name = models.CharField(max_length=120)
        dob = models.DateField(null=True, blank=True)

        class Meta:
            app_label = "hospital_app"
            db_table = "hospital_patient"

        def __str__(self):
            return f"{self.first_name} {self.last_name}"

    class Appointment(models.Model):
        patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="appointments")
        appointment_date = models.DateField()
        notes = models.TextField(blank=True)

        class Meta:
            app_label = "hospital_app"
            db_table = "hospital_appointment"

        def __str__(self):
            return f"Appointment for {self.patient} on {self.appointment_date}"
    """
)
# Overwrite models.py only if it doesn't exist or differs
write_models = True
if os.path.exists(models_path):
    with open(models_path, "r", encoding="utf-8") as f:
        existing = f.read()
    if existing.strip() == models_contents.strip():
        write_models = False

if write_models:
    with open(models_path, "w", encoding="utf-8") as f:
        f.write(models_contents)

# --- Django settings ---
SETTINGS_DICT = {
    "DEBUG": True,
    "SECRET_KEY": "dev-single-file-hospital-admin-secret",
    "ALLOWED_HOSTS": ["*"],
    "INSTALLED_APPS": [
        "django.contrib.admin",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.sessions",
        "django.contrib.messages",
        "django.contrib.staticfiles",
        "hospital_app",  # now importable because we created package files above
    ],
    "MIDDLEWARE": [
        "django.middleware.security.SecurityMiddleware",
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.middleware.common.CommonMiddleware",
        "django.middleware.csrf.CsrfViewMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "django.contrib.messages.middleware.MessageMiddleware",
    ],
    "ROOT_URLCONF": "__main__",
    "TEMPLATES": [
        {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "APP_DIRS": True,  # admin templates come from contrib apps
            "DIRS": [os.path.join(BASE_DIR, "templates")],
            "OPTIONS": {
                "context_processors": [
                    "django.template.context_processors.debug",
                    "django.template.context_processors.request",
                    "django.contrib.auth.context_processors.auth",
                    "django.contrib.messages.context_processors.messages",
                ],
            },
        }
    ],
    "DATABASES": {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": DB_PATH,
        }
    },
    "STATIC_URL": "/static/",
    "USE_TZ": True,
    "TIME_ZONE": "UTC",
    "AUTH_PASSWORD_VALIDATORS": [],
}

# Apply settings
from django.conf import settings as django_settings

if not django_settings.configured:
    django_settings.configure(**SETTINGS_DICT)

# Ensure templates dir exists for index template
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
os.makedirs(TEMPLATE_DIR, exist_ok=True)
INDEX_TEMPLATE = os.path.join(TEMPLATE_DIR, "simple_index.html")
if not os.path.exists(INDEX_TEMPLATE):
    with open(INDEX_TEMPLATE, "w", encoding="utf-8") as f:
        f.write(
            """<!doctype html>
<html><head><meta charset="utf-8"><title>Hospital Single-file App</title></head>
<body>
  <h1>Hospital Single-file App (Admin enabled)</h1>
  <p><a href="/admin/">Go to admin</a></p>
  <p>If you don't have a superuser: <code>python hospital_single.py createsuperuser</code></p>
</body></html>"""
        )

# --- Setup Django now that hospital_app package exists ---
import django

try:
    django.setup()
except Exception as e:
    # Helpful debug message
    print("Error during django.setup():", e)
    raise

# --- Run built-in migrations so admin/auth/contenttypes exist ---
from django.core.management import call_command

try:
    call_command("migrate", "--noinput", verbosity=1)
except Exception as e:
    print("Error running migrate:", e)
    raise

# --- Import programmatic models (they live in hospital_app.models) ---
# Import models from the created package
from hospital_app.models import Patient, Appointment  # type: ignore

# Ensure our programmatic models' tables exist if not created by migrations
from django.db import connection

with connection.schema_editor() as schema_editor:
    for model in (Patient, Appointment):
        table = model._meta.db_table
        if table not in connection.introspection.table_names():
            schema_editor.create_model(model)
            print("Created table:", table)

# --- Register models in admin ---
from django.contrib import admin

class PatientAdmin(admin.ModelAdmin):
    list_display = ("id", "first_name", "last_name", "dob")
    search_fields = ("first_name", "last_name")

class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "appointment_date")
    list_filter = ("appointment_date",)
    search_fields = ("patient__first_name", "patient__last_name")

try:
    admin.site.register(Patient, PatientAdmin)
    admin.site.register(Appointment, AppointmentAdmin)
except Exception:
    # if already registered (e.g., re-run), ignore
    pass

# --- Minimal index view and urls ---
from django.shortcuts import render
from django.urls import path
from django.contrib import admin as admin_module

def index(request):
    return render(request, "simple_index.html", {})

urlpatterns = [
    path("", index, name="index"),
    path("admin/", admin_module.site.urls),
]

# --- Allow running management commands (runserver, createsuperuser, etc.) ---
if __name__ == "__main__":
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
