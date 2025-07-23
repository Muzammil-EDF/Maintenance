from flask import Flask, render_template, request, redirect, flash, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from io import BytesIO
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import or_, and_, func
import os
from datetime import datetime, timedelta
from math import ceil
import json
import openpyxl

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
    floor = db.Column(db.String(500), nullable=True)
    serial = db.Column(db.String(500), nullable=True)
    date = db.Column(db.String(500), nullable=True)
    home = db.Column(db.String(500),nullable=True)
    status = db.Column(db.String(500), nullable=True)
    brand = db.Column(db.String(500), nullable=True)
    model = db.Column(db.String(500), nullable=True)
    pm_date = db.Column(db.Date)
    pm_status = db.Column(db.String(20), default="Pending")  # "Pending" or "Done"
    checklist = db.Column(db.Text)  # JSON or plain text data of checklist
    
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

# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

@app.route('/api/data')
@login_required
def data():
    draw = int(request.args.get('draw', 1))
    start = int(request.args.get('start', 0))
    length = int(request.args.get('length', 10))

    query = Todo.query
    if current_user.role == 'limited':
        query = query.filter_by(unit=current_user.unit)

    from sqlalchemy import func
    search_filters = []

    def get_col_value(index):
        return request.args.get(f'columns[{index}][search][value]', '').strip().lower()

    # Map of (column index → SQLAlchemy filter)
    col_map = {
        1: lambda val: func.lower(Todo.date).like(f"%{val}%"),
        2: lambda val: func.lower(Todo.home).like(f"%{val}%"),
        3: lambda val: func.lower(Todo.status).like(f"%{val}%"),
        4: lambda val: func.lower(Todo.category).like(f"%{val}%"),
        5: lambda val: func.lower(Todo.brand).like(f"%{val}%"),
        6: lambda val: func.lower(Todo.model).like(f"%{val}%"),
        7: lambda val: func.lower(Todo.tag).like(f"%{val}%"),
        8: lambda val: func.lower(Todo.serial).like(f"%{val}%"),
        9: lambda val: func.lower(Todo.desc).like(f"%{val}%"),
        10: lambda val: func.lower(Todo.unit).like(f"%{val}%"),
        11: lambda val: func.lower(Todo.building).like(f"%{val}%"),
        12: lambda val: func.lower(Todo.floor).like(f"%{val}%"),
        13: lambda val: func.cast(Todo.pm_date, db.String).like(f"%{val}%"),
    }

    for i, filter_func in col_map.items():
        val = get_col_value(i)
        if val:
            search_filters.append(filter_func(val))

    # Apply all filters
    if search_filters:
        from sqlalchemy import and_
        query = query.filter(and_(*search_filters))

    records_filtered = query.count()
    todos = query.offset(start).limit(length).all()

    total = Todo.query.filter_by(unit=current_user.unit).count() if current_user.role == 'limited' else Todo.query.count()

    data = [{
        "sno": t.sno,
        "date": t.date,
        "home": t.home,
        "status": t.status,
        "category": t.category,
        "brand": t.brand,
        "model": t.model,
        "tag": t.tag,
        "serial": t.serial,
        "desc": t.desc,
        "unit": t.unit,
        "building": t.building,
        "floor": t.floor,
        "pm_date": t.pm_date.strftime("%Y-%m-%d") if t.pm_date else "",
        "can_delete": current_user.role == 'master'
    } for t in todos]

    return {
        'draw': draw,
        'recordsTotal': total,
        'recordsFiltered': records_filtered,
        'data': data
    }

# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


@app.route('/api/public_data')
def public_data():
    draw = int(request.args.get('draw', 1))
    start = int(request.args.get('start', 0))
    length = int(request.args.get('length', 10))
    search_value = request.args.get('search[value]', '').lower()

    query = Todo.query

    if search_value:
        search = f"%{search_value}%"
        # from sqlalchemy import func
        query = query.filter(
            or_(
                func.lower(Todo.date).like(search),
                func.lower(Todo.home).like(search),
                func.lower(Todo.status).like(search),
                func.lower(Todo.category).like(search),
                func.lower(Todo.brand).like(search),
                func.lower(Todo.model).like(search),
                func.lower(Todo.tag).like(search),
                func.lower(Todo.serial).like(search),
                func.lower(Todo.desc).like(search),
                func.lower(Todo.unit).like(search),
                func.lower(Todo.building).like(search),
                func.lower(Todo.floor).like(search),
                func.cast(Todo.pm_date, db.String).like(search)
            )
        )

    records_filtered = query.count()
    todos = query.offset(start).limit(length).all()
    total = Todo.query.count()

    data = [{
        "date": t.date,
        "home": t.home,
        "status": t.status,
        "category": t.category,
        "brand": t.brand,
        "model": t.model,
        "tag": t.tag,
        "serial": t.serial,
        "desc": t.desc,
        "unit": t.unit,
        "building": t.building,
        "floor": t.floor,
        "pm_date": t.pm_date.strftime("%Y-%m-%d") if t.pm_date else "",
    } for t in todos]

    return {
        'draw': draw,
        'recordsTotal': total,
        'recordsFiltered': records_filtered,
        'data': data
    }


# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# -----------------------------------------------------------------YTM-1-ELECTRICAL-------------------------------------------------------------
allowed_config_el1 = {
    "2A": {
        "floors": ["FF", "GF", "FF-WORKSHOP", "GF-SAMPLE", "GF-WORKSHOP"],
        "categories": ["Cutting", "Packing"]
    },
    "2B": {
        "floors": ["FF", "GF", "FF-WORKSHOP", "GF-SAMPLE", "GF-WORKSHOP"],
        "categories": ["Cutting", "Packing"]
    },
}
@app.route("/ytm1_schedule_electrical/<building>")
@login_required
def ytm1_schedule_electrical(building):
    # Authorization
    if current_user.unit != "YTM-1" and current_user.role != 'master':
        flash("Unauthorized", "danger")
        return redirect("/")

    # Validate allowed config for building
    config = allowed_config_el1.get(building)
    if not config:
        flash("Invalid building or no config found.", "danger")
        return redirect("/")

    included_floors = config["floors"]
    included_categories = config["categories"]

    # Filter records by unit, building, category and floor
    records = Todo.query.filter(
        and_(
            Todo.unit == "YTM-1",
            Todo.building == building,
            Todo.category.in_(included_categories),
            Todo.floor.in_(included_floors)
        )
    ).order_by(Todo.sno).all()

    if not records:
        flash("No machines found for selected filters.", "warning")
        return render_template("preventive_schedule.html", schedule=[], building=building)

    total_machines = len(records)
    days = 90
    per_day = ceil(total_machines / days)
    
    # Define holidays and generate valid date list
    holidays = {
        datetime.strptime(date, "%Y-%m-%d").date()
        for date in [
            "2025-02-05", "2025-03-23", "2025-03-30", "2025-03-31", "2025-04-01",
            "2025-05-01", "2025-06-06", "2025-06-07", "2025-06-08", "2025-07-04",
            "2025-07-05", "2025-08-14", "2025-09-04", "2025-11-09", "2025-12-25"
        ]
    }
    start_date = datetime(2025, 7, 13).date()
    valid_dates = []
    current_date = start_date


    while len(valid_dates) < days:
        if current_date.weekday() != 6 and current_date not in holidays:
            valid_dates.append(current_date)
        current_date += timedelta(days=1)


    

    schedule = []
    machine_index = 0

    for i in range(days):
        daily_batch = records[machine_index:machine_index + per_day]
        if not daily_batch:
            break

        date_obj = valid_dates[i]
        for machine in daily_batch:
            # restrict the dats change of pm by putting inside IF code into IF, and vice versa
            if not machine.pm_date:
                machine.pm_date = date_obj

            schedule.append({
                "sno": machine.sno,
                "brand": machine.brand,
                "model": machine.model,
                "tag": machine.tag,
                "serial": machine.serial,
                "desc": machine.desc,
                "building": machine.building,
                "floor": machine.floor,
                "preventive_date": machine.pm_date.strftime("%Y-%m-%d") if machine.pm_date else "N/A",
                "pm_status": machine.pm_status or "Pending"
            })

        machine_index += len(daily_batch)
    try:
        db.session.commit()
        flash("Preventive maintenance schedule generated and saved.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating pm_date: {e}", "danger")

    return render_template("preventive_schedule.html", schedule=schedule, building=building, per_day=per_day, today=datetime.today().date())

# -----------------------------------------------------------------YTM-1-MECHANICAL-------------------------------------------------------------
allowed_config1 = {
    "2A": {
        "floors": ["FF", "GF", "FF-WORKSHOP", "GF-SAMPLE", "GF-WORKSHOP"],
        "categories": ["Normal", "Special"]
    },
    "2B": {
        "floors": ["FF", "SF-SAMPLE"],
        "categories": ["Normal", "Special"]
    },
}
@app.route("/ytm1_schedule/<building>")
@login_required
def ytm1_schedule(building):
    # Authorization
    if current_user.unit != "YTM-1" and current_user.role != 'master':
        flash("Unauthorized", "danger")
        return redirect("/")

    # Validate allowed config for building
    config = allowed_config1.get(building)
    if not config:
        flash("Invalid building or no config found.", "danger")
        return redirect("/")

    included_floors = config["floors"]
    included_categories = config["categories"]

    # Filter records by unit, building, category and floor
    records = Todo.query.filter(
        and_(
            Todo.unit == "YTM-1",
            Todo.building == building,
            Todo.category.in_(included_categories),
            Todo.floor.in_(included_floors)
        )
    ).all()

    if not records:
        flash("No machines found for selected filters.", "warning")
        return render_template("preventive_schedule.html", schedule=[], building=building)

    total_machines = len(records)
    days = 90
    per_day = ceil(total_machines / days)
    
    # Define holidays and generate valid date list
    holidays = {
        datetime.strptime(date, "%Y-%m-%d").date()
        for date in [
            "2025-02-05", "2025-03-23", "2025-03-30", "2025-03-31", "2025-04-01",
            "2025-05-01", "2025-06-06", "2025-06-07", "2025-06-08", "2025-07-04",
            "2025-07-05", "2025-08-14", "2025-09-04", "2025-11-09", "2025-12-25"
        ]
    }
    start_date = datetime(2025, 7, 13).date()
    valid_dates = []
    current_date = start_date


    while len(valid_dates) < days:
        if current_date.weekday() != 6 and current_date not in holidays:
            valid_dates.append(current_date)
        current_date += timedelta(days=1)


    

    schedule = []
    machine_index = 0

    for i in range(days):
        daily_batch = records[machine_index:machine_index + per_day]
        if not daily_batch:
            break

        date_obj = valid_dates[i]
        for machine in daily_batch:
            # restrict the dats change of pm by putting inside IF code into IF, and vice versa
            if not machine.pm_date:
                machine.pm_date = date_obj

            schedule.append({
                "sno": machine.sno,
                "brand": machine.brand,
                "model": machine.model,
                "tag": machine.tag,
                "serial": machine.serial,
                "desc": machine.desc,
                "building": machine.building,
                "floor": machine.floor,
                "preventive_date": machine.pm_date.strftime("%Y-%m-%d") if machine.pm_date else "N/A",
                "pm_status": machine.pm_status or "Pending"
            })

        machine_index += len(daily_batch)
    try:
        db.session.commit()
        flash("Preventive maintenance schedule generated and saved.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating pm_date: {e}", "danger")

    return render_template("preventive_schedule.html", schedule=schedule, building=building, per_day=per_day, today=datetime.today().date())

# -----------------------------------------------------------------YTM-2-ELECTRICAL-------------------------------------------------------------
allowed_config_el2 = {
    "2A": {
        "floors": ["FF", "GF", "SF", "TF", "GF-WORKSHOP"],
        "categories": ["Cutting", "Packing", "Tracks"]
    },
    "2B": {
        "floors": ["FF", "GF", "SF"],
        "categories": ["Cutting", "Packing"]
    },
}
@app.route("/ytm2_schedule_electrical/<building>")
@login_required
def ytm2_schedule_electrical(building):
    # Authorization
    if current_user.unit != "YTM-2" and current_user.role != 'master':
        flash("Unauthorized", "danger")
        return redirect("/")

    # Validate allowed config for building
    config = allowed_config_el2.get(building)
    if not config:
        flash("Invalid building or no config found.", "danger")
        return redirect("/")

    included_floors = config["floors"]
    included_categories = config["categories"]

    # Filter records by unit, building, category and floor
    records = Todo.query.filter(
        and_(
            Todo.unit == "YTM-2",
            Todo.building == building,
            Todo.category.in_(included_categories),
            Todo.floor.in_(included_floors)
        )
    ).all()

    if not records:
        flash("No machines found for selected filters.", "warning")
        return render_template("preventive_schedule.html", schedule=[], building=building)

    total_machines = len(records)
    days = 90
    per_day = ceil(total_machines / days)
    
    # Define holidays and generate valid date list
    holidays = {
        datetime.strptime(date, "%Y-%m-%d").date()
        for date in [
            "2025-02-05", "2025-03-23", "2025-03-30", "2025-03-31", "2025-04-01",
            "2025-05-01", "2025-06-06", "2025-06-07", "2025-06-08", "2025-07-04",
            "2025-07-05", "2025-08-14", "2025-09-04", "2025-11-09", "2025-12-25"
        ]
    }
    start_date = datetime(2025, 7, 13).date()
    valid_dates = []
    current_date = start_date


    while len(valid_dates) < days:
        if current_date.weekday() != 6 and current_date not in holidays:
            valid_dates.append(current_date)
        current_date += timedelta(days=1)


    

    schedule = []
    machine_index = 0

    for i in range(days):
        daily_batch = records[machine_index:machine_index + per_day]
        if not daily_batch:
            break

        date_obj = valid_dates[i]
        for machine in daily_batch:
            # restrict the dats change of pm by putting inside IF code into IF, and vice versa
            if not machine.pm_date:
                machine.pm_date = date_obj

            schedule.append({
                "sno": machine.sno,
                "brand": machine.brand,
                "model": machine.model,
                "tag": machine.tag,
                "serial": machine.serial,
                "desc": machine.desc,
                "building": machine.building,
                "floor": machine.floor,
                "preventive_date": machine.pm_date.strftime("%Y-%m-%d") if machine.pm_date else "N/A",
                "pm_status": machine.pm_status or "Pending"
            })

        machine_index += len(daily_batch)
    try:
        db.session.commit()
        flash("Preventive maintenance schedule generated and saved.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating pm_date: {e}", "danger")

    return render_template("preventive_schedule.html", schedule=schedule, building=building, per_day=per_day, today=datetime.today().date())


# -----------------------------------------------------------------YTM-2-MECHANICAL-------------------------------------------------------------
allowed_config2 = {
    "2A": {
        "floors": ["FF", "GF", "SF", "TF", "GF-WORKSHOP"],
        "categories": ["Normal", "Special", "Automatic Plants", "Steam Generator"]
    },
    "2B": {
        "floors": ["FF", "GF", "SF"],
        "categories": ["Normal", "Special", "Quilting", "Automatic Plants", "Steam Generator"]
    },
}
@app.route("/ytm2_schedule/<building>")
@login_required
def ytm2_schedule(building):
    # Authorization
    if current_user.unit != "YTM-2" and current_user.role != 'master':
        flash("Unauthorized", "danger")
        return redirect("/")

    # Validate allowed config for building
    config = allowed_config2.get(building)
    if not config:
        flash("Invalid building or no config found.", "danger")
        return redirect("/")

    included_floors = config["floors"]
    included_categories = config["categories"]

    # Filter records by unit, building, category and floor
    records = Todo.query.filter(
        and_(
            Todo.unit == "YTM-2",
            Todo.building == building,
            Todo.category.in_(included_categories),
            Todo.floor.in_(included_floors)
        )
    ).all()

    if not records:
        flash("No machines found for selected filters.", "warning")
        return render_template("preventive_schedule.html", schedule=[], building=building)

    total_machines = len(records)
    days = 90
    per_day = ceil(total_machines / days)
    
    # Define holidays and generate valid date list
    holidays = {
        datetime.strptime(date, "%Y-%m-%d").date()
        for date in [
            "2025-02-05", "2025-03-23", "2025-03-30", "2025-03-31", "2025-04-01",
            "2025-05-01", "2025-06-06", "2025-06-07", "2025-06-08", "2025-07-04",
            "2025-07-05", "2025-08-14", "2025-09-04", "2025-11-09", "2025-12-25"
        ]
    }
    start_date = datetime(2025, 7, 13).date()
    valid_dates = []
    current_date = start_date


    while len(valid_dates) < days:
        if current_date.weekday() != 6 and current_date not in holidays:
            valid_dates.append(current_date)
        current_date += timedelta(days=1)


    

    schedule = []
    machine_index = 0

    for i in range(days):
        daily_batch = records[machine_index:machine_index + per_day]
        if not daily_batch:
            break

        date_obj = valid_dates[i]
        for machine in daily_batch:
            # restrict the dats change of pm by putting inside IF code into IF, and vice versa
            if not machine.pm_date:
                machine.pm_date = date_obj

            schedule.append({
                "sno": machine.sno,
                "brand": machine.brand,
                "model": machine.model,
                "tag": machine.tag,
                "serial": machine.serial,
                "desc": machine.desc,
                "building": machine.building,
                "floor": machine.floor,
                "preventive_date": machine.pm_date.strftime("%Y-%m-%d") if machine.pm_date else "N/A",
                "pm_status": machine.pm_status or "Pending"
            })

        machine_index += len(daily_batch)
    try:
        db.session.commit()
        flash("Preventive maintenance schedule generated and saved.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating pm_date: {e}", "danger")

    return render_template("preventive_schedule.html", schedule=schedule, building=building, per_day=per_day, today=datetime.today().date())



# -----------------------------------------------------------------YTM-3-ELECTRICAL-------------------------------------------------------------
allowed_config_el3 = {
    "3A": {
        "floors": ["FF", "GF", "SF", "TF", "SF-WORKSHOP"],
        "categories": ["Cutting", "Packing", "Automatic Plants", "Tracks", "Tables", "Heat Transfer", "Label Printer", "Steam Generator"]
    },
}
@app.route("/ytm3_schedule_electrical/<building>")
@login_required
def ytm3_schedule_electrical(building):
    # Authorization
    if current_user.unit != "YTM-3" and current_user.role != 'master':
        flash("Unauthorized", "danger")
        return redirect("/")

    # Validate allowed config for building
    config = allowed_config_el3.get(building)
    if not config:
        flash("Invalid building or no config found.", "danger")
        return redirect("/")

    included_floors = config["floors"]
    included_categories = config["categories"]

    # Filter records by unit, building, category and floor
    records = Todo.query.filter(
        and_(
            Todo.unit == "YTM-3",
            Todo.building == building,
            Todo.category.in_(included_categories),
            Todo.floor.in_(included_floors)
        )
    ).all()

    if not records:
        flash("No machines found for selected filters.", "warning")
        return render_template("preventive_schedule.html", schedule=[], building=building)

    total_machines = len(records)
    days = 90
    per_day = ceil(total_machines / days)
    
    # Define holidays and generate valid date list
    holidays = {
        datetime.strptime(date, "%Y-%m-%d").date()
        for date in [
            "2025-02-05", "2025-03-23", "2025-03-30", "2025-03-31", "2025-04-01",
            "2025-05-01", "2025-06-06", "2025-06-07", "2025-06-08", "2025-07-04",
            "2025-07-05", "2025-08-14", "2025-09-04", "2025-11-09", "2025-12-25"
        ]
    }
    start_date = datetime(2025, 7, 13).date()
    valid_dates = []
    current_date = start_date


    while len(valid_dates) < days:
        if current_date.weekday() != 6 and current_date not in holidays:
            valid_dates.append(current_date)
        current_date += timedelta(days=1)


    

    schedule = []
    machine_index = 0

    for i in range(days):
        daily_batch = records[machine_index:machine_index + per_day]
        if not daily_batch:
            break

        date_obj = valid_dates[i]
        for machine in daily_batch:
            # restrict the dats change of pm by putting inside IF code into IF, and vice versa
            if not machine.pm_date:
                machine.pm_date = date_obj

            schedule.append({
                "sno": machine.sno,
                "brand": machine.brand,
                "model": machine.model,
                "tag": machine.tag,
                "serial": machine.serial,
                "desc": machine.desc,
                "building": machine.building,
                "floor": machine.floor,
                "preventive_date": machine.pm_date.strftime("%Y-%m-%d") if machine.pm_date else "N/A",
                "pm_status": machine.pm_status or "Pending"
            })

        machine_index += len(daily_batch)
    try:
        db.session.commit()
        flash("Preventive maintenance schedule generated and saved.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating pm_date: {e}", "danger")

    return render_template("preventive_schedule.html", schedule=schedule, building=building, per_day=per_day, today=datetime.today().date())


# -----------------------------------------------------------------YTM-3-MECHANICAL-------------------------------------------------------------
allowed_config3 = {
    "3A": {
        "floors": ["FF", "GF", "SF", "TF", "SF-WORKSHOP"],
        "categories": ["Normal", "Special"]
    },
}
@app.route("/ytm3_schedule/<building>")
@login_required
def ytm3_schedule(building):
    # Authorization
    if current_user.unit != "YTM-3" and current_user.role != 'master':
        flash("Unauthorized", "danger")
        return redirect("/")

    # Validate allowed config for building
    config = allowed_config3.get(building)
    if not config:
        flash("Invalid building or no config found.", "danger")
        return redirect("/")

    included_floors = config["floors"]
    included_categories = config["categories"]

    # Filter records by unit, building, category and floor
    records = Todo.query.filter(
        and_(
            Todo.unit == "YTM-3",
            Todo.building == building,
            Todo.category.in_(included_categories),
            Todo.floor.in_(included_floors)
        )
    ).all()

    if not records:
        flash("No machines found for selected filters.", "warning")
        return render_template("preventive_schedule.html", schedule=[], building=building)

    total_machines = len(records)
    days = 90
    per_day = ceil(total_machines / days)
    
    # Define holidays and generate valid date list
    holidays = {
        datetime.strptime(date, "%Y-%m-%d").date()
        for date in [
            "2025-02-05", "2025-03-23", "2025-03-30", "2025-03-31", "2025-04-01",
            "2025-05-01", "2025-06-06", "2025-06-07", "2025-06-08", "2025-07-04",
            "2025-07-05", "2025-08-14", "2025-09-04", "2025-11-09", "2025-12-25"
        ]
    }
    start_date = datetime(2025, 7, 13).date()
    valid_dates = []
    current_date = start_date


    while len(valid_dates) < days:
        if current_date.weekday() != 6 and current_date not in holidays:
            valid_dates.append(current_date)
        current_date += timedelta(days=1)


    

    schedule = []
    machine_index = 0

    for i in range(days):
        daily_batch = records[machine_index:machine_index + per_day]
        if not daily_batch:
            break

        date_obj = valid_dates[i]
        for machine in daily_batch:
            # restrict the dats change of pm by putting inside IF code into IF, and vice versa
            if not machine.pm_date:
                machine.pm_date = date_obj

            schedule.append({
                "sno": machine.sno,
                "brand": machine.brand,
                "model": machine.model,
                "tag": machine.tag,
                "serial": machine.serial,
                "desc": machine.desc,
                "building": machine.building,
                "floor": machine.floor,
                "preventive_date": machine.pm_date.strftime("%Y-%m-%d") if machine.pm_date else "N/A",
                "pm_status": machine.pm_status or "Pending"
            })

        machine_index += len(daily_batch)
    try:
        db.session.commit()
        flash("Preventive maintenance schedule generated and saved.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating pm_date: {e}", "danger")

    return render_template("preventive_schedule.html", schedule=schedule, building=building, per_day=per_day, today=datetime.today().date())



# ------------------------------------------------------------YTM-7-ELECTRICAL------------------------------------------------------------------
allowed_config_el7 = {
    "A": {
        "floors": ["FF", "GF-TRAINING", "SF", "TF"],
        "categories": ["Automatic Plants", "Cutting", "Tracks", "Packing", "Tables", "Steam Generator", "Label Printer", "Heat Transfer", "Pillow Turner", "Quilting", "Embroidery"]
    },
    "B": {
        "floors": ["FF", "GF-WORKSHOP", "SF", "TF"],
        "categories": ["Automatic Plants", "Cutting", "Tracks", "Packing", "Tables", "Steam Generator", "Label Printer", "Heat Transfer", "Pillow Turner", "Quilting", "Embroidery"]
    },
    "C": {
        "floors": ["FF", "SF"],
        "categories": ["Automatic Plants", "Cutting", "Tracks", "Packing", "Tables", "Steam Generator", "Label Printer", "Heat Transfer", "Pillow Turner", "Quilting", "Embroidery"]
    },
    "E": {
        "floors": ["GF", "SF", "TF"],
        "categories": ["Automatic Plants", "Cutting", "Tracks", "Packing", "Tables", "Steam Generator", "Label Printer", "Heat Transfer", "Pillow Turner", "Quilting", "Embroidery"]
    },
    "F": {
        "floors": ["GF", "SF", "TF"],
        "categories": ["Automatic Plants", "Cutting", "Tracks", "Packing", "Tables", "Steam Generator", "Label Printer", "Heat Transfer", "Pillow Turner", "Quilting", "Embroidery"]
    },
    "Water-Jet": {
        "floors": ["FF", "GF"],
        "categories": ["Automatic Plants", "Cutting", "Tracks", "Packing", "Tables", "Steam Generator", "Label Printer", "Heat Transfer", "Pillow Turner", "Quilting", "Embroidery"]
    },
    "G": {
        "floors": ["FF"],
        "categories": ["Washing"]
    },
}
@app.route("/ytm7_schedule_electrical/<building>")
@login_required
def ytm7_schedule_electrical(building):
    # Authorization
    if current_user.unit != "YTM-7" and current_user.role != 'master':
        flash("Unauthorized", "danger")
        return redirect("/")

    # Validate allowed config for building
    config = allowed_config_el7.get(building)
    if not config:
        flash("Invalid building or no config found.", "danger")
        return redirect("/")

    included_floors = config["floors"]
    included_categories = config["categories"]

    # Filter records by unit, building, category and floor
    records = Todo.query.filter(
        and_(
            Todo.unit == "YTM-7",
            Todo.building == building,
            Todo.category.in_(included_categories),
            Todo.floor.in_(included_floors)
        )
    ).all()

    if not records:
        flash("No machines found for selected filters.", "warning")
        return render_template("preventive_schedule.html", schedule=[], building=building)

    total_machines = len(records)
    days = 90
    per_day = ceil(total_machines / days)
    
    # Define holidays and generate valid date list
    holidays = {
        datetime.strptime(date, "%Y-%m-%d").date()
        for date in [
            "2025-02-05", "2025-03-23", "2025-03-30", "2025-03-31", "2025-04-01",
            "2025-05-01", "2025-06-06", "2025-06-07", "2025-06-08", "2025-07-04",
            "2025-07-05", "2025-08-14", "2025-09-04", "2025-11-09", "2025-12-25"
        ]
    }
    start_date = datetime(2025, 7, 13).date()
    valid_dates = []
    current_date = start_date


    while len(valid_dates) < days:
        if current_date.weekday() != 6 and current_date not in holidays:
            valid_dates.append(current_date)
        current_date += timedelta(days=1)


    

    schedule = []
    machine_index = 0

    for i in range(days):
        daily_batch = records[machine_index:machine_index + per_day]
        if not daily_batch:
            break

        date_obj = valid_dates[i]
        for machine in daily_batch:
            # restrict the dats change of pm by putting inside IF code into IF, and vice versa
            if not machine.pm_date:
                machine.pm_date = date_obj

            schedule.append({
                "sno": machine.sno,
                "brand": machine.brand,
                "model": machine.model,
                "tag": machine.tag,
                "serial": machine.serial,
                "desc": machine.desc,
                "building": machine.building,
                "floor": machine.floor,
                "preventive_date": machine.pm_date.strftime("%Y-%m-%d") if machine.pm_date else "N/A",
                "pm_status": machine.pm_status or "Pending"
            })

        machine_index += len(daily_batch)
    try:
        db.session.commit()
        flash("Preventive maintenance schedule generated and saved.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating pm_date: {e}", "danger")

    return render_template("preventive_schedule.html", schedule=schedule, building=building, per_day=per_day, today=datetime.today().date())


# ------------------------------------------------------------YTM-7-MECHANICAL------------------------------------------------------------------
allowed_config7 = {
    "A": {
        "floors": ["FF", "GF-TRAINING", "SF", "TF"],
        "categories": ["Normal", "Special"]
    },
    "B": {
        "floors": ["FF", "GF-WORKSHOP", "SF", "TF"],
        "categories": ["Normal", "Special"]
    },
    "C": {
        "floors": ["FF", "SF"],
        "categories": ["Normal", "Special"]
    },
    "E": {
        "floors": ["GF", "SF", "TF"],
        "categories": ["Normal", "Special"]
    },
    "F": {
        "floors": ["GF", "SF", "TF"],
        "categories": ["Normal", "Special"]
    },
    "Water-Jet": {
        "floors": ["FF", "GF"],
        "categories": ["Normal", "Special"]
    },
}
@app.route("/ytm7_schedule/<building>")
@login_required
def ytm7_schedule(building):
    # Authorization
    if current_user.unit != "YTM-7" and current_user.role != 'master':
        flash("Unauthorized", "danger")
        return redirect("/")

    # Validate allowed config for building
    config = allowed_config7.get(building)
    if not config:
        flash("Invalid building or no config found.", "danger")
        return redirect("/")

    included_floors = config["floors"]
    included_categories = config["categories"]

    # Filter records by unit, building, category and floor
    records = Todo.query.filter(
        and_(
            Todo.unit == "YTM-7",
            Todo.building == building,
            Todo.category.in_(included_categories),
            Todo.floor.in_(included_floors)
        )
    ).all()

    if not records:
        flash("No machines found for selected filters.", "warning")
        return render_template("preventive_schedule.html", schedule=[], building=building)

    total_machines = len(records)
    days = 90
    per_day = ceil(total_machines / days)
    
    # Define holidays and generate valid date list
    holidays = {
        datetime.strptime(date, "%Y-%m-%d").date()
        for date in [
            "2025-02-05", "2025-03-23", "2025-03-30", "2025-03-31", "2025-04-01",
            "2025-05-01", "2025-06-06", "2025-06-07", "2025-06-08", "2025-07-04",
            "2025-07-05", "2025-08-14", "2025-09-04", "2025-11-09", "2025-12-25"
        ]
    }
    start_date = datetime(2025, 7, 13).date()
    valid_dates = []
    current_date = start_date


    while len(valid_dates) < days:
        if current_date.weekday() != 6 and current_date not in holidays:
            valid_dates.append(current_date)
        current_date += timedelta(days=1)


    

    schedule = []
    machine_index = 0

    for i in range(days):
        daily_batch = records[machine_index:machine_index + per_day]
        if not daily_batch:
            break

        date_obj = valid_dates[i]
        for machine in daily_batch:
            # restrict the dats change of pm by putting inside IF code into IF, and vice versa
            if not machine.pm_date:
                machine.pm_date = date_obj

            schedule.append({
                "sno": machine.sno,
                "brand": machine.brand,
                "model": machine.model,
                "tag": machine.tag,
                "serial": machine.serial,
                "desc": machine.desc,
                "building": machine.building,
                "floor": machine.floor,
                "preventive_date": machine.pm_date.strftime("%Y-%m-%d") if machine.pm_date else "N/A",
                "pm_status": machine.pm_status or "Pending"
            })

        machine_index += len(daily_batch)
    try:
        db.session.commit()
        flash("Preventive maintenance schedule generated and saved.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating pm_date: {e}", "danger")

    return render_template("preventive_schedule.html", schedule=schedule, building=building, per_day=per_day, today=datetime.today().date())


# ---------------------------------------PERFORM---PREVENTIVE---------------------------------------------- 
@app.route("/perform_pm/<int:sno>", methods=["GET", "POST"])
@login_required
def perform_pm(sno):
    return_url = request.args.get("return_url", "/")  # default fallback
    todo = Todo.query.get_or_404(sno)

    if current_user.role != 'master' and todo.unit != current_user.unit:
        flash("Unauthorized", "danger")
        return redirect(return_url)

    # if todo.pm_date != datetime.today().date():
    #     flash("PM can only be performed on the scheduled date.", "warning")
    #     return redirect(return_url)

    CHECKLIST_ITEMS = [
        "Plunger", "Oil Pump", "Oil Leakage", "Oil Filter", "Valve",
        "Bell Cover", "Belt", "Stuffing/Block", "Motor", "Panel",
        "Bobbin Case", "Boot/Boot Screw", "Tension Spring", "Main Cam", "Push Rod",
        "Needle Plate", "Pressure Spring", "Tension Rod", "Residual Thread", "Cleaning",
        "Machine Safety Equipment", "Needle Drag", "Check Drag", "Hydraulic pipe"
    ]

    if request.method == "POST":
        structured = []
        for i, desc in enumerate(CHECKLIST_ITEMS, start=1):
            structured.append({
                "sno": i,
                "desc": desc,
                "check": request.form.get(f"check_{i}", ""),
                "repaired": "yes" if request.form.get(f"repaired_{i}") else "no",
                "replaced": "yes" if request.form.get(f"replaced_{i}") else "no",
                "remarks": request.form.get(f"remarks_{i}", "")
            })

        todo.pm_status = "Done"
        todo.checklist = json.dumps(structured)
        db.session.commit()
        flash("Checklist submitted and PM marked as Done.", "success")
        return redirect(return_url)

    return render_template("perform_pm.html", todo=todo, checklist_items=CHECKLIST_ITEMS, return_url=return_url)


# ---------------------------VIEW CHECKLIST---------------------------------

@app.route("/view_checklist/<int:sno>")
@login_required
def view_checklist(sno):
    todo = Todo.query.get_or_404(sno)

    # Only master users or the assigned unit user can view
    if current_user.role != 'master' and todo.unit != current_user.unit:
        flash("Unauthorized access.", "danger")
        return redirect("/")

    return render_template("view_checklist.html", todo=todo)

# =============TEMPLATE FILTERS=============

@app.template_filter('nl2br')
def nl2br(value):
    return value.replace('\n', '<br>\n')


@app.template_filter("loads")
def loads_filter(value):
    try:
        return json.loads(value)
    except:
        return []



# ----------------------------PM SCHEDULE LOGS DOWNLOADING-------------------------------
@app.route("/download_log")
@login_required
def download_log():

    # Allow only authorized units or master
    allowed_units = ["YTM-1", "YTM-2", "YTM-3", "YTM-7"]
    if current_user.unit not in allowed_units and current_user.role != 'master':
        flash("Unauthorized", "danger")
        return redirect("/")

    # 1. Determine selected unit (master can select any via ?unit=YTM-2)
    selected_unit = current_user.unit if current_user.role != 'master' else request.args.get("unit", "YTM-1")

    # 2. Get selected building if passed (master can filter with ?building=2A)
    selected_building = request.args.get("building", None)

    # 3. Base query
    query = Todo.query.filter(Todo.unit == selected_unit)

    # 4. Filter by building only if provided
    if selected_building:
        query = query.filter(
            and_(
                Todo.building == selected_building,
                Todo.pm_status == "Done")
        )

    # 5. No filter on PM status (you want all: Pending, Done, etc.)
    records = query.order_by(Todo.pm_date).all()

    log_rows = []

    for r in records:
        if not r.checklist:
            continue  # skip if no checklist

        try:
            checklist = json.loads(r.checklist)
        except:
            continue  # skip invalid checklist format

        for row in checklist:
            log_rows.append({
                "Machine S.No": r.sno,
                "Unit": r.unit,
                "Building": r.building,
                "Floor": r.floor,
                "PM Date": r.pm_date.strftime('%Y-%m-%d') if r.pm_date else "",
                # "Performed By": r.pm_by if hasattr(r, 'pm_by') else "",
                "Description": r.desc,
                "Tag No": r.tag,
                "Serial No": r.serial,
                "Checklist Item": row["desc"],
                "Check": row["check"],
                "Repaired": row["repaired"],
                "Replaced": row["replaced"],
                "Remarks": row["remarks"]
            })

    df = pd.DataFrame(log_rows)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="PM_Log_Detailed")
    output.seek(0)

    return send_file(
        output,
        download_name="PM_Log_Detailed.xlsx",
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )




# ------------------------------------------PM SCHEDULE DOWNLOADING-----------------------------------
@app.route("/download_schedule/<building>")
@login_required
def download_schedule(building):
    # Allow only authorized units or master
    allowed_units = ["YTM-1", "YTM-2", "YTM-3", "YTM-7"]

    # Determine which unit's data to fetch
    if current_user.role == 'master':
        selected_unit = request.args.get("unit")
        if not selected_unit or selected_unit not in allowed_units:
            flash("Please select a valid unit.", "danger")
            return redirect("/")
    else:
        selected_unit = current_user.unit
        if selected_unit not in allowed_units:
            flash("Unauthorized", "danger")
            return redirect("/")

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
        "Brand": record.brand,
        "Model": record.model,
        "Description": record.desc,
        "Tag": record.tag,
        "Serial": record.serial,
        "Building": record.building,
        "Floor": record.floor,
        "PM Date": record.pm_date.strftime("%Y-%m-%d") if record.pm_date else "N/A"
    } for record in records]

    df = pd.DataFrame(data)

    # Create in-memory Excel file
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="PM Schedule")
    output.seek(0)

    return send_file(output, as_attachment=True, download_name=f"{selected_unit}_{building}_PM_Schedule.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

