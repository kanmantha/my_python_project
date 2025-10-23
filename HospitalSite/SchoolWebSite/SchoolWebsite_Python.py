# school_single_fixed.py
from flask import Flask, request, redirect, url_for, flash, send_file, render_template_string, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField, DateField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Length, Email, Optional, NumberRange
from flask_login import LoginManager, login_user, current_user, login_required, logout_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import io, csv, re
from datetime import date, timedelta

# ---------------------
# Config + App + DB
# ---------------------
app = Flask(__name__)
app.config.update(
    SECRET_KEY="dev-single-file-secret-change-me",  # change in production
    SQLALCHEMY_DATABASE_URI="sqlite:///school_single.sqlite",
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
)
db = SQLAlchemy(app)
login = LoginManager(app)
login.login_view = "login"

# ---------------------
# MODELS
# ---------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default="admin")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    roll_no = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120))
    class_name = db.Column(db.String(50))
    extra = db.Column(db.String(255))

    attendances = db.relationship('Attendance', backref='student', lazy='dynamic')
    grades = db.relationship('Grade', backref='student', lazy='dynamic')

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(10), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))

class Grade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(80), nullable=False)
    marks = db.Column(db.Float, nullable=False)
    max_marks = db.Column(db.Float, default=100.0)
    term = db.Column(db.String(50), default="Term 1")
    remarks = db.Column(db.String(255))
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))

# ---------------------
# FORMS
# ---------------------
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(1,64)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class EnrollForm(FlaskForm):
    roll_no = StringField('Roll Number', validators=[DataRequired(), Length(1,20)])
    name = StringField('Full Name', validators=[DataRequired(), Length(1,120)])
    email = StringField('Email', validators=[Optional(), Email()])
    class_name = StringField('Class', validators=[Optional(), Length(1,50)])
    extra = TextAreaField('Notes', validators=[Optional()])
    submit = SubmitField('Enroll Student')

class GradeForm(FlaskForm):
    student_id = SelectField('Student', coerce=int, validators=[DataRequired()])
    subject = StringField('Subject', validators=[DataRequired(), Length(1,80)])
    marks = IntegerField('Marks', validators=[DataRequired(), NumberRange(min=0)])
    max_marks = IntegerField('Max Marks', default=100, validators=[Optional()])
    term = StringField('Term', default="Term 1", validators=[Optional()])
    remarks = TextAreaField('Remarks', validators=[Optional()])
    submit = SubmitField('Save Grade')

# ---------------------
# TEMPLATES (embedded)
# ---------------------
base_tpl = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>School Portal (Single-file)</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/modern-normalize/modern-normalize.css">
  <style>
    body { font-family: Arial, sans-serif; max-width: 1100px; margin: 20px auto; }
    nav a { margin-right: 12px; }
    table { border-collapse: collapse; width:100%; }
    th,td { padding:8px; border:1px solid #ddd; text-align:left; }
    .flash { padding:8px; margin-bottom:10px; border-radius:4px; }
    .flash-success { background:#d4edda; color:#155724; }
    .flash-danger { background:#f8d7da; color:#721c24; }
    form p { margin:6px 0; }
    header small { color:#666; display:block; margin-top:-6px; }
  </style>
</head>
<body>
  <header>
    <h1>School Portal</h1>
    <nav>
      {% if current_user.is_authenticated %}
      <a href="{{ url_for('index') }}">Dashboard</a>
      <a href="{{ url_for('students') }}">Students</a>
      <a href="{{ url_for('enroll') }}">Enroll</a>
      <a href="{{ url_for('attendance') }}">Attendance</a>
      <a href="{{ url_for('grades') }}">Grades</a>
      <a href="{{ url_for('report') }}">Reports</a>
      <a href="{{ url_for('export_students') }}">Export CSV</a>
      <a href="{{ url_for('logout') }}">Logout</a>
      {% else %}
      <a href="{{ url_for('login') }}">Login</a>
      {% endif %}
    </nav>
    <hr>
  </header>
  {% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
      {% for category, msg in messages %}
        <div class="flash flash-{{ category }}">{{ msg }}</div>
      {% endfor %}
    {% endif %}
  {% endwith %}

  {{ child_content|safe }}

  <footer style="margin-top:20px; font-size:0.9em; color:#666;">
    &copy; School Portal
  </footer>
</body>
</html>
"""

login_tpl = """
{% block content %}
  <h2>Login</h2>
  <form method="post">
    {{ form.hidden_tag() }}
    <p>{{ form.username.label }}<br>{{ form.username(size=32) }}</p>
    <p>{{ form.password.label }}<br>{{ form.password(size=32) }}</p>
    <p>{{ form.submit() }}</p>
  </form>
{% endblock %}
"""

index_tpl = """
{% block content %}
  <h2>Dashboard</h2>
  <p>Total students: <strong>{{ total_students }}</strong></p>
  <p>Present today ({{ today }}): <strong>{{ present_count }}</strong></p>
  <p><a href="{{ url_for('students') }}">View all students</a></p>
{% endblock %}
"""

students_tpl = """
{% block content %}
  <h2>Students</h2>
  <form method="get" style="margin-bottom:10px;">
    <input type="text" name="q" placeholder="search name / roll" value="{{ q }}">
    <button>Search</button>
  </form>
  <table>
    <tr><th>Roll</th><th>Name</th><th>Class</th><th>Email</th><th>Actions</th></tr>
    {% for s in students %}
      <tr>
        <td>{{ s.roll_no }}</td>
        <td>{{ s.name }}</td>
        <td>{{ s.class_name or "" }}</td>
        <td>{{ s.email or "" }}</td>
        <td><a href="{{ url_for('view_student', student_id=s.id) }}">View</a></td>
      </tr>
    {% else %}
      <tr><td colspan="5">No students found.</td></tr>
    {% endfor %}
  </table>
{% endblock %}
"""

enroll_tpl = """
{% block content %}
  <h2>Enroll Student</h2>
  <form method="post">
    {{ form.hidden_tag() }}
    <p>{{ form.roll_no.label }}<br>{{ form.roll_no(size=24) }}</p>
    <p>{{ form.name.label }}<br>{{ form.name(size=48) }}</p>
    <p>{{ form.email.label }}<br>{{ form.email(size=48) }}</p>
    <p>{{ form.class_name.label }}<br>{{ form.class_name(size=24) }}</p>
    <p>{{ form.extra.label }}<br>{{ form.extra(rows=4, cols=60) }}</p>
    <p>{{ form.submit() }}</p>
  </form>
{% endblock %}
"""

attendance_tpl = """
{% block content %}
  <h2>Attendance for {{ selected_date }}</h2>
  <form method="post">
    <p>Date: <input type="date" name="date" value="{{ selected_date.isoformat() }}"></p>
    <table>
      <tr><th>Roll</th><th>Name</th><th>Status</th></tr>
      {% for s in students %}
      <tr>
        <td>{{ s.roll_no }}</td>
        <td>{{ s.name }}</td>
        <td>
          <select name="status_{{ s.id }}">
            {% set st = existing.get(s.id) %}
            <option value="Present" {% if st and st.status=='Present' %}selected{% endif %}>Present</option>
            <option value="Absent" {% if st and st.status=='Absent' %}selected{% endif %}>Absent</option>
            <option value="Leave" {% if st and st.status=='Leave' %}selected{% endif %}>Leave</option>
          </select>
        </td>
      </tr>
      {% endfor %}
    </table>
    <p><button type="submit">Save Attendance</button></p>
  </form>
{% endblock %}
"""

grades_tpl = """
{% block content %}
  <h2>Grades</h2>
  <h3>Add Grade</h3>
  <form method="post">
    {{ form.hidden_tag() }}
    <p>{{ form.student_id.label }}<br>{{ form.student_id() }}</p>
    <p>{{ form.subject.label }}<br>{{ form.subject(size=40) }}</p>
    <p>{{ form.marks.label }}<br>{{ form.marks() }}</p>
    <p>{{ form.max_marks.label }}<br>{{ form.max_marks() }}</p>
    <p>{{ form.term.label }}<br>{{ form.term(size=30) }}</p>
    <p>{{ form.remarks.label }}<br>{{ form.remarks(rows=2, cols=60) }}</p>
    <p>{{ form.submit() }}</p>
  </form>

  <h3>Recent Grades</h3>
  <table>
    <tr><th>Student</th><th>Subject</th><th>Marks</th><th>Term</th><th>Remarks</th></tr>
    {% for g in grades %}
      <tr>
        <td>{{ g.student.roll_no }} - {{ g.student.name }}</td>
        <td>{{ g.subject }}</td>
        <td>{{ g.marks }} / {{ g.max_marks }}</td>
        <td>{{ g.term }}</td>
        <td>{{ g.remarks or "" }}</td>
      </tr>
    {% else %}
      <tr><td colspan="5">No grades yet.</td></tr>
    {% endfor %}
  </table>
{% endblock %}
"""

view_student_tpl = """
{% block content %}
  <h2>Student: {{ s.roll_no }} - {{ s.name }}</h2>
  <p><strong>Class:</strong> {{ s.class_name or "" }} &nbsp; <strong>Email:</strong> {{ s.email or "" }}</p>
  <p><strong>Notes:</strong> {{ s.extra or "—" }}</p>

  <h3>Attendance (last 30)</h3>
  <table>
    <tr><th>Date</th><th>Status</th></tr>
    {% for a in attendances %}
      <tr><td>{{ a.date }}</td><td>{{ a.status }}</td></tr>
    {% else %}
      <tr><td colspan="2">No attendance records.</td></tr>
    {% endfor %}
  </table>

  <h3>Grades (last 30)</h3>
  <table>
    <tr><th>Subject</th><th>Marks</th><th>Term</th><th>Remarks</th></tr>
    {% for g in grades %}
      <tr><td>{{ g.subject }}</td><td>{{ g.marks }} / {{ g.max_marks }}</td><td>{{ g.term }}</td><td>{{ g.remarks or "" }}</td></tr>
    {% else %}
      <tr><td colspan="4">No grades recorded.</td></tr>
    {% endfor %}
  </table>
{% endblock %}
"""

report_tpl = """
{% block content %}
  <h2>Attendance Report (last 7 days)</h2>
  <table>
    <tr><th>Date</th><th>Present</th><th>Total Students</th><th>% Present</th></tr>
    {% for row in summary %}
      <tr>
        <td>{{ row.date }}</td>
        <td>{{ row.present }}</td>
        <td>{{ row.total }}</td>
        <td>{{ "%.1f"|format((row.present / (row.total or 1))*100) }}%</td>
      </tr>
    {% endfor %}
  </table>
{% endblock %}
"""

template_env = {
    "base": base_tpl,
    "login.html": login_tpl,
    "index.html": index_tpl,
    "students.html": students_tpl,
    "enroll.html": enroll_tpl,
    "attendance.html": attendance_tpl,
    "grades.html": grades_tpl,
    "view_student.html": view_student_tpl,
    "report.html": report_tpl,
}

# ---------------------
# Template rendering helper (fixed)
# ---------------------
def render(name, **context):
    """
    Render a child template into base_tpl. Important: render the child template (so its
    Jinja tags are evaluated with the given context) first, then insert the rendered
    HTML into the base template as `child_content`.
    """
    if name not in template_env:
        raise RuntimeError(f"Template not found: {name}")

    child = template_env[name]

    # remove top `{% extends "base" %}` if present
    child = re.sub(r'^\s*\{%\s*extends\s+["\']base["\']\s*%}\s*', '', child, count=1, flags=re.MULTILINE)

    # extract content inside `{% block content %}` if present
    m = re.search(r'\{%\s*block\s+content\s*%}([\s\S]*?)\{%\s*endblock\s*%}', child, flags=re.MULTILINE)
    if m:
        inner = m.group(1)
    else:
        inner = child

    # First render the inner child template with the context so child Jinja expressions are resolved
    child_html = render_template_string(inner, **context)

    # Now render the base template, injecting rendered child_html as child_content
    full = template_env["base"]
    return render_template_string(full, child_content=child_html, **context)

# ---------------------
# Debug / admin init endpoint (only in debug)
# ---------------------
@app.route('/init-admin', methods=['GET', 'POST'])
def init_admin():
    if not app.debug:
        return "Not allowed", 403

    if request.method == 'GET':
        return (
            "<h3>Init / Reset admin</h3>"
            "<form method='post'>"
            "Password: <input name='password'/>"
            "<button type='submit'>Set admin password</button>"
            "</form>"
            "<p>Or POST JSON {\"password\":\"...\"}</p>"
        )

    newpw = request.form.get('password') or (request.json or {}).get('password')
    if not newpw:
        return "Provide password", 400

    with app.app_context():
        db.create_all()
        u = User.query.filter_by(username='admin').first()
        if not u:
            u = User(username='admin', role='admin')
            db.session.add(u)
        u.set_password(newpw)
        db.session.commit()
    return f"Admin password set to: <strong>{newpw}</strong> (use admin / {newpw})", 200

# ---------------------
# ROUTES
# ---------------------
@app.route('/')
@login_required
def index():
    total_students = Student.query.count()
    today = date.today()
    present_count = Attendance.query.filter_by(date=today, status='Present').count()
    return render("index.html", total_students=total_students, present_count=present_count, today=today)

@app.route('/login', methods=['GET','POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash("Logged in successfully.", "success")
            return redirect(url_for('index'))
        flash("Invalid username or password.", "danger")
    else:
        # helpful debugging prints when form validation fails (only shown in console)
        if request.method == 'POST':
            app.logger.debug("=== Login form validation failed ===")
            app.logger.debug("request.form: %s", dict(request.form))
            app.logger.debug("form.errors: %s", form.errors)
    return render("login.html", form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/students')
@login_required
def students():
    q = request.args.get('q', '')
    if q:
        students = Student.query.filter(Student.name.ilike(f'%{q}%') | Student.roll_no.ilike(f'%{q}%')).all()
    else:
        students = Student.query.order_by(Student.roll_no).all()
    return render("students.html", students=students, q=q)

@app.route('/enroll', methods=['GET','POST'])
@login_required
def enroll():
    form = EnrollForm()
    if form.validate_on_submit():
        if Student.query.filter_by(roll_no=form.roll_no.data).first():
            flash("Roll Number already exists.", "warning")
            return render("enroll.html", form=form)
        s = Student(roll_no=form.roll_no.data.strip(), name=form.name.data.strip(),
                    email=form.email.data, class_name=form.class_name.data, extra=form.extra.data)
        db.session.add(s); db.session.commit()
        flash("Student enrolled.", "success")
        return redirect(url_for('students'))
    return render("enroll.html", form=form)

@app.route('/student/<int:student_id>')
@login_required
def view_student(student_id):
    s = Student.query.get_or_404(student_id)
    attendances = s.attendances.order_by(Attendance.date.desc()).limit(30).all() if s.attendances else []
    grades = s.grades.order_by(Grade.id.desc()).limit(30).all() if s.grades else []
    return render("view_student.html", s=s, attendances=attendances, grades=grades)

@app.route('/attendance', methods=['GET','POST'])
@login_required
def attendance():
    selected_date = request.args.get('date')
    if selected_date:
        selected_date = date.fromisoformat(selected_date)
    else:
        selected_date = date.today()
    students = Student.query.order_by(Student.roll_no).all()
    if request.method == 'POST':
        d = date.fromisoformat(request.form.get('date'))
        # remove old records for date d
        Attendance.query.filter_by(date=d).delete()
        for s in students:
            status = request.form.get(f'status_{s.id}', 'Absent')
            att = Attendance(date=d, status=status, student_id=s.id)
            db.session.add(att)
        db.session.commit()
        flash("Attendance saved.", "success")
        return redirect(url_for('attendance', date=d.isoformat()))
    existing_q = Attendance.query.filter_by(date=selected_date).all()
    existing = {a.student_id: a for a in existing_q}
    return render("attendance.html", students=students, existing=existing, selected_date=selected_date)

@app.route('/grades', methods=['GET','POST'])
@login_required
def grades():
    form = GradeForm()
    form.student_id.choices = [(s.id, f"{s.roll_no} - {s.name}") for s in Student.query.order_by(Student.roll_no)]
    if form.validate_on_submit():
        g = Grade(student_id=form.student_id.data, subject=form.subject.data.strip(),
                  marks=form.marks.data, max_marks=form.max_marks.data or 100.0,
                  term=form.term.data, remarks=form.remarks.data)
        db.session.add(g); db.session.commit()
        flash("Grade saved.", "success")
        return redirect(url_for('grades'))
    grades = Grade.query.order_by(Grade.id.desc()).limit(100).all()
    return render("grades.html", form=form, grades=grades)

@app.route('/export/students.csv')
@login_required
def export_students():
    students = Student.query.order_by(Student.roll_no).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['roll_no','name','email','class_name','extra'])
    for s in students:
        writer.writerow([s.roll_no, s.name, s.email or '', s.class_name or '', s.extra or ''])
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode()), mimetype='text/csv', as_attachment=True, download_name='students.csv')

@app.route('/report')
@login_required
def report():
    today = date.today()
    dates = [(today - timedelta(days=i)) for i in range(7)]
    summary = []
    for d in dates:
        total = Student.query.count()
        present = Attendance.query.filter_by(date=d, status='Present').count()
        summary.append({'date': d, 'present': present, 'total': total})
    return render("report.html", summary=summary)

# ---------------------
# Startup: create DB + default admin if missing
# ---------------------
def ensure_db_and_admin():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        u = User(username='admin', role='admin')
        u.set_password('admin')  # change on first login
        db.session.add(u); db.session.commit()
        print("Created default admin / admin (please change password)")

if __name__ == '__main__':
    with app.app_context():
        ensure_db_and_admin()
    app.run(debug=True)
