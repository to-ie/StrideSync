import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # General Configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'cccccclvndchctrhhlkfnfhfttulbrlrghhkiiggvjrk'

    # Database Configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f'sqlite:///{os.path.join(basedir, "app.db")}'

    # Mail Configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 25))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'false').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'StrideSync <no-reply@stridesync.com>')
