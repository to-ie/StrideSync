from typing import Optional
import secrets
import enum

from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db, login

from datetime import datetime, timezone


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

user_challenges = sa.Table(
    "user_challenges",
    db.metadata,
    sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), primary_key=True),
    sa.Column("challenge_id", sa.Integer, sa.ForeignKey("challenges.id"), primary_key=True)
)

# ---------------------------
# Models
# ---------------------------

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)

    email: so.Mapped[str] = so.mapped_column(sa.String(120), index=True, unique=True, nullable=False)
    password_hash: so.Mapped[str] = so.mapped_column(sa.String(256))

    username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True, unique=True, nullable=False)
    role: so.Mapped[UserRole] = so.mapped_column(sa.Enum(UserRole), default=UserRole.USER, nullable=False)

    is_verified: so.Mapped[bool] = so.mapped_column(default=False)
    verification_token: so.Mapped[str] = so.mapped_column(default=lambda: secrets.token_urlsafe(32), nullable=False)

    runs: so.Mapped[list["Run"]] = so.relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )

    groups: so.Mapped[list["Group"]] = so.relationship(
        secondary=user_groups,
        back_populates="members"
    )

    admin_of_groups: so.Mapped[list["Group"]] = so.relationship(
        secondary=group_admins,
        back_populates="admins"
    )

    challenges: so.Mapped[list["Challenge"]] = so.relationship(
        secondary=user_challenges,
        back_populates="participants"
    )

    joined_challenges: so.Mapped[list["Challenge"]] = so.relationship(
        secondary=user_challenges,
        back_populates="participants"
    )

    def __repr__(self):
        return f"<User {self.email} - {self.role.name} - {'Verified' if self.is_verified else 'Unverified'}>"
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Run(db.Model):
    __tablename__ = "runs"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    date: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), index=True)
    distance: so.Mapped[int] = so.mapped_column(sa.Integer)  # meters
    time: so.Mapped[int] = so.mapped_column(sa.Integer)      # seconds (duration)
    pace: so.Mapped[int] = so.mapped_column(sa.Integer)      # seconds per km

    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey("users.id"), index=True)
    user: so.Mapped["User"] = so.relationship(back_populates="runs")

    groups: so.Mapped[list["Group"]] = so.relationship(
        secondary=run_groups,
        back_populates="runs"
    )

    def __repr__(self):
        return f"<Run {self.id} - User {self.user_id}>"


class Group(db.Model):
    __tablename__ = "groups"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(100), unique=True, nullable=False)
    description: so.Mapped[Optional[str]] = so.mapped_column(sa.Text)

    members: so.Mapped[list["User"]] = so.relationship(
        secondary=user_groups,
        back_populates="groups"
    )

    admins: so.Mapped[list["User"]] = so.relationship(
        secondary=group_admins,
        back_populates="admin_of_groups"
    )

    runs: so.Mapped[list["Run"]] = so.relationship(
        secondary=run_groups,
        back_populates="groups"
    )

    def __repr__(self):
        return f"<Group {self.name}>"




class Challenge(db.Model):
    __tablename__ = "challenges"

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(100), nullable=False)
    description: so.Mapped[str] = so.mapped_column(sa.Text, nullable=True)

    start_date: so.Mapped[datetime] = so.mapped_column(default=datetime.utcnow)
    end_date: so.Mapped[datetime] = so.mapped_column(nullable=True)

    is_active: so.Mapped[bool] = so.mapped_column(default=True)

    participants: so.Mapped[list["User"]] = so.relationship(
        secondary=user_challenges,
        back_populates="joined_challenges"
    )

    def __repr__(self):
        return f"<Challenge {self.name}>"


@login.user_loader
def load_user(id):
    return db.session.get(User, int(id))