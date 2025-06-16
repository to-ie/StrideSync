from app import app
from app.forms import LoginForm
from flask import render_template, flash, redirect, url_for
from flask_login import current_user, login_user
import sqlalchemy as sa
from app import db
from flask import request
from urllib.parse import urlsplit
from app.forms import RegisterForm
from app.models import User, UserRole, Run
from flask_login import logout_user
from app.email import send_verification_email
from app.models import Run, Challenge
from datetime import datetime, timedelta
from calendar import month_abbr
from collections import defaultdict
from flask_login import login_required, current_user


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
        return redirect(url_for('dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        email_input = form.email.data.strip().lower()
        user = db.session.scalar(
            sa.select(User).where(User.email == email_input)
        )
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
        login_user(user, remember=form.remember_me.data)
        flash('Your account was created! Please check your inbox to verify your email.', 'success')
        return redirect(url_for('index'))
    return render_template('register.html', title='Register', form=form)


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
    # Fetch user's runs
    runs = db.session.scalars(
        sa.select(Run).where(Run.user_id == current_user.id)
    ).all()

    # Create dictionary: {date: total_distance}
    distance_by_date = {}
    for run in runs:
        run_date = run.date.date()
        distance_by_date[run_date] = distance_by_date.get(run_date, 0) + run.distance

    # Align to most recent Monday, 365 days ago
    today = datetime.utcnow().date()
    start_date = today - timedelta(days=364)
    while start_date.weekday() != 0:  # Make sure week starts on Monday
        start_date -= timedelta(days=1)

    # Build heatmap grid (53 weeks × 7 days)
    heatmap_cells = []
    month_labels = []
    current_month = None

    for week in range(53):
        column = []
        week_start = start_date + timedelta(weeks=week)

        # Month label (for first day of the week)
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

    # Recent 5 runs
    recent_runs = db.session.scalars(
        sa.select(Run)
        .where(Run.user_id == current_user.id)
        .order_by(Run.date.desc())
        .limit(5)
    ).all()

    # Active challenges
    live_challenges = db.session.scalars(
        sa.select(Challenge).where(Challenge.is_active == True)
    ).all()

    return render_template(
        "dashboard.html",
        user=current_user,
        runs=runs,
        recent_runs=recent_runs,
        live_challenges=live_challenges,
        heatmap_cells=heatmap_cells,
        month_labels=month_labels
    )
