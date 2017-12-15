import os
from flask import Flask, render_template, session, redirect, request, url_for, flash
from flask_script import Manager, Shell
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, FileField, PasswordField, BooleanField, SelectMultipleField, ValidationError
from wtforms.validators import Required, Length, Email, Regexp, EqualTo
from flask_sqlalchemy import SQLAlchemy
import random
from flask_migrate import Migrate, MigrateCommand

# Imports for email from app
from flask_mail import Mail, Message
from threading import Thread
from werkzeug import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# Imports for login management
from flask_login import LoginManager, login_required, logout_user, login_user, UserMixin, current_user

# for looking up itunes
import requests
import json

# Configure base directory of app
basedir = os.path.abspath(os.path.dirname(__file__))

# Application configurations
app = Flask(__name__)
app.static_folder = 'static'
app.config['SECRET_KEY'] = 'hardtoguessstring'
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get('DATABASE_URL') or "postgresql://localhost/final_364"  
# Lines for db setup so it will work as expected
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Set up email config stuff
app.config['MAIL_SERVER'] = 'smtp.googlemail.com'
app.config['MAIL_PORT'] = 587 #default
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME') # TODO export to your environs -- may want a new account just for this. It's expecting gmail, not umich
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_SUBJECT_PREFIX'] = '[Songs App]'
app.config['MAIL_SENDER'] = 'Admin <>' # TODO fill in email
app.config['ADMIN'] = os.environ.get('ADMIN') or "marielse4321@gmail.com" # If Admin in environ variable / in prod or this fake email
app.config['HEROKU_ON'] = os.environ.get('HEROKU')

# Set up Flask debug and necessary additions to app
manager = Manager(app)
db = SQLAlchemy(app) # For database use
migrate = Migrate(app, db) # For database use/updating
manager.add_command('db', MigrateCommand) # Add migrate command to manager
mail = Mail(app) # For email sending

# Login configurations setup
login_manager = LoginManager()
login_manager.session_protection = 'strong'
login_manager.login_view = 'login'
login_manager.init_app(app) # set up login manager

## Set up Shell context so it's easy to use the shell to debug
# Define function
def make_shell_context():
    return dict( app=app, db=db, Song=Song, Artist=Artist, User=User, Playlist=Playlist)
# Add function use to manager
manager.add_command("shell", Shell(make_context=make_shell_context))

#########
######### Everything above this line is important/useful setup, not mostly application-specific problem-solving.
#########

##### Functions to send email #####

def send_async_email(app, msg):
    with app.app_context():
        mail.send(msg)

def send_email(to, subject, template, **kwargs): # kwargs = 'keyword arguments', this syntax means to unpack any keyword arguments into the function in the invocation...
    msg = Message(app.config['MAIL_SUBJECT_PREFIX'] + ' ' + subject,
                  sender=app.config['MAIL_SENDER'], recipients=[to])
    msg.body = render_template(template + '.txt', **kwargs)
    msg.html = render_template(template + '.html', **kwargs)
    thr = Thread(target=send_async_email, args=[app, msg]) # using the async email to make sure the email sending doesn't take up all the "app energy" -- the main thread -- at once
    thr.start()
    return thr # The thread being returned
    # However, if your app sends a LOT of email, it'll be better to set up some additional "queuing" software libraries to handle it. But we don't need to do that yet. Not quite enough users!

##### Set up Models #####

# Set up association Table between person and songs
collections = db.Table('collections', db.Column('user_id',db.Integer, db.ForeignKey('person.id')),db.Column('song_id',db.Integer, db.ForeignKey('songs.id')))

# Set up association Table between songs and playlists
on_playlist = db.Table('on_playlist',db.Column('user_id', db.Integer, db.ForeignKey('songs.id')),db.Column('playlist_id',db.Integer, db.ForeignKey('playlists.id')))

# Special model for users to log in
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, index=True)
    email = db.Column(db.String(64), unique=True, index=True)
    playlists = db.relationship('Playlist', backref='User')
    password_hash = db.Column(db.String(128))

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

class Person(db.Model):
    __tablename__ = "person"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(64), db.ForeignKey("users.email"))
    name = db.Column(db.String(64))
    song_id = db.relationship('Song',secondary=collections,backref=db.backref('person',lazy='dynamic'),lazy='dynamic')

class Song(db.Model):
    __tablename__ = "songs"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(64))
    artist_id = db.Column(db.Integer, db.ForeignKey("artists.id"))

class Artist(db.Model):
    __tablename__ = "artists"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    songs = db.relationship('Song',backref='Artist')

class Playlist(db.Model):
    __tablename__ = "playlists"
    id = db.Column(db.Integer, primary_key=True)
    songs = db.relationship('Song',secondary=on_playlist,backref=db.backref('playlists',lazy='dynamic'),lazy='dynamic')
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))

## DB load functions
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id)) # returns User object or None

##### Forms #####

class SongForm(FlaskForm):
    song = StringField("What is the title of the song you are looking for?", validators=[Required()])
    submit = SubmitField('Submit')

class sendEamil(FlaskForm):
    email = StringField("Enter your friend's email:", validators=[Required(),Length(1,64),Email()])
    submit = SubmitField('Submit')

class RegistrationForm(FlaskForm):
    email = StringField('Enter your email:', validators=[Required(),Length(1,64),Email()])
    username = StringField('Enter your username:',validators=[Required(),Length(1,64),Regexp('^[A-Za-z][A-Za-z0-9_.]*$',0,'Usernames must have only letters, numbers, dots or underscores')])
    password = PasswordField('Enter your password:',validators=[Required(),EqualTo('password2',message="Passwords must match")])
    password2 = PasswordField("Confirm your Password:",validators=[Required()])
    submit = SubmitField('Register')

    #Additional checking methods for the form
    def validate_email(self,field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('Email already registered.')

    def validate_username(self,field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('Username already taken')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[Required(), Length(1,64), Email()])
    password = PasswordField('Password', validators=[Required()])
    remember_me = BooleanField('Keep me logged in')
    submit = SubmitField('Log In')

### For database additions / get_or_create functions

def get_song_by_name(song_name):
    """returns song or None"""
    s = Song.query.filter_by(title=song_name).first()
    return s

def get_or_create_artist(db_session,artist_name):
    artist = db_session.query(Artist).filter_by(name=artist_name).first()
    if artist:
        return artist
    else:
        artist = Artist(name=artist_name)
        db_session.add(artist)
        db_session.commit()
        return artist

def get_or_create_song(db_session, song_title, song_artist):
    artist = get_or_create_artist(db_session, song_artist)
    song = db_session.query(Song).filter_by(title=song_title, artist_id=artist.id).first()
    if song:
        return song
    song = Song(title=song_title,artist_id=artist.id)
    db_session.add(song)
    db_session.commit()
    return song

##### Set up Controllers (view functions) #####

## Error handling routes
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

@app.route('/')
def index():
    return redirect('song/normal')

## Login routes
@app.route('/login',methods=["GET","POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is not None and user.verify_password(form.password.data):
            login_user(user, form.remember_me.data)
            return redirect(request.args.get('next') or url_for('index'))
        flash('Invalid username or password.')
    return render_template('login.html',form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out')
    return redirect(url_for('index'))

@app.route('/register',methods=["GET","POST"])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(email=form.email.data,username=form.username.data,password=form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('You can now log in!')
        return redirect(url_for('login'))
    return render_template('register.html',form=form)

@app.route('/song/<more>',methods=["GET","POST"])
def song_input(more):
    base_url = 'https://itunes.apple.com/search?entity=song&limit=10&term='
    form = SongForm()
    if form.validate_on_submit():
        song = form.song.data 
        url = base_url + song
        x = requests.get(url).text
        #print(x)
        song_list = []
        #finalString = 'The top 5 artists who sing {} are: '.format(song)
        params_dict = song.replace(' ', '*') + ":"
        for i in range(10):
            artist = json.loads(x)['results'][i]['artistName']
            dictor = {'song':song, 'artist':artist, 'both':params_dict+artist.replace(' ', '*')}
            song_list.append(dictor)
            #finalString += json.loads(x)['results'][i]['artistName']
        if more == 'normal':
            return render_template('song_list.html', songs=song_list, name=song, params_dict=params_dict, number=5)
        else:
            return render_template('song_list.html', songs=song_list, name=song, params_dict=params_dict, number=10)
    return render_template('song.html',form=form)

@app.route('/song_status',methods=["GET","POST"])
def song_status():
    if request.method == 'GET':
        result = request.args
        choice = result.get('choice')
        print("choice = ")
        print(choice)
        choice = choice.split(':')
        track = choice[0]
        if '*' in track:
            track = track.replace('*', ' ')
        print(track)
        artist = choice[1].replace('*', ' ')
        print(artist)
        # add the song to the song/artist table
        get_or_create_song(db.session, track, artist)
        url = '/send/' + track.replace(' ', '*') + '/' + artist.replace(' ', '*')
    return render_template('save_and_send.html', song_name=track, song_artist=artist, url=url)

@app.route('/send/<song>/<artist>',methods=["GET","POST"])
def send_song(song, artist):
    # do something
    form = sendEamil()
    if form.validate_on_submit():
        email = form.email.data
        send_email(email, 'This is a cool song', 'mail/new_song', song_name=song, song_artist=artist)
    return render_template('email_friend.html',form=form)


if __name__ == '__main__':
    db.create_all()
    manager.run() # NEW: run with this: python main_app.py runserver
    # Also provides more tools for debugging








