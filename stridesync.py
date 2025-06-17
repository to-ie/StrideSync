from dotenv import load_dotenv
load_dotenv()

import sqlalchemy as sa
import sqlalchemy.orm as so
from app import app, db
from app.models import User