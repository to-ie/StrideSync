from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[
        DataRequired(message='Email address is required.'),
        Email(message='Please enter a valid email address.'),
        Length(max=120)
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message="Password is required.")
    ])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('SIGN IN')

class RegisterForm(FlaskForm):
    email = StringField('Email', validators=[
        DataRequired(message='Email address is required.'),
        Email(message="Please enter a valid email address.")
    ])
    username = StringField('Username', validators=[
        DataRequired(message='Let us know what we should call you!'),
        Length(min=4, max=64, message='Chose a different username (min 4 characters).')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=6, message="Password must be at least 6 characters.")
    ])
    password2 = PasswordField('Repeat Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords don\'t match.')
    ])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Register')