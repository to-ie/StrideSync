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

login.login_view = 'login'

# Email config
mail = Mail()

# Create app instance
app = Flask(__name__)
app.config.from_object(Config)
mail.init_app(app)

# Initialize extensions with the app
db.init_app(app)
migrate.init_app(app, db)
login.init_app(app)

# Import routes AFTER app is created to avoid circular import
from app import routes, models
