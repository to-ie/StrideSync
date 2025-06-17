from flask import (
    render_template, flash, redirect, url_for,
    request, session, abort, jsonify
)
from flask_login import (
    login_user, logout_user, current_user, login_required
)

import sqlalchemy as sa

from sqlalchemy import select, func, and_
from urllib.parse import urlsplit
from datetime import datetime, timedelta
from calendar import month_abbr

from app import app, db
from app.forms import (
    LoginForm, RegisterForm, LogActivityForm,
    EditRunForm, DeleteRunForm, CreateGroupForm
)
from app.models import (
    User, UserRole, Run, Group,
    GroupInvite, user_groups, run_groups
)

from app.utils.token import generate_group_invite_token, verify_group_invite_token

from app.email import (
    send_verification_email, send_group_invite_email
)
from app.utils.token import generate_group_invite_token




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
            # Store the invite details in session
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


    form = LogActivityForm()
    form.groups.choices = [(g.id, g.name) for g in current_user.groups]

    edit_form = EditRunForm()
    edit_form.groups.choices = [(g.id, g.name) for g in current_user.groups]

    delete_form = DeleteRunForm()
    create_group_form = CreateGroupForm()


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
        create_group_form=create_group_form
    )

@app.route('/log_activity', methods=['POST'])
@login_required
def log_activity():
    form = LogActivityForm()
    form.groups.choices = [(g.id, g.name) for g in current_user.groups]

    if form.validate_on_submit():
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
        return redirect(url_for('dashboard'))

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


    if run and run.user_id == current_user.id:
        date = request.form.get('date')
        distance = float(request.form.get('distance'))
        time = int(request.form.get('time')) * 60  # seconds
        pace = round(time / distance, 2) if distance > 0 else 0

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
    return redirect(url_for('dashboard'))


@app.route('/delete_run/<int:run_id>', methods=['POST'])
@login_required
def delete_run(run_id):
    run = db.session.get(Run, run_id)
    if run and run.user_id == current_user.id:
        db.session.delete(run)
        db.session.commit()
        flash('Activity deleted.', 'info')
    return redirect(url_for('dashboard'))

@app.route('/groups/create', methods=['POST'])
@login_required
def create_group():
    create_group_form = CreateGroupForm()
    if create_group_form.validate_on_submit():
        group = Group(
            name=create_group_form.name.data.strip(),
            description=create_group_form.description.data.strip()
        )
        group.members.append(current_user)
        group.admins.append(current_user)
        db.session.add(group)
        db.session.commit()
        return redirect(url_for('view_group', group_id=group.id))

    flash("Failed to create group. Please check the form.", "danger")
    session['open_group_modal'] = True

    return render_template(
        "dashboard.html",
        user=current_user,
        runs=runs,
        recent_runs=recent_runs,
        heatmap_cells=heatmap_cells,
        month_labels=month_labels,
        form=LogActivityForm(),
        edit_form=EditRunForm(),
        delete_form=DeleteRunForm(),
        create_group_form=create_group_form
    )


@app.route('/groups/<int:group_id>')
@login_required
def view_group(group_id):
    group = db.session.get(Group, group_id)
    if not group:
        abort(404)
    

    # Check if the current user is part of the group
    if current_user not in group.members:
        flash("You are not a member of this group.", "warning")  #
        return redirect(url_for('dashboard')) 

        
    # ✅ Top 5 by total distance (group-linked runs only)
    top_distance = db.session.execute(
        sa.select(User.username, sa.func.sum(Run.distance).label('total_distance'))
        .select_from(User)
        .join(Run, Run.user_id == User.id)
        .join(run_groups, run_groups.c.run_id == Run.id)
        .where(run_groups.c.group_id == group_id)
        .group_by(User.username)
        .order_by(sa.desc('total_distance'))
        .limit(5)
    ).all()


    # ✅ Top 5 by number of runs (group-linked runs only)
    top_runs = db.session.execute(
        sa.select(User.username, sa.func.count(Run.id).label('run_count'))
        .join(Run, Run.user_id == User.id)
        .join(run_groups, run_groups.c.run_id == Run.id)
        .where(run_groups.c.group_id == group_id)
        .group_by(User.username)
        .order_by(sa.desc('run_count'))
        .limit(5)
    ).all()

    # ✅ Top 5 by best average pace (from last 5 group-linked runs per user)
    pace_data = []
    for user in group.members:
        recent_runs = db.session.scalars(
            sa.select(Run)
            .join(run_groups, run_groups.c.run_id == Run.id)
            .where(
                Run.user_id == user.id,
                run_groups.c.group_id == group_id
            )
            .order_by(Run.date.desc())
            .limit(5)
        ).all()
        if recent_runs:
            avg_pace = sum(run.pace for run in recent_runs) / len(recent_runs)
            pace_data.append((user.username, avg_pace))
    top_pace = sorted(pace_data, key=lambda x: x[1])[:5]  # lower pace = faster

    # ✅ Paginated user runs in the group
    PER_PAGE = 5
    user_runs_paginated = {}

    for member in group.members:
        page = request.args.get(f'page_{member.id}', 1, type=int)

        runs = db.session.scalars(
            sa.select(Run)
            .join(run_groups, run_groups.c.run_id == Run.id)
            .where(
                Run.user_id == member.id,
                run_groups.c.group_id == group.id
            )
            .order_by(Run.date.desc())
            .limit(PER_PAGE)
            .offset((page - 1) * PER_PAGE)
        ).all()

        run_count = db.session.scalar(
            sa.select(sa.func.count(Run.id))
            .join(run_groups, run_groups.c.run_id == Run.id)
            .where(
                Run.user_id == member.id,
                run_groups.c.group_id == group.id
            )
        )

        user_runs_paginated[member.id] = {
            "runs": runs,
            "total": run_count,
            "pages": (run_count + PER_PAGE - 1) // PER_PAGE,
            "current": page,
        }

    print("Top distance data:", top_distance)

    return render_template(
        "group.html",
        group=group,
        is_admin=current_user in group.admins,
        top_distance=top_distance,
        top_runs=top_runs,
        top_pace=top_pace,
        user_runs_paginated=user_runs_paginated
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
        print("🚨 Email error:", e)
        return jsonify({"success": False, "message": "Failed to send email."}), 500

    return jsonify({"success": True, "message": f"Invitation sent to {email}."})

@app.route('/groups/<int:group_id>/delete', methods=['POST'])
@login_required
def delete_group(group_id):
    group = db.session.get(Group, group_id)
    if not group or current_user not in group.admins:
        abort(403)

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