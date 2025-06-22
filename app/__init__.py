from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail

# Create extensions (not tied to app yet)
db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
mail = Mail()

# Create Flask app instance
app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions with the app
db.init_app(app)
migrate.init_app(app, db)
login.init_app(app)
login.login_view = "login"  # name of your login route function
login.login_message = "Please log in to access this page."
login.login_message_category = "warning"
mail.init_app(app)

from app import routes, models
