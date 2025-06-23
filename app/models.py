import secrets
import enum
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db, login
from sqlalchemy import Numeric, Boolean, String, Column


# ---------------------------
# Enums
# ---------------------------

class UserRole(enum.Enum):
    ADMIN = "admin"
    USER = "user"


# ---------------------------
# Association Tables
# ---------------------------

user_groups = sa.Table(
    "user_groups",
    db.metadata,
    sa.Column("user_id", sa.ForeignKey("users.id"), primary_key=True),
    sa.Column("group_id", sa.ForeignKey("groups.id"), primary_key=True),
)

run_groups = sa.Table(
    "run_groups",
    db.metadata,
    sa.Column("run_id", sa.ForeignKey("runs.id"), primary_key=True),
    sa.Column("group_id", sa.ForeignKey("groups.id"), primary_key=True),
)

group_admins = sa.Table(
    "group_admins",
    db.metadata,
    sa.Column("user_id", sa.ForeignKey("users.id"), primary_key=True),
    sa.Column("group_id", sa.ForeignKey("groups.id"), primary_key=True),
)

# ---------------------------
# Models
# ---------------------------

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = sa.Column(sa.Integer, primary_key=True)
    email = sa.Column(sa.String(120), unique=True, nullable=False, index=True)
    password_hash = sa.Column(sa.String(256))
    username = sa.Column(sa.String(64), unique=True, nullable=False, index=True)
    role = sa.Column(sa.Enum(UserRole), default=UserRole.USER, nullable=False)
    is_verified = sa.Column(sa.Boolean, default=False)
    verification_token = sa.Column(sa.String(128), nullable=False, default=lambda: secrets.token_urlsafe(32))
    unit_preference = Column(String(2), default='km')  # 'km' or 'mi'
    notify_group_activity = Column(Boolean, default=True)
    is_public_profile = Column(Boolean, default=False)

    reset_token = db.Column(db.String, nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)

    runs = so.relationship("Run", back_populates="user", cascade="all, delete-orphan")
    groups = so.relationship("Group", secondary=user_groups, back_populates="members")
    admin_of_groups = so.relationship("Group", secondary=group_admins, back_populates="admins")

    def __repr__(self):
        return f"<User {self.email} - {self.role.name} - {'Verified' if self.is_verified else 'Unverified'}>"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Run(db.Model):
    __tablename__ = "runs"

    id = sa.Column(sa.Integer, primary_key=True)
    date = sa.Column(sa.DateTime(timezone=True), index=True)
    distance = sa.Column(Numeric(precision=8, scale=2))  # replaces sa.Integer
    time = sa.Column(sa.Integer)      # seconds (duration)
    pace = sa.Column(sa.Integer)      # seconds per km

    user_id = sa.Column(sa.Integer, sa.ForeignKey("users.id"), index=True)
    user = so.relationship("User", back_populates="runs")

    groups = so.relationship("Group", secondary=run_groups, back_populates="runs")

    def __repr__(self):
        return f"<Run {self.id} - User {self.user_id}>"


class Group(db.Model):
    __tablename__ = "groups"

    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String(100), unique=True, nullable=False)
    description = sa.Column(sa.Text)

    members = so.relationship("User", secondary=user_groups, back_populates="groups")
    admins = so.relationship("User", secondary=group_admins, back_populates="admin_of_groups")
    runs = so.relationship("Run", secondary=run_groups, back_populates="groups")
    invites = so.relationship("GroupInvite", back_populates="group", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Group {self.name}>"


class GroupInvite(db.Model):
    __tablename__ = "group_invite"

    id = sa.Column(sa.Integer, primary_key=True)
    email = sa.Column(sa.String(120), nullable=False)
    token = sa.Column(sa.String(128), nullable=False, unique=True)
    group_id = sa.Column(sa.Integer, sa.ForeignKey('groups.id'), nullable=False)
    created_at = sa.Column(sa.DateTime, default=datetime.utcnow)
    inviter_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', name='fk_group_invite_inviter_id_users'),
        nullable=True
    )
    inviter = db.relationship('User', backref='sent_invites', foreign_keys=[inviter_id])


    group = so.relationship("Group", back_populates="invites")

    def __repr__(self):
        return f"<GroupInvite {self.email} -> Group {self.group_id}>"


# ---------------------------
# Flask-Login Loader
# ---------------------------

@login.user_loader 
def load_user(id): 
    return db.session.get(User, int(id))
