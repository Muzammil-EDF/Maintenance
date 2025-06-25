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
                model=request.form['model'],
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
            pm_date_str = request.form.get("pm_date")
            if pm_date_str:
                try:
                    todo.pm_date = datetime.strptime(pm_date_str, "%Y-%m-%d").date()
                except ValueError:
                    flash("Invalid PM date format.", "danger")


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

# ----------------------PM SCHEDULING YTM-1-------------------------------------

@app.route("/ytm1_schedule/<building>")
@login_required
def ytm1_schedule(building):
    # Authorization check
    if current_user.unit != "YTM-1" and current_user.role != 'master':
        flash("Unauthorized", "danger")
        return redirect("/")

    included_categories = ["Normal", "Special"]

    # Fetch matching records
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
    per_day = ceil(total_machines / days)

    schedule = []
    current_date = datetime.today()
    machine_index = 0

    for day in range(days):
        daily_batch = records[machine_index:machine_index + per_day]
        if not daily_batch:
            break

        date_obj = current_date.date()
        date_str = date_obj.strftime("%Y-%m-%d")
        for machine in daily_batch:
            # Only set pm_date if it's not already set
            if not machine.pm_date:
                machine.pm_date = date_obj

            schedule.append({
                "brand": machine.brand,
                "model": machine.model,
                "tag": machine.tag,
                "serial": machine.serial,
                "desc": machine.desc,
                "building": machine.building,
                "floor": machine.floor,
                "preventive_date": machine.pm_date.strftime("%Y-%m-%d") if machine.pm_date else "N/A"
            })


        machine_index += len(daily_batch)
        current_date += timedelta(days=1)

    try:
        db.session.commit()
        flash("Preventive maintenance schedule generated and saved.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating pm_date: {e}", "danger")

    return render_template("preventive_schedule.html", schedule=schedule, building=building, per_day=per_day)


# ----------------------PM SCHEDULING YTM-2-------------------------------------
@app.route("/ytm2_schedule/<building>")
@login_required
def ytm2_schedule(building):
    # Authorization check
    if current_user.unit != "YTM-2" and current_user.role != 'master':
        flash("Unauthorized", "danger")
        return redirect("/")

    included_categories = ["Normal", "Special"]

    # Fetch matching records
    records = Todo.query.filter(
        and_(
            Todo.unit == "YTM-2",
            Todo.building == building,
            Todo.category.in_(included_categories)
        )
    ).all()

    if not records:
        flash("No machines found for selected building and categories.", "warning")
        return render_template("preventive_schedule.html", schedule=[], building=building)

    total_machines = len(records)
    days = 90
    per_day = ceil(total_machines / days)

    schedule = []
    current_date = datetime.today()
    machine_index = 0

    for day in range(days):
        daily_batch = records[machine_index:machine_index + per_day]
        if not daily_batch:
            break

        date_obj = current_date.date()
        date_str = date_obj.strftime("%Y-%m-%d")
        for machine in daily_batch:
            # Only set pm_date if it's not already set
            if not machine.pm_date:
                machine.pm_date = date_obj

            schedule.append({
                "brand": machine.brand,
                "model": machine.model,
                "tag": machine.tag,
                "serial": machine.serial,
                "desc": machine.desc,
                "building": machine.building,
                "floor": machine.floor,
                "preventive_date": machine.pm_date.strftime("%Y-%m-%d") if machine.pm_date else "N/A"
            })


        machine_index += len(daily_batch)
        current_date += timedelta(days=1)

    try:
        db.session.commit()
        flash("Preventive maintenance schedule generated and saved.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating pm_date: {e}", "danger")

    return render_template("preventive_schedule.html", schedule=schedule, building=building, per_day=per_day)

@app.route("/download_schedule/<building>")
@login_required
def download_schedule(building):
    # Allow only authorized units or master
    allowed_units = ["YTM-1", "YTM-2", "YTM-3", "YTM-7"]
    if current_user.unit not in allowed_units and current_user.role != 'master':
        flash("Unauthorized", "danger")
        return redirect("/")

    # Determine which unit's data to fetch
    selected_unit = current_user.unit if current_user.role != 'master' else request.args.get("unit", "YTM-1")

    included_categories = ["Normal", "Special"]
    records = Todo.query.filter(
        and_(
            Todo.unit == selected_unit,
            Todo.building == building,
            Todo.category.in_(included_categories)
        )
    ).order_by(Todo.pm_date.asc()).all()

    if not records:
        flash("No data available to export.", "warning")
        return redirect(f"/{selected_unit.lower()}_schedule/{building}")

    # Convert to DataFrame
    data = [{
        "PM Date": record.pm_date.strftime("%Y-%m-%d") if record.pm_date else "N/A",
        "Description": record.desc,
        "Brand": record.brand,
        "Model": record.model,
        "Tag": record.tag,
        "Serial": record.serial,
        "Building": record.building,
        "Floor": record.floor
    } for record in records]

    df = pd.DataFrame(data)

    # Create in-memory Excel file
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="PM Schedule")
    output.seek(0)

    filename = f"PM_Schedule_{selected_unit}_{building}.xlsx"
    return send_file(output, download_name=filename, as_attachment=True)
