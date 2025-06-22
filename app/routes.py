from flask import (
    render_template, flash, redirect, url_for,
    request, session, abort, jsonify
)
from flask_login import (
    login_user, logout_user, current_user, login_required
)

import sqlalchemy as sa

from sqlalchemy import select, func, and_, desc
from urllib.parse import urlsplit
from datetime import datetime, timedelta
from calendar import month_abbr

from app import app, db
from app.forms import (
    LoginForm, RegisterForm, LogActivityForm,
    EditRunForm, DeleteRunForm, CreateGroupForm, RequestResetForm, ResetPasswordForm
)
from app.models import (
    User, UserRole, Run, Group,
    GroupInvite, user_groups, run_groups
)

from app.utils.token import generate_group_invite_token, verify_group_invite_token

from app.email import (
    send_verification_email, send_group_invite_email, send_password_reset_email,
    send_contact_email, send_admin_registration_alert
)
from app.utils.token import generate_group_invite_token

import secrets

from app.forms import AccountForm

from decimal import Decimal, ROUND_HALF_UP

from collections import Counter, defaultdict

import random

from calendar import month_abbr




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
    invite_token = request.args.get('invite_token')

    # Handle invite token before form submission
    if invite_token:
        data = verify_group_invite_token(invite_token)
        if data:
            session["pending_invite_group_id"] = data["group_id"]
            session["pending_invite_email"] = data["email"]

    # Redirect already logged in users
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        username = form.username.data.strip()

        # Check if email or username is already taken
        if db.session.scalar(sa.select(User).where(User.email == email)):
            flash('Email is already registered.', 'warning')
            return redirect(url_for('register'))
        if db.session.scalar(sa.select(User).where(User.username == username)):
            flash('Username is already taken.', 'warning')
            return redirect(url_for('register'))

        # Create user
        user = User(
            email=email,
            username=username,
            role=UserRole.USER,
            is_verified=False
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        #email admin
        send_admin_registration_alert(user)

        # Check for pending invite and auto-join
        group_id = session.pop("pending_invite_group_id", None)
        invited_email = session.pop("pending_invite_email", None)

        if group_id and invited_email == email:
            group = db.session.get(Group, group_id)
            if group:
                group.members.append(user)
                invite = db.session.scalar(
                    sa.select(GroupInvite).where(
                        sa.and_(
                            GroupInvite.email == email,
                            GroupInvite.group_id == group.id
                        )
                    )
                )
                if invite:
                    db.session.delete(invite)
                db.session.commit()

        # Send email verification
        send_verification_email(user)

        flash('Your account was created! Please check your inbox to verify your email before logging in.', 'success')
        return redirect(url_for('login'))
    if request.method == 'GET' and "pending_invite_email" in session:
        form.email.data = session["pending_invite_email"]

    return render_template('register.html', form=form)

@app.route('/reset-password', methods=['GET', 'POST'])
def request_password_reset():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = RequestResetForm()
    if form.validate_on_submit():
        user = db.session.scalar(sa.select(User).where(User.email == form.email.data.strip().lower()))
        if user:
            user.reset_token = secrets.token_urlsafe(32)
            user.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
            db.session.commit()
            send_password_reset_email(user)  # You must define this
            flash("If the email is registered, you'll receive a reset email.", "info")
        else:
            flash("If the email is registered, you'll receive a reset email.", "info")

        return redirect(url_for('login'))

    return render_template('auth/request_reset.html', form=form)

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    user = db.session.scalar(sa.select(User).where(User.reset_token == token))

    if not user or user.reset_token_expiry < datetime.utcnow():
        flash("Invalid or expired reset link.", "danger")
        return redirect(url_for('login'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        user.reset_token = None
        user.reset_token_expiry = None
        db.session.commit()
        flash("Password reset successfully. You can now log in.", "success")
        return redirect(url_for('login'))

    return render_template('auth/reset_password.html', form=form)

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

    sorted_groups = sorted(current_user.groups, key=lambda g: g.id, reverse=True)

    # Prepare stats variables
    if runs:
        # Sort by date
        runs_sorted = sorted(runs, key=lambda r: r.date)
        first_run_date = runs_sorted[0].date.date()
        last_run_date = runs_sorted[-1].date.date()
        total_days = (last_run_date - first_run_date).days + 1
        weeks_active = max(total_days // 7, 1)

        distances = [r.distance for r in runs]
        paces = [r.pace for r in runs if r.distance >= 1]
        times = [r.time for r in runs]

        # 🏆 Core
        longest_run = max(distances)
        fastest_pace = min(paces)
        day_counts = Counter(r.date.strftime('%A') for r in runs)
        most_frequent_day = day_counts.most_common(1)[0][0]

        # Longest streak
        date_set = set(r.date.date() for r in runs)
        sorted_dates = sorted(date_set)
        longest_streak = current_streak = temp_streak = 1
        for i in range(1, len(sorted_dates)):
            if (sorted_dates[i] - sorted_dates[i - 1]).days == 1:
                temp_streak += 1
                longest_streak = max(longest_streak, temp_streak)
            else:
                temp_streak = 1
        # Current streak
        today = datetime.utcnow().date()
        streak = 0
        for offset in range(0, 1000):
            check = today - timedelta(days=offset)
            if check in date_set:
                streak += 1
            else:
                if offset == 0:  # didn't run today
                    continue
                break
        current_streak = streak

        # 🔄 Consistency
        avg_runs_per_week = round(len(runs) / weeks_active, 1)

        # Top months
        month_counter = Counter(r.date.strftime('%b') for r in runs)
        top_months = ', '.join(m[0] for m in month_counter.most_common(2))

        # ⏱️ Performance (approximate matching for 5k/10k)
        best_5k = best_10k = "–"
        best_5k_time = min((r.time for r in runs if 4.8 <= r.distance <= 5.2), default=None)
        best_10k_time = min((r.time for r in runs if 9.5 <= r.distance <= 10.5), default=None)
        if best_5k_time:
            best_5k = f"{int(best_5k_time // 60)}:{int(best_5k_time % 60):02d}"
        if best_10k_time:
            best_10k = f"{int(best_10k_time // 60)}:{int(best_10k_time % 60):02d}"

        # 💪 Volume & Effort
        total_distance = round(sum(distances), 2)
        total_time_sec = sum(times)
        total_hours = total_time_sec // 3600
        total_minutes = (total_time_sec % 3600) // 60
        avg_distance = round(sum(distances) / len(distances), 2)
        avg_pace_sec = int(sum(paces) / len(paces)) if paces else 0
        avg_pace = f"{avg_pace_sec // 60}:{avg_pace_sec % 60:02d}" if avg_pace_sec else "–"

        # 📅 Time-Based
        month_activity = Counter(r.date.strftime('%B') for r in runs)
        most_active_month = month_activity.most_common(1)[0][0]
        gaps = [(runs_sorted[i + 1].date - runs_sorted[i].date).days for i in range(len(runs_sorted) - 1)]
        longest_gap = max(gaps) if gaps else 0

        stats = {
            "longest_run": round(longest_run, 2),
            "fastest_pace": f"{int(fastest_pace // 60)}:{int(fastest_pace % 60):02d}",
            "longest_streak": longest_streak,
            "most_frequent_day": most_frequent_day,
            "current_streak": current_streak,
            "avg_runs_per_week": avg_runs_per_week,
            "top_months": top_months,
            "best_5k": best_5k,
            "best_10k": best_10k,
            "total_distance": total_distance,
            "total_time": f"{int(total_hours)}h {int(total_minutes)}m",
            "total_runs": len(runs),
            "avg_distance": avg_distance,
            "avg_pace": avg_pace,
            "most_active_month": most_active_month,
            "longest_gap": longest_gap,
            "first_run_date": first_run_date.strftime('%d %b %Y')
        }
    else:
        stats = {
            "longest_run": "–",
            "fastest_pace": "–",
            "longest_streak": 0,
            "most_frequent_day": "–",
            "current_streak": 0,
            "avg_runs_per_week": 0,
            "top_months": "–",
            "best_5k": "–",
            "best_10k": "–",
            "total_distance": 0,
            "total_time": "0h 0m",
            "total_runs": 0,
            "avg_distance": 0,
            "avg_pace": "–",
            "most_active_month": "–",
            "longest_gap": 0,
            "first_run_date": "–"
        }

    # Aggregate distance per day
    distance_by_date = {}
    for run in runs:
        run_date = run.date.date()
        distance_by_date[run_date] = distance_by_date.get(run_date, 0) + run.distance

    # Start date: 52 weeks ago (rounded back to previous Monday)
    today = datetime.utcnow().date()
    start_date = today - timedelta(days=364)
    while start_date.weekday() != 0:
        start_date -= timedelta(days=1)

    # Build heatmap
    heatmap_cells = []
    for week in range(53):
        column = []
        week_start = start_date + timedelta(weeks=week)
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

    # Build month_labels for the first week of each month
    month_labels = {}
    current_month = None
    for i, week in enumerate(heatmap_cells):
        for cell in week:
            if cell:
                cell_month = cell["date"].month
                if cell_month != current_month:
                    current_month = cell_month
                    month_labels[i] = cell["date"].strftime('%b')
                break


    # Recent runs
    recent_runs = db.session.scalars(
        sa.select(Run)
        .where(Run.user_id == current_user.id)
        .order_by(Run.date.desc())
        .limit(5)
    ).all()

    # Forms
    form = LogActivityForm()
    form.groups.choices = [(g.id, g.name) for g in current_user.groups]

    edit_form = EditRunForm()
    edit_form.groups.choices = [(g.id, g.name) for g in current_user.groups]

    delete_form = DeleteRunForm()
    create_group_form = CreateGroupForm()

    # ⏱️ Aggregate by week
    three_months_ago = datetime.utcnow().date() - timedelta(weeks=13)
    progress_runs = [r for r in runs if r.date.date() >= three_months_ago]

    weekly_distance = defaultdict(float)
    weekly_paces = defaultdict(list)
    weekly_labels = {}

    for r in progress_runs:
        run_date = r.date.date()
        year, week, weekday = run_date.isocalendar()
        monday = run_date - timedelta(days=weekday - 1)
        sunday = monday + timedelta(days=6)

        label = f"{monday.day}–{sunday.day} {month_abbr[monday.month]}"
        key = f"{year}-W{week:02d}"

        weekly_distance[key] += float(r.distance)
        if r.distance >= 1:
            weekly_paces[key].append(float(r.pace))

        weekly_labels[key] = label

    # Sort by week
    sorted_keys = sorted(weekly_distance.keys())
    chart_labels = [weekly_labels[k] for k in sorted_keys]
    distance_data = [round(weekly_distance[k], 2) for k in sorted_keys]
    pace_data = [
        round(sum(weekly_paces[k]) / len(weekly_paces[k]), 2) if weekly_paces[k] else None
        for k in sorted_keys
    ]

    progress_charts = {
        "labels": chart_labels,
        "distance": distance_data,
        "pace": pace_data
    }

    return render_template(
        "dashboard.html",
        user=current_user,
        runs=runs,
        recent_runs=recent_runs,
        heatmap_cells=heatmap_cells,
        month_labels=month_labels,
        form=form,
        edit_form=edit_form,
        delete_form=delete_form, 
        create_group_form=create_group_form,
        sorted_groups=sorted_groups,
        progress_charts=progress_charts,
        stats=stats
    )



@app.route('/log_activity', methods=['POST'])
@login_required
def log_activity():
    form = LogActivityForm()
    form.groups.choices = [(g.id, g.name) for g in current_user.groups]

    if form.validate_on_submit():
        raw_distance = form.distance.data
        distance = float(raw_distance.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

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

        selected_group_ids = [int(gid) for gid in request.form.getlist('groups')]
        if selected_group_ids:
            run.groups = db.session.scalars(
                sa.select(Group).where(Group.id.in_(selected_group_ids))
            ).all()

        db.session.add(run)
        db.session.flush()  # ensures run.id is populated

        db.session.commit()
        flash("Activity logged successfully!", "success")
        session.pop("open_activity_modal", None)
        return redirect(request.referrer or url_for('my_activities'))

    flash("There was an error logging your activity.", "danger")
    session["open_activity_modal"] = True
    return redirect(url_for('dashboard'))

@app.route('/edit_run/<int:run_id>', methods=['POST'])
@login_required
def edit_run(run_id):
    run = db.session.get(Run, run_id)

    if not run or run.user_id != current_user.id:
        flash("You are not authorized to edit this run.", "warning")
        return redirect(url_for('dashboard'))

    date = request.form.get('date')
    raw_distance = request.form.get('distance')
    time_minutes = request.form.get('time')

    try:
        # Convert and round distance to 2 decimal places
        distance = float(Decimal(raw_distance).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        time = int(time_minutes) * 60  # total time in seconds
        pace = round(time / distance, 2) if distance > 0 else 0
    except Exception as e:
        flash("Invalid input. Please check your entries.", "danger")
        return redirect(url_for('dashboard'))

    # Update the run
    run.date = datetime.strptime(date, "%Y-%m-%d")
    run.distance = distance
    run.time = time
    run.pace = pace

    # Update group associations
    selected_group_ids = request.form.getlist('groups')
    run.groups = db.session.scalars(
        sa.select(Group).where(Group.id.in_(selected_group_ids))
    ).all()

    db.session.commit()
    flash('Run updated.', 'success')
    return redirect(request.referrer or url_for('my_activities'))

@app.route('/delete_run/<int:run_id>', methods=['POST'])
@login_required
def delete_run(run_id):
    run = db.session.get(Run, run_id)
    if run and run.user_id == current_user.id:
        if run:
            run.groups.clear()  
            db.session.delete(run)

        db.session.delete(run)
        db.session.commit()
        flash('Activity deleted.', 'info')
    return redirect(url_for('dashboard'))

@app.route('/groups/create', methods=['POST'])
@login_required
def create_group():
    create_group_form = CreateGroupForm()

    if create_group_form.validate_on_submit():
        group_name = create_group_form.name.data.strip()
        group_description = create_group_form.description.data.strip()

        # Case-insensitive check for duplicate group name
        existing_group = db.session.scalar(
            sa.select(Group).where(func.lower(Group.name) == group_name.lower())
        )
        if existing_group:
            flash("A group with this name already exists. Please choose a different name.", "warning")
            session['open_group_modal'] = True
            return redirect(url_for('dashboard'))

        # Create and save the group
        group = Group(
            name=group_name,
            description=group_description
        )
        group.members.append(current_user)
        group.admins.append(current_user)

        db.session.add(group)
        db.session.commit()

        flash(f"Group '{group.name}' created successfully.", "success")
        return redirect(url_for('view_group', group_id=group.id))

    # If form did not validate
    flash("Failed to create group. Please check the form.", "danger")
    session['open_group_modal'] = True
    return redirect(url_for('dashboard'))



@app.route('/groups/<int:group_id>')
@login_required
def view_group(group_id):
    group = db.session.get(Group, group_id)
    if not group:
        abort(404)

    if current_user not in group.members:
        flash("You are not a member of this group.", "warning")
        return redirect(url_for('dashboard'))

    # ✅ Top 5 by total distance
    top_distance = db.session.execute(
        sa.select(User.username, func.sum(Run.distance).label('total_distance'))
        .select_from(Run)
        .join(User, Run.user_id == User.id)
        .join(run_groups, run_groups.c.run_id == Run.id)
        .where(run_groups.c.group_id == group.id)
        .group_by(User.username)
        .order_by(desc('total_distance'))
        .limit(5)
    ).all()

    # ✅ Top 5 by number of runs
    top_runs = db.session.execute(
        sa.select(User.username, func.count(Run.id).label('run_count'))
        .join(Run, Run.user_id == User.id)
        .join(run_groups, run_groups.c.run_id == Run.id)
        .where(run_groups.c.group_id == group.id)
        .group_by(User.username)
        .order_by(desc('run_count'))
        .limit(5)
    ).all()

    # ✅ Top 5 by best average pace (last 5 group-linked runs)
    pace_data = []
    for user in group.members:
        recent_runs = db.session.scalars(
            sa.select(Run)
            .join(run_groups, run_groups.c.run_id == Run.id)
            .where(Run.user_id == user.id, run_groups.c.group_id == group.id)
            .order_by(Run.date.desc())
            .limit(5)
        ).all()
        if recent_runs:
            avg_pace = sum(float(r.pace) for r in recent_runs) / len(recent_runs)
            pace_data.append((user.username, avg_pace))
    top_pace = sorted(pace_data, key=lambda x: x[1])[:5]

    # ✅ Paginated runs per user
    PER_PAGE = 5
    user_runs_paginated = {}
    for member in group.members:
        page = request.args.get(f'page_{member.id}', 1, type=int)
        runs = db.session.scalars(
            sa.select(Run)
            .join(run_groups, run_groups.c.run_id == Run.id)
            .where(Run.user_id == member.id, run_groups.c.group_id == group.id)
            .order_by(Run.date.desc())
            .limit(PER_PAGE)
            .offset((page - 1) * PER_PAGE)
        ).all()
        run_count = db.session.scalar(
            sa.select(func.count(Run.id))
            .join(run_groups, run_groups.c.run_id == Run.id)
            .where(Run.user_id == member.id, run_groups.c.group_id == group.id)
        )
        user_runs_paginated[member.id] = {
            "runs": runs,
            "total": run_count,
            "pages": (run_count + PER_PAGE - 1) // PER_PAGE,
            "current": page,
        }

    # ✅ Weekly group stats
    today = datetime.utcnow().date()
    start_of_week = today - timedelta(days=today.weekday())

    weekly_runs = db.session.scalars(
        sa.select(Run)
        .join(run_groups, run_groups.c.run_id == Run.id)
        .where(run_groups.c.group_id == group.id, Run.date >= start_of_week)
    ).all()

    # Define day labels early
    day_labels = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    distance_by_day = {day: 0.0 for day in day_labels}

    weekly_summary = defaultdict(list)
    for run in weekly_runs:
        weekly_summary[run.user_id].append(run)

    group_distance = 0.0
    group_time = 0.0
    group_run_count = 0
    group_paces = []
    group_day_counts = Counter()
    fastest_run = None
    longest_run = None
    user_weekly_stats = {}

    for user_id, runs in weekly_summary.items():
        dists = [float(r.distance) for r in runs]
        times = [float(r.time) for r in runs]
        paces = [float(r.pace) for r in runs if r.distance >= 1]

        user_distance = sum(dists)
        user_time = sum(times)
        user_runs = len(runs)
        user_avg_pace = int(sum(paces) / len(paces)) if paces else None
        user_longest_run = max(dists) if dists else None
        user_fastest_pace = min(paces) if paces else None

        user_weekly_stats[user_id] = {
            "distance": round(user_distance, 2),
            "runs": user_runs,
            "time": user_time,
            "avg_pace": user_avg_pace,
            "longest_run": user_longest_run,
            "fastest_pace": user_fastest_pace,
        }

        group_distance += user_distance
        group_time += user_time
        group_run_count += user_runs
        group_paces.extend(paces)

        for r in runs:
            day = r.date.strftime("%A")
            if day in distance_by_day:
                distance_by_day[day] += float(r.distance)
            group_day_counts[day] += 1
            if not fastest_run or r.pace < fastest_run.pace:
                fastest_run = r
            if not longest_run or r.distance > longest_run.distance:
                longest_run = r

    group_avg_pace = int(sum(group_paces) / len(group_paces)) if group_paces else None
    most_active_day = group_day_counts.most_common(1)[0][0] if group_day_counts else "–"

    # ✅ Progress chart (last 3 months)
    from_date = today - timedelta(weeks=13)
    all_recent_runs = db.session.scalars(
        sa.select(Run)
        .join(run_groups, run_groups.c.run_id == Run.id)
        .where(run_groups.c.group_id == group.id, Run.date >= from_date)
    ).all()


    progress_data = defaultdict(lambda: defaultdict(float))
    week_labels = {}

    for run in all_recent_runs:
        run_date = run.date.date()
        year, week, weekday = run_date.isocalendar()
        monday = run_date - timedelta(days=weekday - 1)
        sunday = monday + timedelta(days=6)
        key = f"{year}-W{week:02d}"
        label = f"{monday.day}–{sunday.day} {month_abbr[monday.month]}"
        progress_data[key][run.user_id] += float(run.distance)
        week_labels[key] = label

    sorted_weeks = sorted(progress_data.keys())
    user_lines = {
        member.username: [
            round(progress_data[week].get(member.id, 0.0), 2)
            for week in sorted_weeks
        ] for member in group.members
    }


    # ✅ Final weekly stats dict
    group_weekly_stats = {
        "total_distance": round(group_distance, 2),
        "total_runs": group_run_count,
        "total_time": group_time,
        "avg_pace": group_avg_pace,
        "most_active_day": most_active_day,
        "fastest_run": fastest_run,
        "longest_run": longest_run,
        "user_stats": user_weekly_stats,
        "distance_chart": {
            "labels": [user.username for user in group.members],
            "data": [user_weekly_stats.get(user.id, {}).get("distance", 0) for user in group.members]
        },
        "daily_chart": {
            "labels": day_labels,
            "data": [round(distance_by_day[d], 2) for d in day_labels]
        },
        "progress_chart": {
            "labels": [week_labels[w] for w in sorted_weeks],
            "series": user_lines
        }
    }

    return render_template(
        "group.html",
        group=group,
        is_admin=current_user in group.admins,
        top_distance=top_distance,
        top_runs=top_runs,
        top_pace=top_pace,
        user_runs_paginated=user_runs_paginated,
        group_weekly_stats=group_weekly_stats
    )


@app.route('/groups/<int:group_id>/invite', methods=['POST'])
@login_required
def invite_to_group(group_id):
    group = db.session.get(Group, group_id)
    if not group or current_user not in group.admins:
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    data = request.get_json()
    email = data.get('email', '').strip().lower()
    if not email:
        return jsonify({"success": False, "message": "Email is required"}), 400

    # Check if user already exists
    existing_user = db.session.scalar(sa.select(User).where(User.email == email))
    if existing_user:
        if existing_user in group.members:
            return jsonify({"success": False, "message": "User is already in the group"}), 409
        group.members.append(existing_user)
        db.session.commit()
        return jsonify({"success": True, "message": f"{existing_user.username} added to the group."})

    # Check if invite already exists
    existing_invite = db.session.scalar(
        sa.select(GroupInvite).where(
            sa.and_(
                GroupInvite.email == email,
                GroupInvite.group_id == group.id
            )
        )
    )
    if existing_invite:
        return jsonify({"success": False, "message": "Invite already sent."}), 409

    # Create invite and send email
    try:
        token = generate_group_invite_token(email=email, group_id=group.id)
        invite = GroupInvite(email=email, group_id=group.id, token=token)
        db.session.add(invite)
        db.session.commit()

        send_group_invite_email(email, group)
    except Exception as e:
        return jsonify({"success": False, "message": "Failed to send email."}), 500

    return jsonify({"success": True, "message": f"Invitation sent to {email}."})

@app.route('/groups/<int:group_id>/delete', methods=['POST'])
@login_required
def delete_group(group_id):
    group = db.session.get(Group, group_id)
    if not group or current_user not in group.admins:
        abort(403)

    # Unlink all runs from the group, but do NOT delete the runs
    for run in group.runs:
        run.groups = [g for g in run.groups if g.id != group.id]

    # Delete any pending invites
    db.session.execute(sa.delete(GroupInvite).where(GroupInvite.group_id == group.id))

    db.session.delete(group)
    db.session.commit()
    flash(f"The group '{group.name}' has been deleted.", "info")
    return redirect(url_for('dashboard'))

@app.route('/groups/<int:group_id>/member/<int:user_id>/runs')
@login_required
def get_member_runs(group_id, user_id):
    PER_PAGE = 10
    page = request.args.get('page', 1, type=int)

    group = db.session.get(Group, group_id)
    if not group or current_user not in group.members:
        abort(403)

    runs = db.session.scalars(
        sa.select(Run)
        .join(run_groups, run_groups.c.run_id == Run.id)
        .where(
            Run.user_id == user_id,
            run_groups.c.group_id == group_id
        )
        .order_by(Run.date.desc())
        .limit(PER_PAGE)
        .offset((page - 1) * PER_PAGE)
    ).all()

    run_count = db.session.scalar(
        sa.select(sa.func.count(Run.id))
        .join(run_groups, run_groups.c.run_id == Run.id)
        .where(
            Run.user_id == user_id,
            run_groups.c.group_id == group_id
        )
    )

    pages = (run_count + PER_PAGE - 1) // PER_PAGE

    return render_template(
        "partials/_member_runs.html",
        runs=runs,
        page=page,
        pages=pages,
        user_id=user_id,
        group_id=group_id
    )

@app.route('/groups/<int:group_id>/remove_run/<int:run_id>', methods=['POST'])
@login_required
def remove_run_from_group(group_id, run_id):
    run = db.session.get(Run, run_id)
    group = db.session.get(Group, group_id)

    if not run or not group:
        abort(404)

    if run.user_id != current_user.id:
        abort(403)

    # Remove the group association
    run.groups = [g for g in run.groups if g.id != group_id]
    db.session.commit()

    flash('Run removed from group. It was not deleted.', 'info')
    return redirect(url_for('view_group', group_id=group_id))

@app.route('/groups/<int:group_id>/leave', methods=['POST'])
@login_required
def leave_group(group_id):
    group = db.session.get(Group, group_id)
    if not group:
        abort(404)

    # Prevent admins from leaving
    if current_user in group.admins:
        flash("As an admin, you must delete the group instead of leaving it.", "warning")
        return redirect(url_for('dashboard'))

    # Remove user from members list
    if current_user in group.members:
        group.members.remove(current_user)
        db.session.commit()
        flash(f"You have left the group '{group.name}'.", "info")

    return redirect(url_for('dashboard'))

@app.route('/my-activities')
@login_required
def my_activities():
    runs = db.session.scalars(
        sa.select(Run).where(Run.user_id == current_user.id).order_by(Run.date.desc())
    ).all()

    form = LogActivityForm()
    form.groups.choices = [(g.id, g.name) for g in current_user.groups]

    edit_form = EditRunForm()
    edit_form.groups.choices = [(g.id, g.name) for g in current_user.groups]

    delete_form = DeleteRunForm()

    return render_template(
        "my_activities.html",
        runs=runs,
        form=form,
        edit_form=edit_form,
        delete_form=delete_form,
        user=current_user
    )

@app.route('/my-groups')
@login_required
def my_groups():
    sorted_groups = sorted(current_user.groups, key=lambda g: g.id, reverse=True)
    create_group_form = CreateGroupForm()
    return render_template(
        "my_groups.html",
        groups=sorted_groups,
        create_group_form=create_group_form,
        user=current_user
    )

@app.route('/groups/<int:group_id>/edit', methods=['POST'])
@login_required
def edit_group(group_id):
    group = db.session.get(Group, group_id)

    if not group or current_user not in group.admins:
        abort(403)

    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()

    if name:
        group.name = name
    group.description = description

    db.session.commit()
    flash("Group details updated.", "success")
    return redirect(url_for('view_group', group_id=group_id))

@app.route('/groups/<int:group_id>/remove_member/<int:user_id>', methods=['POST'])
@login_required
def remove_member_from_group(group_id, user_id):
    group = db.session.get(Group, group_id)
    member = db.session.get(User, user_id)

    if not group or not member:
        abort(404)

    if current_user not in group.admins or member not in group.members:
        abort(403)

    if member == current_user:
        flash("You can't remove yourself. Leave the group instead.", "warning")
        return redirect(url_for('view_group', group_id=group_id))

    # ✅ Remove member from group
    group.members.remove(member)

    # ✅ Also remove this member's runs from the group
    for run in member.runs:
        run.groups = [g for g in run.groups if g.id != group.id]

    db.session.commit()
    flash(f"{member.username} has been removed from the group.", "info")
    return redirect(url_for('view_group', group_id=group_id))

@app.route('/my-account', methods=['GET', 'POST'])
@login_required
def my_account():
    user = current_user

    if request.method == 'POST':
        form = AccountForm()
        if form.validate_on_submit():
            updated = False

            username = form.username.data.strip()
            email = form.email.data.strip().lower()
            password = form.password.data.strip()

            changed_username = username.lower() != user.username.lower()
            changed_email = email != user.email
            changed_password = bool(password)

            # ✅ Username uniqueness check (case-insensitive, excluding self)
            if changed_username:
                existing = db.session.scalar(
                    sa.select(User).where(
                        sa.func.lower(User.username) == username.lower(),
                        User.id != user.id
                    )
                )
                if existing:
                    flash("Username is already taken.", "warning")
                    return redirect(url_for('my_account'))
                user.username = username
                updated = True

            # ✅ Email uniqueness check (excluding self)
            if changed_email:
                existing = db.session.scalar(
                    sa.select(User).where(
                        User.email == email,
                        User.id != user.id
                    )
                )
                if existing:
                    flash("Email is already registered.", "warning")
                    return redirect(url_for('my_account'))

                user.email = email
                user.is_verified = False
                user.verification_token = secrets.token_urlsafe(32)
                db.session.commit()
                send_verification_email(user)
                flash("Email updated. Please verify your new address.", "info")
                logout_user()
                return redirect(url_for('login'))

            # ✅ Password update
            if changed_password:
                user.set_password(password)
                flash("Password updated successfully.", "success")
                updated = True

            if updated:
                db.session.commit()
                flash("Account updated.", "success")
            else:
                flash("No changes made.", "info")

            return redirect(url_for('my_account'))
        else:
            flash("Please correct the errors below.", "danger")
            print("Form errors:", form.errors)

    else:
        form = AccountForm(obj=user)

    return render_template("my_account.html", form=form, user=user)

@app.route('/admin')
@login_required
def admin_panel():
    if current_user.role != UserRole.ADMIN:
        abort(403)

    users = db.session.scalars(sa.select(User)).all()
    groups = db.session.scalars(sa.select(Group)).all()

    user_stats = {
        user.id: {
            "num_runs": len(user.runs),
            "num_groups": len(user.groups)
        }
        for user in users
    }

    group_stats = {
        group.id: {
            "num_users": len(group.members)
        }
        for group in groups
    }

    return render_template(
        "admin.html",
        users=users,
        groups=groups,
        user_stats=user_stats,
        group_stats=group_stats,
        UserRole=UserRole
    )

@app.route('/admin/users/<int:user_id>/promote', methods=['POST'])
@login_required
def admin_promote_user(user_id):
    if current_user.role != UserRole.ADMIN:
        abort(403)

    user = db.session.get(User, user_id)
    if user and user.role != UserRole.ADMIN:
        user.role = UserRole.ADMIN
        db.session.commit()
        flash(f"{user.username} has been promoted to admin.", "info")

    return redirect(url_for('admin_panel'))

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    if current_user.role != UserRole.ADMIN:
        abort(403)

    user = db.session.get(User, user_id)
    if user:
        # Remove from all groups
        for group in list(user.groups):
            group.members.remove(user)

        # Delete groups this user created (if you're tracking that)
        for group in db.session.scalars(sa.select(Group).where(Group.admins.any(id=user.id))):
            db.session.delete(group)

        # Delete runs and group associations
        for run in list(user.runs):
            run.groups.clear()
            db.session.delete(run)

        db.session.delete(user)
        db.session.commit()
        flash(f"{user.username} has been deleted.", "danger")

    return redirect(url_for('admin_panel'))

@app.route('/admin/groups/<int:group_id>/edit', methods=['POST'])
@login_required
def admin_edit_group(group_id):
    if current_user.role != UserRole.ADMIN:
        abort(403)

    group = db.session.get(Group, group_id)
    if not group:
        abort(404)

    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()

    if name:
        group.name = name
    group.description = description

    db.session.commit()
    flash(f"Group '{group.name}' updated.", "success")
    return redirect(url_for('admin_panel'))

@app.route('/admin/groups/<int:group_id>/delete', methods=['POST'])
@login_required
def admin_delete_group(group_id):
    if current_user.role != UserRole.ADMIN:
        abort(403)

    group = db.session.get(Group, group_id)
    if group:
        # Unlink all runs from the group, but do NOT delete the runs
        for run in group.runs:
            run.groups = [g for g in run.groups if g.id != group.id]

        # Delete any pending invites
        db.session.execute(sa.delete(GroupInvite).where(GroupInvite.group_id == group.id))
        db.session.delete(group)
        db.session.commit()
        flash(f"Group '{group.name}' deleted.", "danger")

    return redirect(url_for('admin_panel'))

@app.route('/admin/users/<int:user_id>/verify', methods=['POST'])
@login_required
def admin_verify_user(user_id):
    if current_user.role != UserRole.ADMIN:
        abort(403)

    user = db.session.get(User, user_id)
    if not user:
        abort(404)

    user.is_verified = True
    user.verification_token = ""
    db.session.commit()

    flash(f"{user.username}'s email address has been verified.", "success")
    return redirect(url_for('admin_panel'))

@app.route('/admin/groups/<int:group_id>/remove/<int:user_id>', methods=['POST'])
@login_required
def admin_remove_user_from_group(group_id, user_id):
    if current_user.role != UserRole.ADMIN:
        abort(403)

    group = db.session.get(Group, group_id)
    user = db.session.get(User, user_id)

    if not group or not user:
        abort(404)

    if user in group.members:
        group.members.remove(user)

        # 🚨 Remove all runs by this user from the group
        for run in user.runs:
            run.groups = [g for g in run.groups if g.id != group_id]

        db.session.commit()
        flash(f"{user.username} has been removed from {group.name}.", "info")

    return redirect(url_for('admin_panel'))

@app.route('/admin/users/<int:user_id>/demote', methods=['POST'])
@login_required
def admin_demote_user(user_id):
    if current_user.role != UserRole.ADMIN:
        abort(403)

    user = db.session.get(User, user_id)
    if user and user.role == UserRole.ADMIN and user.id != current_user.id:
        user.role = UserRole.USER
        db.session.commit()
        flash(f"{user.username} has been demoted to regular user.", "info")

    return redirect(url_for('admin_panel'))

@app.route('/admin/users/<int:user_id>/edit', methods=['POST'])
@login_required
def admin_edit_user(user_id):
    if current_user.role != UserRole.ADMIN:
        abort(403)

    user = db.session.get(User, user_id)
    if not user:
        abort(404)

    new_username = request.form.get("username", "").strip()
    new_email = request.form.get("email", "").strip()

    if new_username and new_username != user.username:
        existing_user = db.session.scalar(sa.select(User).where(User.username == new_username))
        if existing_user:
            flash("Username already exists.", "danger")
            return redirect(url_for("admin_panel"))
        user.username = new_username

    if new_email and new_email != user.email:
        existing_email = db.session.scalar(sa.select(User).where(User.email == new_email))
        if existing_email:
            flash("Email address already exists.", "danger")
            return redirect(url_for("admin_panel"))
        user.email = new_email
        # 🛑 DO NOT require re-verification
        user.is_verified = True
        user.verification_token = ""

    db.session.commit()
    flash(f"User updated successfully.", "success")
    return redirect(url_for("admin_panel"))

@app.route('/admin/groups/<int:group_id>/add_user', methods=['POST'])
@login_required
def admin_add_user_to_group(group_id):
    if current_user.role != UserRole.ADMIN:
        abort(403)

    username = request.form.get("username", "").strip()
    group = db.session.get(Group, group_id)
    user = db.session.scalar(sa.select(User).where(User.username == username))

    if not group or not user:
        flash("Group or user not found.", "danger")
    elif user in group.members:
        flash("User is already in the group.", "info")
    else:
        group.members.append(user)
        db.session.commit()
        flash(f"Added {user.username} to {group.name}.", "success")

    return redirect(url_for('admin_panel'))

@app.errorhandler(404)
def not_found_error(error):
    return render_template("404.html"), 404

@app.errorhandler(403)
def forbidden_error(error):
    return render_template("403.html"), 403

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()

    import traceback
    from app.email import send_admin_error_alert

    try:
        tb = traceback.format_exc()
        send_admin_error_alert(error, tb, request)
    except Exception as e:
        app.logger.error(f"Error sending admin alert email: {e}")

    return render_template("500.html"), 500

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        message_body = request.form.get('message', '').strip()
        captcha_answer = request.form.get('captcha', '').strip()
        expected_answer = session.pop('captcha_answer', None)

        if not name or not email or not message_body:
            flash('Please fill in all fields.', 'danger')
            return redirect(url_for('contact'))

        if expected_answer is None or captcha_answer != expected_answer:
            flash('Incorrect CAPTCHA. Please try again.', 'danger')
            return redirect(url_for('contact'))

        try:
            send_contact_email(name, email, message_body)
            flash('Thanks for reaching out! We’ve received your message.', 'success')
        except Exception as e:
            flash('Oops, something went wrong while sending your message.', 'danger')

        return redirect(url_for('contact'))

    # Generate CAPTCHA
    num1 = random.randint(1, 9)
    num2 = random.randint(1, 9)
    operator = random.choice(['+', '-'])
    answer = str(eval(f"{num1}{operator}{num2}"))
    session['captcha_answer'] = answer
    captcha_question = f"What is {num1} {operator} {num2}?"

    return render_template('contact.html', captcha_question=captcha_question)