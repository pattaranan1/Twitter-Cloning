from functools import wraps
from flask import Flask, request, render_template, redirect, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
import time
from datetime import datetime
import sys

app = Flask(__name__)
app.config['SECRET_KEY'] = "SPN STOP ASSIGN WORK PLEASE"
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:postgres@localhost:5432/postgres'
db = SQLAlchemy(app)
migrate = Migrate(app, db)

followers = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'))
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    username = db.Column(db.String(80), unique= True, nullable = False)
    password = db.Column(db.String, unique= True, nullable = False)
    posts = db.relationship('Post', backref='user', lazy=True)

    followed = db.relationship(
        'User', secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref('followers', lazy='dynamic'), lazy='dynamic')
    
    def set_password(self, password):
       self.password = generate_password_hash(password)

    def check_password(self, password):
       return check_password_hash(self.password, password)

    def get_posts(self):
        followed_posts = Post.query.join(
            followers, (followers.c.followed_id == Post.user_id)).filter(
            followers.c.follower_id == self.id)
        own = Post.query.filter_by(user_id=self.id)
        posts = followed_posts.union(own).order_by(Post.created_at.desc()).limit(1000).all()
        total_post = []
        for post in posts:    
            total_post.append({'text':post.text, 'username': post.user.username, 'elapsed': elapsed(post.created_at)})

        return total_post

    def follow(self, user):
        if not self.is_following(user):
            self.followed.append(user)

    def unfollow(self, user):
        if self.is_following(user):
            self.followed.remove(user)

    def is_following(self, user):
        return self.followed.filter(followers.c.followed_id == user.id).count() > 0

    def __repr__(self):
        return f'<User {self.username}'

class Post(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    post_id = db.Column(db.Integer, primary_key = True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now())
    text = db.Column(db.Text, nullable=False)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session:
            return redirect('/')
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def root():
    if session:
        return redirect('/home')
    return render_template('login.html', error_message=None)

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    user = User.query.filter_by(username=username).first()
    
    if not user:
        error_message = f'No such user {username}'
        return render_template('login.html', error_message=error_message)
    
    if not user.check_password(password):
        error_message = 'Wrong password!'
        return render_template('login.html', error_message=error_message)

    session['username'] = username
    return redirect('/home')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    error_message = None
    
    if request.method == 'GET':
            return render_template('signup.html', error_message=error_message)

    username = request.form['username']
    password = request.form['password']
    confirm_password = request.form['confirm_password']

    if "" in [username, password, confirm_password]:
        error_message = 'Every field of the registration form is needed!'
        return render_template('signup.html', error_message=error_message)

    if password != confirm_password:
        error_message = 'Password and Confirmation password must be the same'
        return render_template('signup.html', error_message=error_message)

    user = User.query.filter_by(username=username).first()

    if user:
        error_message = 'Sorry the selected username is already in use.'
        return render_template('signup.html', error_message=error_message)
    
    create_user(username, password)
    session['username'] = username
    return redirect('/home')

def create_user(username, password):
    new_user = User(username = username, password = generate_password_hash(password))
    db.session.add(new_user)
    db.session.commit()

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect('/')

@app.route('/home')
@login_required
def home():   

    user = User.query.filter_by(username=session['username']).first()
    posts = user.get_posts()

    return render_template('home.html', posts=posts, username=session['username'], following=user.followed.count(), followers=user.followers.count(), error_message=None)

@app.route('/post', methods=["POST"])
@login_required
def post():
    user = User.query.filter_by(username=session['username']).first()
    new_post(request.form['post'], user.id)
    return redirect('/home')

def new_post(text, user_id):
    new_post = Post(user_id = user_id, text=text, created_at=datetime.now())
    db.session.add(new_post)
    db.session.commit()

def elapsed(t):
    duration = datetime.now() - t

    total_seconds = duration.total_seconds()

    if total_seconds < 60:
        return f'{int(total_seconds)}s' 
    elif total_seconds< 3600:
        m = int(total_seconds/60)
        return f"{m}m"
    elif total_seconds < 3600 * 24:
        h = int(total_seconds/3600)
        return f"{h}h"
    elif total_seconds < 31536000:
        return t.strftime("%b %e")

    return t.strftime("%b %e, %Y")

@app.route('/timeline')
@login_required
def timeline():
    posts = Post.query.order_by(Post.created_at.desc()).limit(1000).all()
    total_post = []
    for post in posts:   
        total_post.append({'text':post.text, 'username': post.user.username, 'elapsed': elapsed(post.created_at)})
    return render_template('timeline.html', posts=total_post, users=get_last_users())

def get_last_users():
    users = User.query.limit(10).all()
    total_users = []
    for user in users:
        total_users.append(user.username)
    return total_users

@app.route('/profile/<username>')
@login_required
def profile(username):
    
    user = User.query.filter_by(username=username).first()

    if not user:
        error_message = f'Profile {username} not exists'
        return render_template('profile.html', username=username, error_message=error_message)

    return render_template('profile.html', username=username, profile=get_profile(user), posts=user.get_posts(), error_message=None)

def get_profile(user): 
    my_user = User.query.filter_by(username=session['username']).first()

    profile = {'user_id': user.id}
    profile['self'] = user.id == my_user.id 
    profile['is_following'] = my_user.is_following(user)

    return profile

@app.route('/follow')
@login_required
def follow():
    my_user = User.query.filter_by(username=session['username']).first()
    other_user = User.query.filter_by(id=request.values['uid']).first()
    username = follow_user(other_user, my_user, request.values['f'])
    return redirect(f'/profile/{username}')

def follow_user(other_user, my_user, f):
    if my_user.id == other_user.id:
       return my_user.username

    if f == '1':
       my_user.follow(other_user)
       db.session.commit()
    elif f == '0':
       my_user.unfollow(other_user)
       db.session.commit()
    else:
        error_message = 'Invalid operation'
        return render_template('home.html', error_message=error_message) 
    return other_user.username