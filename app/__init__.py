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
mail.init_app(app)

# Import routes and models AFTER initializing extensions
from app import routes, models
