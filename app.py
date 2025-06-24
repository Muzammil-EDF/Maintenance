from flask import Flask, render_template, request, redirect, flash, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_
from io import BytesIO
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import or_, and_
import os
from datetime import datetime, timedelta
from math import ceil

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a strong secret key
# app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///master_db.db"
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
uri = os.environ.get('DATABASE_URL')
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ------------------ Models ------------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'master' or 'limited'
    unit = db.Column(db.String(100))  # For limited users

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Todo(db.Model):
    sno = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(200), nullable=True)
    desc = db.Column(db.String(500), nullable=True)
    tag = db.Column(db.String(500), nullable=True)
    unit = db.Column(db.String(500), nullable=True)
    building = db.Column(db.String(500), nullable=True)
    floor = db.Column(db.String(500))
    serial = db.Column(db.String(500))
    date = db.Column(db.String(500))
    home = db.Column(db.String(500))
    status = db.Column(db.String(500))
    brand = db.Column(db.String(500))
    model = db.Column(db.String(500))
    pm_date = db.Column(db.Date)

    def __repr__(self):
        return f"{self.sno} - {self.desc}"

# ------------------ Login Manager ------------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ------------------ Routes ------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect('/')
        flash("Invalid credentials", "danger")

    # ✅ Always fetch Todo records for view-only table (even if not authenticated)
    alltodo = Todo.query.all()

    return render_template('login.html', alltodo=alltodo)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/login')

@app.route('/', methods=['GET', 'POST'])
@login_required
def get_input():
    if request.method == 'POST':
        if current_user.role == 'master' or current_user.unit == request.form['unit']:
            todo = Todo(
                category=request.form['category'],
                desc=request.form['desc'],
                tag=request.form['tag'],
                unit=request.form['unit'],
                building=request.form['building'],
                floor=request.form['floor'],
                serial=request.form['serial'],
                date=request.form['date'],
                home=request.form['home'],
                status=request.form['status'],
                brand=request.form['brand'],
                model=request.form['model']
                pm_date=request.form['pm_date']
            )
            db.session.add(todo)
            db.session.commit()
        else:
            flash("You don't have permission to add data to this unit", "warning")

    if current_user.role == 'master':
        alltodo = Todo.query.all()
    else:
        alltodo = Todo.query.filter_by(unit=current_user.unit).all()
    return render_template('index.html', alltodo=alltodo)

@app.route("/update/<int:sno>", methods=['GET', 'POST'])
@login_required
def update(sno):
    todo = Todo.query.filter_by(sno=sno).first_or_404()

    # Ensure limited user only accesses their own unit's data
    if current_user.role == 'limited' and todo.unit != current_user.unit:
        flash("You are not authorized to update this item.", "danger")
        return redirect("/")
    
    if request.method == 'POST':
        if current_user.role == 'limited':
            # Only allow updating building and floor
            todo.building = request.form['building']
            todo.floor = request.form['floor']
        else:
            # Master can update all fields
            todo.category = request.form['category']
            todo.desc = request.form['desc']
            todo.tag = request.form['tag']
            todo.unit = request.form['unit']
            todo.building = request.form['building']
            todo.floor = request.form['floor']
            todo.serial = request.form['serial']
            todo.date = request.form['date']
            todo.home = request.form['home']
            todo.status = request.form['status']
            todo.brand = request.form['brand']
            todo.model = request.form['model']
            todo.pm_date = request.form['pm_date']

        db.session.commit()
        flash("Update successful.", "success")
        return redirect("/")

    return render_template("update.html", todo=todo)


@app.route("/delete/<int:sno>")
@login_required
def delete(sno):
    todo = Todo.query.get_or_404(sno)
    if current_user.role != 'master' and todo.unit != current_user.unit:
        flash("Unauthorized to delete this entry", "danger")
        return redirect('/')
    db.session.delete(todo)
    db.session.commit()
    return redirect('/')

@app.route("/search", methods=["GET"])
@login_required
def search():
    query = request.args.get('query')
    filters = or_(
        Todo.category.ilike(f"%{query}%"),
        Todo.desc.ilike(f"%{query}%"),
        Todo.tag.ilike(f"%{query}%"),
        Todo.unit.ilike(f"%{query}%"),
        Todo.building.ilike(f"%{query}%"),
        Todo.floor.ilike(f"%{query}%"),
        Todo.serial.ilike(f"%{query}%"),
        Todo.date.ilike(f"%{query}%"),
        Todo.home.ilike(f"%{query}%"),
        Todo.status.ilike(f"%{query}%"),
        Todo.brand.ilike(f"%{query}%"),
        Todo.model.ilike(f"%{query}%"),
        Todo.pm_date.ilike(f"%{query}%")
    )
    if current_user.role == 'master':
        results = Todo.query.filter(filters).all()
    else:
        results = Todo.query.filter(filters, Todo.unit == current_user.unit).all()
    return render_template("search.html", results=results, query=query)


@app.route("/download_excel")
@login_required  # Optional: only allow logged-in users
def download_excel():
    # Get records from DB
    if current_user.role == 'master':
        data = Todo.query.all()
    else:
        data = Todo.query.filter_by(unit=current_user.unit).all()

    # Convert to DataFrame
    rows = [{
        "Category": d.category,
        "Description": d.desc,
        "Tag": d.tag,
        "Unit": d.unit,
        "Building": d.building,
        "Floor": d.floor,
        "Serial": d.serial,
        "Date": d.date,
        "Home": d.home,
        "Status": d.status,
        "Brand": d.brand,
        "Model": d.model,
        "PM_Date": d.pm_date
    } for d in data]

    df = pd.DataFrame(rows)

    # Write to Excel in memory
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="TodoData")
    output.seek(0)

    # Send as file to user
    return send_file(
        output,
        download_name="todo_data.xlsx",
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@app.route("/ytm1_schedule/<building>")
@login_required
def ytm1_schedule(building):
    if current_user.unit != "YTM-1" and current_user.role != 'master':
        flash("Unauthorized", "danger")
        return redirect("/")

    included_categories = ["Normal", "Special"]

    records = Todo.query.filter(
        and_(
            Todo.unit == "YTM-1",
            Todo.building == building,
            Todo.category.in_(included_categories)
        )
    ).all()

    if not records:
        flash("No machines found for selected building and categories.", "warning")
        return render_template("preventive_schedule.html", schedule=[], building=building)

    total_machines = len(records)
    days = 90

    # Calculate how many machines per day, using ceil to ensure within 90 days
    per_day = ceil(total_machines / days)

    schedule = []
    current_date = datetime.today()
    machine_index = 0

    for day in range(days):
        # On the last day, take all remaining machines
        daily_batch = records[machine_index:machine_index + per_day]
        if not daily_batch:
            break  # No more machines left

        date_str = current_date.strftime("%Y-%m-%d")
        for machine in daily_batch:
            schedule.append({
                # "category": machine.category,
                "brand": machine.brand,
                "model": machine.model,
                "tag": machine.tag,
                "serial": machine.serial,
                "desc": machine.desc,
                "building": machine.building,
                "floor": machine.floor,
                "preventive_date": date_str
            })

        machine_index += len(daily_batch)
        current_date += timedelta(days=1)

    return render_template("preventive_schedule.html", schedule=schedule, building=building, per_day=per_day)


