from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length
from wtforms import DateField, FloatField, IntegerField, SelectMultipleField
from wtforms import DateField, DecimalField, SelectMultipleField, IntegerField
from wtforms.validators import DataRequired, NumberRange
from wtforms.widgets import ListWidget, CheckboxInput
from flask_wtf import FlaskForm
from wtforms import DecimalField, IntegerField, DateField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional
from wtforms import SelectMultipleField
from wtforms.validators import DataRequired, NumberRange

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

class LogActivityForm(FlaskForm):
    date = DateField('Date', validators=[DataRequired()])
    distance = DecimalField('Distance (km)', validators=[DataRequired(), NumberRange(min=0.1)])
    hours = IntegerField('Hours', default=0, validators=[NumberRange(min=0)])
    minutes = IntegerField('Minutes', default=0, validators=[NumberRange(min=0, max=59)])

    groups = SelectMultipleField('Log to Groups', coerce=int)
    challenges = SelectMultipleField('Log to Challenges', coerce=int)

class EditRunForm(FlaskForm):
    date = DateField('Date', validators=[DataRequired()])
    distance = DecimalField('Distance (km)', validators=[DataRequired(), NumberRange(min=0.1)])
    hours = IntegerField('Hours', default=0, validators=[NumberRange(min=0)])
    minutes = IntegerField('Minutes', default=0, validators=[NumberRange(min=0, max=59)])
    
    groups = SelectMultipleField('Log to Groups', coerce=int)
    challenges = SelectMultipleField('Log to Challenges', coerce=int)

    submit = SubmitField('Save Changes')
        
class DeleteRunForm(FlaskForm):
    submit = SubmitField('Delete')

class CreateGroupForm(FlaskForm):
    name = StringField("Group Name", validators=[DataRequired(), Length(max=100)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=500)])
    submit = SubmitField("Create Group")