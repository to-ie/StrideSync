from flask import render_template, flash, redirect, url_for, request, session, abort, jsonify
from flask_login import login_user, logout_user, current_user, login_required
import sqlalchemy as sa
from app import db, login_manager, app
from app.forms import (
    LoginForm, RegisterForm, LogActivityForm,
    EditRunForm, DeleteRunForm, CreateGroupForm
)
from app.models import (
    User, UserRole, Run, Group,
    GroupInvite, user_groups, run_groups
)
from app.email import (
    send_verification_email, send_group_invite_email
)
from app.utils.token import generate_group_invite_token, verify_group_invite_token
from datetime import datetime, timedelta


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


@app.route('/delete_run/<int:run_id>', methods=['POST'])
@login_required
def delete_run(run_id):
    run = db.session.get(Run, run_id)
    if run and run.user_id == current_user.id:
        # Remove the associations with groups and user
        for group in run.groups:
            group.runs.remove(run)  # Remove the run from associated groups
        db.session.delete(run)
        db.session.commit()
        flash('Activity deleted. All associated group associations were removed.', 'info')
    return redirect(url_for('dashboard'))


@app.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if user and user.id == current_user.id:
        # Remove the user's associations from any groups
        for group in user.groups:
            group.members.remove(user)
        for group in user.admin_of_groups:
            group.admins.remove(user)
        
        # Delete any runs associated with the user
        for run in user.runs:
            db.session.delete(run)
        
        db.session.delete(user)
        db.session.commit()
        flash('Your account and all related data (runs and groups) have been deleted.', 'info')
        return redirect(url_for('index'))

    flash('You cannot delete another user.', 'danger')
    return redirect(url_for('dashboard'))


@app.route('/delete_group/<int:group_id>', methods=['POST'])
@login_required
def delete_group(group_id):
    group = db.session.get(Group, group_id)
    if not group or current_user not in group.admins:
        abort(403)

    # Keep the runs but remove the group association
    for run in group.runs:
        run.groups.remove(group)  # Remove the group association from runs

    db.session.delete(group)
    db.session.commit()
    flash(f"The group '{group.name}' has been deleted. The runs are kept but no longer associated.", "info")
    return redirect(url_for('dashboard'))


@app.route('/groups/<int:group_id>/remove_run/<int:run_id>', methods=['POST'])
@login_required
def remove_run_from_group(group_id, run_id):
    run = db.session.get(Run, run_id)
    group = db.session.get(Group, group_id)

    if not run or not group:
        abort(404)

    if run.user_id != current_user.id:
        abort(403)

    # Remove the group association from the run
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
