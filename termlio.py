import datetime
import re
import random

from flask import Flask, request, session, redirect, render_template
from flask.ext.mail import Message, Mail
from flask.ext.sqlalchemy import SQLAlchemy
from wtforms import validators

from forms import SignUpForm
import settings

from dateutil.relativedelta import relativedelta
import wikipedia
from werkzeug.security import generate_password_hash, check_password_hash

mail = Mail()

app = Flask(__name__)
app.config.from_object(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = settings.database_uri
db = SQLAlchemy(app)

app.secret_key = settings.app_secret_key

# Mail config

app.config["MAIL_SERVER"] = settings.mail['server']
app.config["MAIL_PORT"] = settings.mail['port']
app.config["MAIL_USE_SSL"] = settings.mail['use_ssl']
app.config["MAIL_USERNAME"] = settings.mail['username']
app.config["MAIL_PASSWORD"] = settings.mail['password']

mail.init_app(app)


# Database Setup


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(100))
    is_active = db.Column(db.Boolean())
    expiration_date = db.Column(db.DateTime())
    sets = db.relationship("Set", backref="user")

    def __init__(self, email, password):
        self.email = email
        self.set_password(password)
        self.is_active = True
        self.expiration_date = datetime.date.today()

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def __repr__(self):
        return '<User %r>' % self.email


class Set(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    title = db.Column(db.String(50))
    terms = db.Column(db.String(4294967294))

    def __init__(self, user_id, title, terms):
        self.user_id = user_id
        self.title = title
        self.terms = terms

    def __repr__(self):
        return (self.title + " " + self.terms)

class Definition(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    term = db.Column(db.String(50))
    definition = db.Column(db.String(5000))

    def __init__(self, term, definition):
        self.term = term
        self.definition = definition

    def __repr__(self):
        return (self.term + self.definition)


# Notification Systems


def send_signup_email():
    msg = Message('Terml.io Account Created', sender='support@terml.io', recipients=[session['email']])
    msg.body = """
                Hello,

                You have successfully signed up for Terml.io!

                At this point, your account is inactive. This means you are unable to \n
                create any sets or search for definitions until you complete your payment. \n
                To do this, sign in, and go to terml.io/payment. This will allow you to enter \n
                your credit card information and begin your subscription to Terml.io. Your \n
                card information WILL NOT be stored on Terml.io's servers, and Terml.io will \n
                not have access to your card number or security details. \n

                If you have any questions regarding this payment, you may email payment@terml.io. \n
                General support inquiries should be sent to support@terml.io, or you may respond \n
                directly to this message. \n

                Thank you for signing up with Terml.io! We are looking forward to seeing you around.

                Regards,
                The Terml.io Team
                """


def send_payment_email():
    msg = Message('Terml.io Subscription Success', sender='support@terml.io', recipients=[session['email']])
    msg.body = """
                Hello,

                You have successfully donated to Terml.io! \n

                Thank you so much for your donation. Terml.io is primarily funded through \n
                donations like yours, which help keep the site up and running. Becuase of you, \n
                we are now able to keep the lights on a little bit longer and help students \n
                learn more efficiently.

                Thanks again,
                The Terml.io Team
                """

# Supercharged features


@app.route('/createpdf/<setid>')
def create_pdf(setid):
    set = Set.query.filter_by(id=setid).first()

    # Check to see if user owns set
    user = User.query.filter_by(email=session.get('email')).first()
    if set.user_id == user.id:
        terms = []
        for term in set.terms.split('>><<'):
            if term != '':
                terms.append(term)
        definitions = define_terms(terms)
        return render_template('createpdf.html', set=set, definitions=definitions, words=terms)
    return render_template('error.html')


@app.route('/createquizletset/<setid>', methods=['GET', 'POST'])
def create_quizlet_set(setid):
    set = Set.query.filter_by(id=setid).first()
    user = User.query.filter_by(email=session.get('email')).first()
    if set.user_id == user.id:
        terms = []
        for term in set.terms.split('>><<'):
            if term != '':
                terms.append(term)
        definitions = quizlet_definitions(terms)
        import_code = ''
        for term in terms:
            import_code += term + '\t' + definitions[term] + '\n'
        return render_template('createquizletset.html', import_code=import_code)


def quizlet_definitions(words):
    definitions = {}
    for word in words:
        try:
            definition = wikipedia.summary(word, sentences=2)
            definitions[word] = definition
        except wikipedia.exceptions.PageError:
            definitions[word] = 'No definition found.'
    return definitions

# Backend Code


def valid_email(email):
    """Validate the email address using a regex."""
    if not re.match("^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*$", email):
        return False
    return True


def define_terms(words):
    definitions = {}
    for word in words:
        cached_definition = Definition.query.filter_by(term=word).first()
        if cached_definition is not None:
            definitions[word] = cached_definition.definition
        else:
            try:
                definition = wikipedia.summary(word, sentences=2)
                definitions[word] = definition
            except wikipedia.exceptions.DisambiguationError as e:
                suggestions = return_suggestions(word, e)
                error = word + " has multiple definitions. Please type one of these: " + suggestions
                return render_template('create.html', words=words, error=error)
            except wikipedia.exceptions.PageError as e:
                definitions[word] = "No definition found."
    return definitions


def return_suggestions(term, e):
    suggestions = ""
    for sug in e.options:
        if(e.options.index(sug) == len(e.options) - 1):
            suggestions += (sug + ".")
        else:
            suggestions += (sug + ", ")
    return suggestions


def remove_blank_words(termlist):
    wordlist = termlist
    for word in wordlist:
        if word == "":
            wordlist.remove(word)
    return wordlist


def delete_set(setid):
    set = Set.query.filter_by(id=setid).first()
    db.session.delete(set)
    db.session.commit()


def user_owns_set(setid):
    user = User.query.filter_by(email=session.get('email'))
    set = Set.query.filter_by(id=setid)
    if set.user_id == user.id:
        return True
    return False


def generate_random_password():
    # Generates random password of 8 characters

    temp_password = ''
    alphanums = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H',
                'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P',
                'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X',
                'Y', 'Z', 'a', 'b', 'c', 'd', 'e', 'f',
                'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n',
                'o', 'p', 'q', 'r', 's', 't', 'u', 'v',
                'w', 'x', 'y', 'z', '1', '2', '3', '4',
                '5', '6', '7', '8', '9', '0']
    count = 0
    while count < 8:
        choice = random.randint(0,61)
        temp_password += alphanums[choice]
        count += 1

    return temp_password

# Page Structure


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/create', methods=['GET', 'POST'])
def create():
    error = None
    if session.get('logged_in'):
        user = User.query.filter_by(email=session['email']).first()
        '''
        qs = request.query_string
        if qs:
            qs = qs.split('&')
            original = (qs[0][9:]).split('%20')
            new_original = ''
            replacement = (qs[1][8:]).split('%20')
            new_replacement = ''
            for word in original:
                if word != original[len(original)-1]:
                    new_original += word + ' '
                else:
                    new_original += word
            for word in replacement:
                if word != replacement[len(replacement)-1]:
                    new_replacement += word + ' '
                else:
                    new_replacement += word
            return 'Replace ' + new_original + ' with ' + new_replacement
        '''
        if request.method == 'POST':
            settitle = request.form['settitle']
            terms = request.form['terms']
            words = terms.split('\n')
            words = remove_blank_words(words)
            session['words'] = words
            session['title'] = settitle
            dbtitle = settitle
            dbwords = ''
            for word in words:
                dbwords += word + '>><<'
            lenwords = len(words)
            if len(terms) != 0:
                definitions = {}
                for word in words:
                    cached_definition = Definition.query.filter_by(term=word).first()
                    if cached_definition is not None:
                        definitions[word] = cached_definition.definition
                    else:
                        try:
                            definition = wikipedia.summary(word, sentences=2)
                            definitions[word] = definition
                            add_definition = Definition(word, definition)
                            db.session.add(add_definition)
                            db.session.commit()
                        except wikipedia.exceptions.DisambiguationError as e:
                            suggestions = return_suggestions(word, e)
                            suggestions = suggestions.split(', ')
                            suggestions = suggestions[:3]
                            error_word = word
                            error = error_word + " has multiple definitions. Replace it with the term most closely relating to yours: "
                            return render_template('create.html', settitle=settitle, words=words, error_word=error_word, error=error, suggestions=suggestions)
                        except wikipedia.exceptions.PageError as e:
                            definitions[word] = "No definition found."
                set = Set(user.id, dbtitle, dbwords)
                db.session.add(set)
                db.session.commit()
                setid = set.id
                return render_template('definitions.html', set=set, words=words,
                                       lenwords=lenwords,
                                       definitions=definitions, setid=setid)
            error = "Please enter terms to define."
        return render_template('create.html', error=error)
        return render_template('activationneeded.html')
    return render_template('signin.html')


@app.route('/review', methods=['GET', 'POST'])
def review():
    if session.get('logged_in'):
        user = User.query.filter_by(email=session.get('email')).first()
        sets = Set.query.filter_by(user_id=user.id).all()
        sets_length = len(sets)
        length_of_sets = {}
        for set in sets:
            count = 0
            for term in set.terms.split('>><<'):
                if term != '':
                    count += 1
            length_of_sets[set] = count
        return render_template('review.html', sets=sets, definitions=definitions, sets_length=sets_length, length_of_sets=length_of_sets)
    return render_template('signin.html')


@app.route('/definitions/<setid>')
def definitions(setid):
    set = Set.query.filter_by(id=setid).first()
    user = User.query.filter_by(email=session.get('email')).first()
    if set.user_id == user.id:
        terms = []
        for term in set.terms.split('>><<'):
            if term != '':
                terms.append(term)
        definitions = define_terms(terms)
        return render_template('definitions.html', set=set, definitions=definitions, words=terms)
    return render_template('error.html')


@app.route('/deleteset/<setid>')
def delete_set_page(setid):
    set = Set.query.filter_by(id=setid).first()
    user = User.query.filter_by(email=session.get('email')).first()
    if 1  == 1:
        delete_set(set.id)
        message = 'You have successfully removed ' + set.title + ' from your sets.'
        sets = Set.query.filter_by(user_id=user.id).all()
        sets_length = len(sets)
        length_of_sets = {}
        for set in sets:
            count = 0
            for term in set.terms.split('>><<'):
                if term != '':
                    count += 1
            length_of_sets[set] = count
        return render_template('review.html', sets=sets, definitions=definitions, sets_length=sets_length, length_of_sets=length_of_sets, message=message)
    return render_template('error.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/learnmore')
def learnmore():
    return render_template('learnmore.html')


@app.route('/account', methods=['GET', 'POST'])
def account():
    if session.get('logged_in'):
        return render_template('account.html')


@app.route('/changeemail', methods=['POST'])
def changeemail():
    if session.get('logged_in'):
        message = None
        error = None
        if valid_email(request.form['email']):
            if User.query.filter_by(email=request.form['email']).first() == None:
                user = User.query.filter_by(email=session.get('email')).first()
                user.email = request.form['email']
                db.session.commit()
                session['email'] = user.email
                message = 'You have successfully changed your email to ' + user.email
            else:
                error = 'A user with that email already exists.'
        else:
            error = 'Please enter a valid email.'
        return render_template('account.html', message=message, error=error)


@app.route('/changepassword', methods=['POST'])
def changepassword():
    message = None
    error = None
    if session.get('logged_in'):
        user = User.query.filter_by(email=session.get('email')).first()
        current_password = request.form['current']
        new_password = request.form['new']
        confirm = request.form['confirm']
        if user.check_password(current_password) == False:
            error = 'Current password incorrect.'
        elif new_password != confirm:
            error = 'New passwords do not match.'
        else:
            user.set_password(new_password)
            db.session.commit()
            message = 'Your password has successfully been updated.'
        return render_template('account.html', message=message, error=error)


@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if not session.get('logged_in'):
        error = None
        if request.method == 'POST':
            user = User.query.filter_by(email=request.form['email']).first()
            if user is not None:
                email = request.form['email']
                password = request.form['password']
                if email != user.email:
                    error = 'Invalid email address.'
                if user.check_password(password) == False:
                    error = 'Invalid password.'
                else:
                    session['logged_in'] = True
                    session['email'] = user.email
                    session['is_active'] = user.is_active
                    session['username'] = ''
                    for letter in user.email:
                        if letter != '@':
                            session['username'] += letter
                        elif letter == '@':
                            break
                    date_today = datetime.datetime.today()
                    return redirect('/')
                return render_template('signin.html', error=error)
            error = 'Invalid email address.'
        return render_template('signin.html', error=error)
    return redirect('/')


@app.route('/signout')
def signout():
    if session.get('logged_in'):
        session['logged_in'] = False
        return redirect('/')
    return redirect('/')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    error = None
    form = SignUpForm(request.form)
    if request.method == 'POST' and form.validate():
        user = User.query.filter_by(email=form.email.data).first()
        if user is None:
            # User db structure (email, password)
            email = form.email.data
            password = form.password.data
            user = User(email, password)
            db.session.add(user)
            db.session.commit()
            # send_signup_email()
            message = 'You have successfully signed up for Terml.io.'
            session['logged_in'] = True
            session['email'] = user.email
            session['username'] = ''
            for letter in user.email:
                if letter != '@':
                    session['username'] += letter
                elif letter == '@':
                    break
            session['is_active'] = user.is_active
            session['expiration_date'] = user.expiration_date
            return render_template('index.html', message=message)
        error = 'That email is already being used by another account. Please sign in, or use a different email.'
        return render_template('signup.html', form=form, error=error)
    return render_template('signup.html', form=form)


@app.route('/forgotpassword', methods=['GET', 'POST'])
def forgotpassword():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        if user != None:
            temp_password = generate_random_password()

            # Change password in db to temp password
            user.set_password(temp_password)
            db.session.commit()

            # Send email with temp password
            msg = Message('Terml.io password reset', sender='support@terml.io', recipients=[request.form['email']])
            body = """
    Hello, \n

    You (or someone else) has requested a password reset on your Terml.io account. \n

    To reset your password, login to Terml.io with your temporary password
    below. Proceed to your account settings by clicking your username in the
    top right corner. You may now reset your password using the controls on
    your account page. \n

    Temporary Password: %s \n

    If you have any further questions, please do not hesitate to contact us.
    You may reply directly to this email, or email us directly at support@terml.io. \n

    -The Terml.io Team

                        """ % temp_password
            msg.body = body
            mail.send(msg)
            return render_template('forgotpasswordwait.html', email=email)
        error = 'An account with the email \'%s\' does not exist.' % email
        return render_template('forgotpassword.html', error=error)
    return render_template('forgotpassword.html')


@app.route('/help')
def help():
    if session.get('logged_in'):
        return render_template('help.html')
    return render_template('error.html')
'''
@app.route('/careers')
def careers():
    return render_template('careers.html')
'''

@app.route('/termsofservice')
def terms_of_service():
    return render_template('termsofservice.html')


@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template('error.html'), 500


if __name__ == '__main__':
    app.run(debug=True)
