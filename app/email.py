from flask import url_for, current_app
from flask_mail import Message
from app import mail

def send_verification_email(user):
    token = user.verification_token
    verify_url = url_for('verify_email', token=token, _external=True)

    msg = Message(
        subject="Verify Your StrideSync Account",
        sender=current_app.config['MAIL_DEFAULT_SENDER'],
        recipients=[user.email]
    )
    msg.body = f"Hi {user.username or 'there'},\n\nClick the link below to verify your account:\n\n{verify_url}\n\nIf you didn't sign up, you can ignore this email."
    msg.html = f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="font-family: Arial, sans-serif; background-color: #f8f9fa; padding: 30px;">
    <tr>
        <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="background-color: white; border-radius: 8px; overflow: hidden; box-shadow: 0 0 10px rgba(0,0,0,0.05);">
            <tr>
            <td style="padding: 30px; text-align: center;">
                <h2 style="color: #000;">Verify your StrideSync account</h2>
                <p style="color: #555; font-size: 16px;">Hi {user.username or 'there'},</p>
                <p style="color: #555; font-size: 16px;">
                Thanks for signing up! Please click the button below to verify your email address and activate your account.
                </p>
                <a href="{verify_url}" style="display: inline-block; margin: 20px 0; padding: 12px 24px; background-color: #000; color: #fff; text-decoration: none; border-radius: 4px;">
                Verify Account
                </a>
                <p style="color: #888; font-size: 14px;">
                If you didn’t create this account, feel free to ignore this email.
                </p>
                <p style="color: #aaa; font-size: 12px; margin-top: 30px;">&copy; 2025 StrideSync</p>
            </td>
            </tr>
        </table>
        </td>
    </tr>
    </table>
    """

    mail.send(msg)
