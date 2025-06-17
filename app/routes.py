from app import app
from app.forms import LoginForm
from flask import render_template, flash, redirect, url_for
from flask_login import current_user, login_user
import sqlalchemy as sa
from app import db
from flask import request
from urllib.parse import urlsplit
from app.forms import RegisterForm, LogActivityForm
from app.models import User, UserRole, Run
from flask_login import logout_user
from app.email import send_verification_email
from app.models import Run, Challenge
from datetime import datetime, timedelta
from calendar import month_abbr
from collections import defaultdict
from flask_login import login_required, current_user
from flask import session
from flask import abort
from app.forms import EditRunForm, DeleteRunForm

@app.route('/')
@app.route('/index')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    user_count = db.session.scalar(sa.select(sa.func.count()).select_from(User))
    total_distance = db.session.scalar(sa.select(sa.func.sum(Run.distance))) or 0

    return render_template(
        'index.html',
        title='Home',
        user_count=user_count,
        total_distance=total_distance
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_verified:
            return redirect(url_for('dashboard'))
        else:
            flash('Please verify your email before continuing.', 'warning')
            return redirect(url_for('logout'))

    form = LoginForm()
    if form.validate_on_submit():
        email_input = form.email.data.strip().lower()
        user = db.session.scalar(sa.select(User).where(User.email == email_input))

        if user is None or not user.check_password(form.password.data):
            flash('Invalid email or password.', 'danger')
            return redirect(url_for('login'))

        if not user.is_verified:
            flash('Please verify your email before logging in.', 'warning')
            return redirect(url_for('login'))

        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or urlsplit(next_page).netloc != '':
            next_page = url_for('dashboard')
        return redirect(next_page)

    return render_template('login.html', form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        username = form.username.data.strip()
        # Check for duplicates
        if db.session.scalar(sa.select(User).where(User.email == email)):
            flash('Email is already registered.', 'warning')
            return redirect(url_for('register'))
        if db.session.scalar(sa.select(User).where(User.username == username)):
            flash('Username is already taken.', 'warning')
            return redirect(url_for('register'))
        user = User(
            email=email,
            username=username,
            role=UserRole.USER,
            is_verified=False
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        send_verification_email(user)
        flash('Your account was created! Please check your inbox to verify your email before logging in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)


@app.route('/verify/<token>')
def verify_email(token):
    user = db.session.scalar(sa.select(User).where(User.verification_token == token))

    if user is None:
        flash("Invalid or expired verification link.", "danger")
        return redirect(url_for('login'))

    if user.is_verified:
        flash("Your account is already verified.", "info")
    else:
        user.is_verified = True
        db.session.commit()
        flash("Your account has been verified!", "success")

    return redirect(url_for('login'))


@app.template_filter('datetimeformat')
def datetimeformat(value, format='%d-%m-%y'):
    if isinstance(value, str):
        value = datetime.strptime(value, "%Y-%m-%d")
    return value.strftime(format)

@app.route('/dashboard')
@login_required
def dashboard():
    runs = db.session.scalars(
        sa.select(Run).where(Run.user_id == current_user.id)
    ).all()

    distance_by_date = {}
    for run in runs:
        run_date = run.date.date()
        distance_by_date[run_date] = distance_by_date.get(run_date, 0) + run.distance

    today = datetime.utcnow().date()
    start_date = today - timedelta(days=364)
    while start_date.weekday() != 0:
        start_date -= timedelta(days=1)

    heatmap_cells = []
    month_labels = []
    current_month = None

    for week in range(53):
        column = []
        week_start = start_date + timedelta(weeks=week)

        if week_start.month != current_month:
            month_labels.append(month_abbr[week_start.month])
            current_month = week_start.month
        else:
            month_labels.append("")

        for day in range(7):
            date = week_start + timedelta(days=day)
            if date > today:
                column.append(None)
            else:
                column.append({
                    "date": date,
                    "active": date in distance_by_date,
                    "distance": distance_by_date.get(date, 0)
                })
        heatmap_cells.append(column)

    recent_runs = db.session.scalars(
        sa.select(Run)
        .where(Run.user_id == current_user.id)
        .order_by(Run.date.desc())
        .limit(5)
    ).all()

    live_challenges = db.session.scalars(
        sa.select(Challenge).where(Challenge.is_active == True)
    ).all()

    form = LogActivityForm()
    form.groups.choices = [(g.id, g.name) for g in current_user.groups]
    form.challenges.choices = [(c.id, c.name) for c in live_challenges]
    edit_form = EditRunForm()
    delete_form = DeleteRunForm()

    return render_template(
        "dashboard.html",
        user=current_user,
        runs=runs,
        recent_runs=recent_runs,
        heatmap_cells=heatmap_cells,
        month_labels=month_labels,
        live_challenges=live_challenges,
        form=form,
        edit_form=edit_form,
        delete_form=delete_form
    )

@app.route('/log_activity', methods=['POST'])
@login_required
def log_activity():
    form = LogActivityForm()
    form.groups.choices = [(g.id, g.name) for g in current_user.groups]
    live_challenges = db.session.scalars(
        sa.select(Challenge).where(Challenge.is_active == True)
    ).all()
    form.challenges.choices = [(c.id, c.name) for c in live_challenges]

    if form.validate_on_submit():
        # Convert Decimal to float
        distance = float(form.distance.data)
        total_seconds = (form.hours.data or 0) * 3600 + (form.minutes.data or 0) * 60

        if total_seconds == 0 or distance <= 0:
            flash("Time and distance must be greater than zero.", "danger")
            session["open_activity_modal"] = True
            return redirect(url_for('dashboard'))

        pace = total_seconds / distance

        run = Run(
            user_id=current_user.id,
            date=form.date.data,
            distance=distance,
            time=total_seconds,
            pace=pace
        )
        db.session.add(run)
        db.session.commit()
        flash("Activity logged successfully!", "success")
        session.pop("open_activity_modal", None)
        return redirect(url_for('dashboard'))

    flash("There was an error logging your activity.", "danger")
    session["open_activity_modal"] = True
    return redirect(url_for('dashboard'))


@app.route('/edit_run/<int:run_id>', methods=['POST'])
@login_required
def edit_run(run_id):
    run = db.session.get(Run, run_id)
    if run and run.user_id == current_user.id:
        date = request.form.get('date')
        distance = float(request.form.get('distance'))
        time = int(request.form.get('time')) * 60  # Convert to seconds
        pace = round(time / distance, 2) if distance > 0 else 0

        run.date = datetime.strptime(date, "%Y-%m-%d")
        run.distance = distance
        run.time = time
        run.pace = pace

        db.session.commit()
        flash('Run updated.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/delete_run/<int:run_id>', methods=['POST'])
@login_required
def delete_run(run_id):
    run = db.session.get(Run, run_id)
    if run and run.user_id == current_user.id:
        db.session.delete(run)
        db.session.commit()
        flash('Run deleted.', 'info')
    return redirect(url_for('dashboard'))