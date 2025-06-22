from flask import url_for, current_app
from flask_mail import Message
from app import mail
from app.utils.token import generate_group_invite_token


def send_verification_email(user):
    token = user.verification_token
    verify_url = url_for('verify_email', token=token, _external=True)

    subject = "Verify Your StrideSync Account"
    recipient = user.email
    sender = current_app.config['MAIL_DEFAULT_SENDER']
    username = user.username or 'there'

    msg = Message(subject=subject, sender=sender, recipients=[recipient])

    # Plain text fallback
    msg.body = f"""Hi {username},

Click the link below to verify your account:

{verify_url}

If you didn't sign up, you can ignore this email."""

    # HTML version
    msg.html = _build_email_html(
        title="Verify your StrideSync account",
        greeting=f"Hi {username},",
        body="Thanks for signing up! Please click the button below to verify your email address and activate your account.",
        action_url=verify_url,
        action_label="Verify Account"
    )

    mail.send(msg)

def send_password_reset_email(user):
    reset_url = url_for('reset_password', token=user.reset_token, _external=True)
    subject = "StrideSync Password Reset"
    recipient = user.email
    sender = current_app.config['MAIL_DEFAULT_SENDER']
    username = user.username or 'there'

    msg = Message(subject=subject, sender=sender, recipients=[recipient])

    # Plain text fallback
    msg.body = f"""Hi {username},

You requested to reset your StrideSync password.

Click the link below to choose a new password:

{reset_url}

If you didn’t request this, you can ignore this email."""

    # HTML version (styled)
    msg.html = _build_email_html(
        title="Reset Your StrideSync Password",
        greeting=f"Hi {username},",
        body="We received a request to reset your password. Click the button below to choose a new one.",
        action_url=reset_url,
        action_label="Reset Password"
    )

    mail.send(msg)


def send_group_invite_email(email, group):
    token = generate_group_invite_token(email, group.id)
    invite_url = url_for('register', _external=True) + f"?invite_token={token}&group_id={group.id}"

    subject = f"You're invited to join '{group.name}' on StrideSync"
    sender = current_app.config['MAIL_DEFAULT_SENDER']

    msg = Message(subject=subject, sender=sender, recipients=[email])

    msg.body = f"""Hi there,

You've been invited to join the group '{group.name}' on StrideSync.

Click the link below to sign up and join the group:

{invite_url}

If you weren't expecting this, you can ignore this email.
"""

    msg.html = _build_email_html(
        title="You're Invited to Join a Group",
        greeting="Hi there,",
        body=f"You've been invited to join the group <strong>{group.name}</strong> on StrideSync.",
        action_url=invite_url,
        action_label="Join the Group"
    )

    mail.send(msg)


def _build_email_html(title, greeting, body, action_url, action_label):
    """Reusable HTML email builder."""
    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="font-family: Arial, sans-serif; background-color: #f8f9fa; padding: 30px;">
      <tr>
        <td align="center">
          <table width="600" cellpadding="0" cellspacing="0" style="background-color: white; border-radius: 8px; overflow: hidden; box-shadow: 0 0 10px rgba(0,0,0,0.05);">
            <tr>
              <td style="padding: 30px; text-align: center;">
                <h2 style="color: #000;">{title}</h2>
                <p style="color: #555; font-size: 16px;">{greeting}</p>
                <p style="color: #555; font-size: 16px;">{body}</p>
                <a href="{action_url}" style="display: inline-block; margin: 20px 0; padding: 12px 24px; background-color: #000; color: #fff; text-decoration: none; border-radius: 4px;">
                  {action_label}
                </a>
                <p style="color: #888; font-size: 14px;">
                  If you weren't expecting this email, you can safely ignore it.
                </p>
                <p style="color: #aaa; font-size: 12px; margin-top: 30px;">&copy; 2025 StrideSync</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
    """

def send_contact_email(name, email, message_text):
    subject = f"New Contact Form Submission from {name}"
    recipient = current_app.config.get('SUPPORT_EMAIL', 'toie@pm.me')
    sender = current_app.config['MAIL_DEFAULT_SENDER']

    msg = Message(subject=subject, sender=sender, recipients=[recipient])
    
    msg.body = f"""New message from StrideSync contact form:

From: {name} <{email}>

Message:
{message_text}
"""

    msg.html = _build_email_html(
        title="New Contact Form Submission",
        greeting=f"From: {name} &lt;{email}&gt;",
        body=message_text.replace('\n', '<br>'),
        action_url="mailto:" + email,
        action_label="Reply"
    )

    mail.send(msg)

def send_admin_registration_alert(user):
    subject = "New User Registered on StrideSync"
    sender = current_app.config['MAIL_DEFAULT_SENDER']
    recipient = "toie@pm.me"

    msg = Message(subject=subject, sender=sender, recipients=[recipient])

    # Plain text fallback
    msg.body = f"""Hello,

A new user just registered on StrideSync:

Username: {user.username}
Email: {user.email}

You can view their details in the admin panel.
"""

    # HTML version (styled to match others)
    msg.html = _build_email_html(
        title="New User Registration",
        greeting="Hello,",
        body=(
            f"A new user just registered on StrideSync:<br><br>"
            f"<strong>Username:</strong> {user.username}<br>"
            f"<strong>Email:</strong> {user.email}<br>"
        ),
        action_url=url_for('admin_panel', _external=True),
        action_label="Open Admin Panel"
    )

    mail.send(msg)

def send_admin_error_alert(error, traceback_str, request):
    subject = "🚨 StrideSync: 500 Internal Server Error"
    sender = current_app.config['MAIL_DEFAULT_SENDER']
    recipient = "toie@pm.me"

    request_info = f"""
    <strong>Path:</strong> {request.path}<br>
    <strong>Method:</strong> {request.method}<br>
    <strong>IP:</strong> {request.remote_addr}<br>
    <strong>User Agent:</strong> {request.user_agent}<br>
    """

    html = _build_email_html(
        title="🚨 500 Error on StrideSync",
        greeting="Hi Admin,",
        body=f"""
        A 500 Internal Server Error occurred on the site:<br><br>
        {request_info}
        <strong>Traceback:</strong><br>
        <pre style='font-size: 13px; background: #f1f1f1; padding: 10px; border-radius: 4px;'>{traceback_str}</pre>
        """,
        action_url='https://dashboard.render.com/web/srv-d1a0rh3ipnbc739k8egg/logs',
        action_label="Open Admin Panel"
    )

    msg = Message(subject=subject, sender=sender, recipients=[recipient])
    msg.body = f"""500 Internal Server Error

Path: {request.path}
Method: {request.method}
IP: {request.remote_addr}
User Agent: {request.user_agent}

Traceback:
{traceback_str}
"""
    msg.html = html
    mail.send(msg)
