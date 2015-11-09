from flask.ext.wtf import Form
from wtforms import TextField, BooleanField, PasswordField, SubmitField, validators


class SignUpForm(Form):
    email = TextField("Email", [validators.Required('Please enter a valid email address.'), validators.Email('Please enter a valid email address.')])
    password = PasswordField('New Password', [
        validators.Required(),
        validators.EqualTo('confirm', message='Passwords must match.')
    ])
    confirm = PasswordField('Confirm Password')
    accept_tos = BooleanField('I accept the', [validators.Required('You must accept the terms and conditions.')])
    submit = SubmitField("Sign Up")
