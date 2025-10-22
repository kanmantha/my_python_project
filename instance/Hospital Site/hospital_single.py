#!/usr/bin/env python3
"""
hospital_single_fixed.py
Single-file Django app (hospital_app) — all fixes applied

Features / fixes:
 - Ensures the single-file module is importable as 'hospital_app' (sys.modules hooks)
 - Provides a minimal HospitalAppConfig at hospital_app.apps
 - Defines Doctor, Patient, Appointment models with app_label='hospital_app' and __module__="hospital_app.models"
 - Runs django.setup() then applies a compatibility monkeypatch for Context.__copy__ (Python 3.14 safe)
 - Runs migrate --run-syncdb then uses connection.schema_editor() to create any missing tables
 - Seeds a demo admin (admin/admin123) and some demo data
 - Simple patients UI with inline editing, appointment creation modal, AJAX endpoints, export, and admin registration

Run:
    python hospital_single_fixed.py

Open:
    http://127.0.0.1:8000/patients/
    http://127.0.0.1:8000/admin/  (login: admin / admin123)

Note: This single-file approach is for local/dev only. For production, use a multi-file Django project with proper migrations.
"""

import os
import sys
import types
import io
import csv
import datetime
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------- Settings ----------------
from django.conf import settings
APP_CONFIG_PATH = "hospital_app.apps.HospitalAppConfig"

if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY="hospital_secret_key",
        ROOT_URLCONF=__name__,
        ALLOWED_HOSTS=["*"],
        INSTALLED_APPS=[
            "django.contrib.admin",
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "django.contrib.messages",
            "django.contrib.staticfiles",
            APP_CONFIG_PATH,
        ],
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
            }
        },
        MIDDLEWARE=[
            "django.middleware.security.SecurityMiddleware",
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.middleware.common.CommonMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
        ],
        TEMPLATES=[{
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "DIRS": [],
            "APP_DIRS": True,
            "OPTIONS": {"context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]},
        }],
        STATIC_URL="/static/",
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
    )

# Expose this module so Django can import hospital_app and hospital_app.apps
sys.modules.setdefault("hospital_app", sys.modules[__name__])

# Create hospital_app.apps module with AppConfig
from django.apps import AppConfig
class HospitalAppConfig(AppConfig):
    name = "hospital_app"
    verbose_name = "Hospital (single-file)"

apps_mod = types.ModuleType("hospital_app.apps")
apps_mod.HospitalAppConfig = HospitalAppConfig
sys.modules["hospital_app.apps"] = apps_mod
# Ensure hospital_app.models import loads this file
sys.modules["hospital_app.models"] = sys.modules[__name__]

# ---------------- Setup Django ----------------
import django
django.setup()

# ---------------- Compatibility monkeypatch for Context.__copy__ (Python 3.14) ----------------
from django.template.context import Context
try:
    from django.template.context import RequestContext
except Exception:
    RequestContext = None

if not getattr(Context, "_patched_copy_for_py314", False):
    def _context_copy(self):
        """
        Safe copy implementation for django.template.context.Context and RequestContext.
        Constructs a duplicate context correctly even when RequestContext requires a request.
        Ensures duplicate.dicts exists and duplicate._processors_index is present and in-range.
        """
        duplicate = None
        try:
            if RequestContext is not None and isinstance(self, RequestContext):
                # RequestContext(request, dict=None, processors=None)
                duplicate = self.__class__(getattr(self, 'request', None))
            else:
                duplicate = self.__class__()
        except TypeError:
            # Fallback to base Context
            from django.template.context import Context as BaseContext
            duplicate = BaseContext()

        # Copy dicts stack
        dicts = getattr(self, 'dicts', None)
        if dicts is not None:
            try:
                duplicate.dicts = [d.copy() for d in dicts]
            except Exception:
                duplicate.dicts = []
                for d in dicts:
                    try:
                        duplicate.dicts.append(dict(d))
                    except Exception:
                        duplicate.dicts.append({})
        else:
            duplicate.dicts = []

        # Ensure _processors_index exists and indexes into duplicate.dicts
        idx = getattr(self, "_processors_index", 0)
        try:
            idx = int(idx)
        except Exception:
            idx = 0
        if idx < 0:
            idx = 0
        while len(duplicate.dicts) <= idx:
            duplicate.dicts.append({})
        duplicate._processors_index = idx

        # Copy render_context if possible
        render_ctx = getattr(self, 'render_context', None)
        if render_ctx is not None:
            try:
                duplicate.render_context = render_ctx.copy()
            except Exception:
                try:
                    from django.template.context import RenderContext
                    duplicate.render_context = RenderContext()
                except Exception:
                    duplicate.render_context = {}

        # Copy visible mapping contents
        try:
            duplicate.update(dict(self))
        except Exception:
            for d in getattr(self, 'dicts', []):
                try:
                    for k, v in d.items():
                        duplicate[k] = v
                except Exception:
                    pass

        return duplicate

    Context.__copy__ = _context_copy
    Context._patched_copy_for_py314 = True
# ---------------- Models ----------------
from django.db import models

class Doctor(models.Model):
    __module__ = "hospital_app.models"
    user = models.OneToOneField("auth.User", on_delete=models.CASCADE)
    specialty = models.CharField(max_length=100, default="General Medicine")
    class Meta:
        app_label = "hospital_app"
    def __str__(self):
        return f"Dr. {self.user.get_full_name() or self.user.username}"

class Patient(models.Model):
    __module__ = "hospital_app.models"
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    age = models.IntegerField(default=0)
    condition = models.CharField(max_length=200, default="General Checkup")
    class Meta:
        app_label = "hospital_app"
    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip()

class Appointment(models.Model):
    __module__ = "hospital_app.models"
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="appointments")
    date = models.DateField()
    time = models.TimeField()
    class Meta:
        app_label = "hospital_app"
    def __str__(self):
        return f"{self.date} {self.time} - {self.patient} with {self.doctor}"

# ---------------- Admin ----------------
from django.contrib import admin
try:
    admin.site.register(Doctor)
    admin.site.register(Patient)
    admin.site.register(Appointment)
except admin.sites.AlreadyRegistered:
    pass

# ---------------- Ensure DB tables exist ----------------
from django.core.management import call_command
from django.db import connection

def create_missing_tables(models_list):
    existing_tables = set(connection.introspection.table_names())
    created = []
    with connection.schema_editor() as schema_editor:
        for m in models_list:
            table = m._meta.db_table
            if table not in existing_tables:
                schema_editor.create_model(m)
                created.append(table)
    return created

def ensure_db_setup():
    try:
        try:
            call_command("migrate", verbosity=1, run_syncdb=True)
        except TypeError:
            call_command("migrate", "--run-syncdb", verbosity=1)
    except Exception as exc:
        print("migrate attempt raised:", exc)

    needed = [Doctor, Patient, Appointment]
    existing_tables = set(connection.introspection.table_names())
    missing_models = [m for m in needed if m._meta.db_table not in existing_tables]
    if missing_models:
        created = create_missing_tables(missing_models)
        if not created:
            print("Current DB tables:", connection.introspection.table_names())
            raise RuntimeError("Failed to create tables for: %s" % ", ".join([m.__name__ for m in missing_models]))
        else:
            print("Created tables:", created)

try:
    ensure_db_setup()
except Exception as e:
    print("DB setup error:", e)
    raise

# ---------------- Seed demo data ----------------
from django.contrib.auth import get_user_model
User = get_user_model()

def seed_demo():
    if not User.objects.filter(username="admin").exists():
        User.objects.create_superuser("admin", "admin@example.com", "admin123")
        print("Created admin/admin123")
    doc_user, _ = User.objects.get_or_create(username="dr_smith", defaults={"first_name":"John","last_name":"Smith","email":"dr_smith@example.com"})
    Doctor.objects.get_or_create(user=doc_user, defaults={"specialty":"Cardiology"})
    Patient.objects.get_or_create(first_name="Alice", last_name="Brown", defaults={"age":30,"condition":"Checkup"})
    Patient.objects.get_or_create(first_name="Bob", last_name="Green", defaults={"age":45,"condition":"Diabetes"})

seed_demo()

# ---------------- Views / Templates / URLs ----------------
from django import forms
from django.shortcuts import get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.urls import path
from django.template import engines
from django.middleware.csrf import get_token
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Prefetch
from django.views.decorators.csrf import csrf_exempt

class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ["first_name","last_name","age","condition"]
        widgets = {"condition": forms.Textarea(attrs={"rows":2})}

django_engine = engines["django"]
def render_template(request, tpl_str, context=None, status=200):
    ctx = {} if context is None else dict(context)
    ctx.setdefault("request", request)
    get_token(request)
    template = django_engine.from_string(tpl_str)
    return HttpResponse(template.render(ctx, request), status=status)

BOOTSTRAP_HEAD = """
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
"""

PATIENT_LIST_TPL = BOOTSTRAP_HEAD + """
<!doctype html>
<html>
<head><meta charset="utf-8"><title>Patients</title></head>
<body class="bg-light">
<div class="container py-4">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h1 class="h3">Patients</h1>
    <div><a href="/admin/" class="btn btn-outline-secondary btn-sm">Admin</a> <a href="/patients/add/" class="btn btn-primary btn-sm">Add</a></div>
  </div>

  <form method="get" class="row g-2 mb-3">
    <div class="col-auto"><input name="q" value="{{ request.GET.q|default:'' }}" placeholder="Search name or condition" class="form-control"></div>
    <div class="col-auto"><button class="btn btn-outline-primary">Search</button></div>
    <div class="col text-end">
      <a href="/patients/export/?format=csv{% if request.GET.q %}&q={{ request.GET.q|urlencode }}{% endif %}" class="btn btn-sm btn-outline-success">Export CSV</a>
      <a href="/patients/export/?format=xlsx{% if request.GET.q %}&q={{ request.GET.q|urlencode }}{% endif %}" class="btn btn-sm btn-outline-success">Export Excel</a>
    </div>
  </form>

  <div class="card shadow-sm">
    <div class="card-body p-0">
      <div class="table-responsive">
        <table class="table table-striped mb-0">
          <thead class="table-light"><tr><th>ID</th><th>First</th><th>Last</th><th>Age</th><th>Condition</th><th>Doctors</th><th>Appointments</th><th>Actions</th></tr></thead>
          <tbody>
          {% for p in patients %}
            <tr data-pk="{{ p.id }}">
              <td>{{ p.id }}</td>
              <td contenteditable="true" data-field="first_name" class="editable">{{ p.first_name }}</td>
              <td contenteditable="true" data-field="last_name" class="editable">{{ p.last_name }}</td>
              <td contenteditable="true" data-field="age" class="editable">{{ p.age }}</td>
              <td contenteditable="true" data-field="condition" class="editable">{{ p.condition }}</td>
              <td data-col="doctors">{{ p.doctor_names }}</td>
              <td data-col="appointments">
                {% for a in p.appt_objs %}
                  <a href="#" class="appt-link" data-appt-id="{{ a.id }}">{{ a.date }} {{ a.time }}</a>{% if not forloop.last %}; {% endif %}
                {% empty %}-{% endfor %}
              </td>
              <td>
                <button class="btn btn-sm btn-primary js-save-row">Save</button>
                <button class="btn btn-sm btn-outline-success js-add-appt" data-pk="{{ p.id }}" data-name="{{ p.first_name }} {{ p.last_name }}">Add Appt</button>
                <button class="btn btn-sm btn-outline-danger" data-bs-toggle="modal" data-bs-target="#deleteModal" data-pk="{{ p.id }}" data-name="{{ p.first_name }} {{ p.last_name }}">Delete</button>
              </td>
            </tr>
          {% empty %}
            <tr><td colspan="8" class="text-center">No patients</td></tr>
          {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <nav class="mt-3"><ul class="pagination justify-content-center">
    {% if page_obj.has_previous %}
      <li class="page-item"><a class="page-link" href="?page=1">&laquo;First</a></li>
      <li class="page-item"><a class="page-link" href="?page={{ page_obj.previous_page_number }}">Prev</a></li>
    {% endif %}
    {% for n in page_range %}
      {% if n == page_obj.number %}
        <li class="page-item active"><span class="page-link">{{ n }}</span></li>
      {% else %}
        <li class="page-item"><a class="page-link" href="?page={{ n }}">{{ n }}</a></li>
      {% endif %}
    {% endfor %}
    {% if page_obj.has_next %}
      <li class="page-item"><a class="page-link" href="?page={{ page_obj.next_page_number }}">Next</a></li>
      <li class="page-item"><a class="page-link" href="?page={{ paginator.num_pages }}">Last &raquo;</a></li>
    {% endif %}
  </ul></nav>

</div>

<!-- Delete modal -->
<div class="modal fade" id="deleteModal" tabindex="-1"><div class="modal-dialog modal-sm modal-dialog-centered"><div class="modal-content">
  <form method="post" id="deleteForm">{% csrf_token %}
    <div class="modal-header"><h5 class="modal-title">Confirm delete</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
    <div class="modal-body">Delete <strong id="delName"></strong>?</div>
    <div class="modal-footer"><button class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancel</button><button class="btn btn-danger" type="submit">Delete</button></div>
  </form>
</div></div></div>

<!-- Add Appointment modal -->
<div class="modal fade" id="addApptModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content">
  <form id="addApptForm">{% csrf_token %}
    <div class="modal-header"><h5 class="modal-title">Add Appointment for <span id="addApptPatientName"></span></h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
    <div class="modal-body">
      <input type="hidden" id="addApptPatientId" name="patient_id"/>
      <div class="mb-2"><label>Doctor</label><select id="addApptDoctor" class="form-select">{% for d in doctors %}<option value="{{ d.id }}">{{ d.user.get_full_name|default:d.user.username }} ({{ d.specialty }})</option>{% endfor %}</select></div>
      <div class="mb-2"><label>Date</label><input type="date" id="addApptDate" class="form-control" required></div>
      <div class="mb-2"><label>Time</label><input type="time" id="addApptTime" class="form-control" required></div>
      <div id="addApptError" class="text-danger small"></div>
    </div>
    <div class="modal-footer"><button class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancel</button><button id="addApptSaveBtn" class="btn btn-primary" type="submit">Add</button></div>
  </form>
</div></div></div>

<script>
function getCookie(name){let v=null;if(document.cookie){const a=document.cookie.split(';');for(let i=0;i<a.length;i++){const c=a[i].trim(); if(c.startsWith(name+'=')){v=decodeURIComponent(c.substring(name.length+1));break;}}}return v}
const csrftoken = getCookie('csrftoken');

document.addEventListener('DOMContentLoaded', function(){
  document.querySelectorAll('td.editable').forEach(cell=>{
    cell.addEventListener('blur', async function(ev){
      const tr = ev.target.closest('tr'); const pk = tr.getAttribute('data-pk'); const field = ev.target.getAttribute('data-field'); const val = ev.target.textContent.trim();
      if(field==='age' && val && isNaN(Number(val))){ alert('Age must be numeric'); return; }
      try{ await fetch('/patients/ajax/update/', {method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':csrftoken}, body: JSON.stringify({id:pk,data:{[field]:val}})}); }catch(e){console.error(e)}
    });
  });

  const addApptModal = new bootstrap.Modal(document.getElementById('addApptModal'));
  document.querySelectorAll('.js-add-appt').forEach(btn=>{ btn.addEventListener('click', ()=>{ document.getElementById('addApptPatientId').value = btn.getAttribute('data-pk'); document.getElementById('addApptPatientName').textContent = btn.getAttribute('data-name'); addApptModal.show(); }); });

  document.getElementById('addApptForm').addEventListener('submit', async function(ev){
    ev.preventDefault();
    const patient_id = document.getElementById('addApptPatientId').value;
    const doctor_id = document.getElementById('addApptDoctor').value;
    const date = document.getElementById('addApptDate').value;
    const time = document.getElementById('addApptTime').value;
    try{
      const res = await fetch('/patients/ajax/add_appointment/', {method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':csrftoken}, body: JSON.stringify({patient_id,doctor_id,date,time})});
      const j = await res.json();
      if(res.ok && j.status==='ok'){
        const tr = document.querySelector('tr[data-pk="'+patient_id+'"]');
        if(tr){ tr.querySelector('td[data-col="doctors"]').textContent = j.doctors || ''; tr.querySelector('td[data-col="appointments"]').innerHTML = j.appt_links_html || j.appointments || ''; }
        addApptModal.hide();
      } else { document.getElementById('addApptError').textContent = j.error || 'Error'; }
    }catch(e){ document.getElementById('addApptError').textContent='Network error' }
  });

  var deleteModal = document.getElementById('deleteModal')
  deleteModal.addEventListener('show.bs.modal', function (event) {
    var button = event.relatedTarget
    var pk = button.getAttribute('data-pk')
    var name = button.getAttribute('data-name')
    var form = document.getElementById('deleteForm')
    form.action = '/patients/' + pk + '/delete/'
    document.getElementById('delName').textContent = name
  })
});
</script>
"""

PATIENT_FORM_TPL = BOOTSTRAP_HEAD + """
<!doctype html><html><head><meta charset="utf-8"><title>{{ title }}</title></head>
<body class="bg-light"><div class="container py-4">
  <a href="/patients/" class="btn btn-link">&larr; Back</a>
  <div class="card"><div class="card-body">
    <h2 class="h5">{{ title }}</h2>
    <form method="post">{% csrf_token %}{{ form.as_p }}<button class="btn btn-primary">Save</button></form>
  </div></div></div></body></html>
"""

# Views

def patients_list(request):
    q = (request.GET.get("q") or "").strip()
    per_page = int(request.GET.get("page_size") or 10)
    page_num = request.GET.get("page") or 1

    appt_prefetch = Prefetch('appointments', queryset=Appointment.objects.select_related('doctor__user').order_by('date','time'))
    qs = Patient.objects.all().prefetch_related(appt_prefetch).order_by("id")
    if q:
        qs = qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(condition__icontains=q))

    patients = []
    for p in qs:
        appts = list(p.appointments.select_related('doctor__user').all())
        p.appt_objs = appts
        p.doctor_names = ", ".join(sorted({ (a.doctor.user.get_full_name() or a.doctor.user.username) for a in appts })) if appts else ""
        patients.append(p)

    paginator = Paginator(patients, per_page)
    try:
        page_obj = paginator.page(page_num)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    current = page_obj.number; total = paginator.num_pages
    start = max(1, current-3); end = min(total, current+3)
    page_range = list(range(start, end+1))

    doctors = Doctor.objects.select_related('user').all()
    context = {"patients": page_obj.object_list, "page_obj": page_obj, "paginator": paginator, "page_range": page_range, "doctors": doctors}
    return render_template(request, PATIENT_LIST_TPL, context)


def patient_add(request):
    if request.method == "POST":
        form = PatientForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("/patients/")
    else:
        form = PatientForm()
    return render_template(request, PATIENT_FORM_TPL, {"form": form, "title": "Add patient"})


def patient_delete(request, pk):
    patient = get_object_or_404(Patient, pk=pk)
    if request.method == "POST":
        patient.delete()
        return redirect("/patients/")
    return redirect("/patients/")

@csrf_exempt
def patients_ajax_update(request):
    if request.method != "POST":
        return JsonResponse({"status":"error","error":"POST required"}, status=405)
    try:
        payload = json.loads(request.body.decode("utf-8"))
        pid = int(payload.get("id"))
        data = payload.get("data", {})
        p = Patient.objects.get(pk=pid)
        allowed = {"first_name","last_name","age","condition"}
        changed = False
        for k,v in data.items():
            if k in allowed:
                if k == "age":
                    try:
                        v = int(v) if v != "" else 0
                    except:
                        return JsonResponse({"status":"error","error":"age must be integer"}, status=400)
                setattr(p, k, v)
                changed = True
        if changed:
            p.save()
        appts = list(p.appointments.select_related('doctor__user').all())
        doctor_names = ", ".join(sorted({ (a.doctor.user.get_full_name() or a.doctor.user.username) for a in appts })) if appts else ""
        appt_links = '; '.join([f'<a href="#" class="appt-link" data-appt-id="{a.id}">{a.date} {a.time}</a>' for a in appts])
        return JsonResponse({"status":"ok","message":"Saved","doctors":doctor_names,"appointments":'; '.join([f"{a.date} {a.time}" for a in appts]), "appt_links_html": appt_links})
    except Exception as e:
        return JsonResponse({"status":"error","error":str(e)}, status=500)

@csrf_exempt
def patients_ajax_add_appointment(request):
    if request.method != "POST":
        return JsonResponse({"status":"error","error":"POST required"}, status=405)
    try:
        payload = json.loads(request.body.decode("utf-8"))
        pid = int(payload.get("patient_id"))
        did = int(payload.get("doctor_id"))
        date_s = payload.get("date")
        time_s = payload.get("time")
        if not (pid and did and date_s and time_s):
            return JsonResponse({"status":"error","error":"missing fields"}, status=400)
        patient = Patient.objects.get(pk=pid)
        doctor = Doctor.objects.get(pk=did)
        date_obj = datetime.datetime.strptime(date_s, "%Y-%m-%d").date()
        time_obj = datetime.datetime.strptime(time_s, "%H:%M").time()
        Appointment.objects.create(doctor=doctor, patient=patient, date=date_obj, time=time_obj)
        appts = list(patient.appointments.select_related('doctor__user').all())
        doctor_names = ", ".join(sorted({ (a.doctor.user.get_full_name() or a.doctor.user.username) for a in appts })) if appts else ""
        appt_links = '; '.join([f'<a href="#" class="appt-link" data-appt-id="{a.id}">{a.date} {a.time}</a>' for a in appts])
        return JsonResponse({"status":"ok","message":"Appointment added","doctors":doctor_names,"appointments":'; '.join([f"{a.date} {a.time}" for a in appts]), "appt_links_html": appt_links})
    except Exception as e:
        return JsonResponse({"status":"error","error":str(e)}, status=500)

def export_patients(request):
    fmt = (request.GET.get("format") or "csv").lower()
    q = (request.GET.get("q") or "").strip()
    qs = Patient.objects.all().prefetch_related('appointments__doctor__user').order_by("id")
    if q:
        qs = qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(condition__icontains=q))
    rows = [("ID","First","Last","Age","Condition","Doctors","Appointments")]
    for p in qs:
        appts = list(p.appointments.all())
        doctor_names = ", ".join(sorted({ (a.doctor.user.get_full_name() or a.doctor.user.username) for a in appts })) if appts else ""
        appt_texts = [f"{a.date.isoformat()} {a.time.strftime('%H:%M')}" for a in appts]
        rows.append((str(p.id), p.first_name, p.last_name, str(p.age), p.condition, doctor_names, "; ".join(appt_texts)))
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if fmt == "xlsx":
        try:
            import openpyxl
            from openpyxl import Workbook
            wb = Workbook(); ws = wb.active
            for r in rows: ws.append(r)
            bio = io.BytesIO(); wb.save(bio); bio.seek(0)
            resp = HttpResponse(bio.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            resp["Content-Disposition"] = f'attachment; filename="patients_{now}.xlsx"'
            return resp
        except Exception:
            pass
    bio = io.StringIO(); writer = csv.writer(bio)
    for r in rows: writer.writerow(r)
    resp = HttpResponse(bio.getvalue(), content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="patients_{now}.csv"'
    return resp

# URLs
from django.urls import path
from django.http import HttpResponseRedirect

def home(request): return HttpResponseRedirect("/patients/")

urlpatterns = [
    path("", home),
    path("patients/", patients_list, name="patients_list"),
    path("patients/add/", patient_add, name="patient_add"),
    path("patients/<int:pk>/delete/", patient_delete, name="patient_delete"),
    path("patients/export/", export_patients, name="patients_export"),
    path("patients/ajax/update/", patients_ajax_update, name="patients_ajax_update"),
    path("patients/ajax/add_appointment/", patients_ajax_add_appointment, name="patients_ajax_add_appointment"),
    path("admin/", admin.site.urls),
]

# Runserver entrypoint
if __name__ == "__main__":
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv if len(sys.argv) > 1 else [sys.argv[0], "runserver", "127.0.0.1:8000"])
