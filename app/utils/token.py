from itsdangerous import URLSafeTimedSerializer
from flask import current_app

def generate_group_invite_token(email, group_id):
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return s.dumps({"email": email, "group_id": group_id}, salt="group-invite")

def verify_group_invite_token(token, max_age=604800):  # 7 days
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        return s.loads(token, salt="group-invite", max_age=max_age)
    except Exception:
        return None
