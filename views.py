from flask import Flask, request, render_template, redirect, session
import redis
import hashlib 
import sys

app = Flask(__name__)
app.config['SECRET_KEY'] = "SPN STOP ASSIGN WORK PLEASE"

def redis_link():
    return redis.StrictRedis(host='127.0.0.1', port=6379, db=0, charset="utf-8", decode_responses=True)

@app.route('/')
def root():
    if session:
        return redirect('/home')
    return render_template('login.html', error_message=None)

@app.route('/login', methods=['POST'])
def login():
    r = redis_link()

    username = request.form['username']
    password = request.form['password']
    user_id = r.get(f'username:{username}:id')

    if not user_id:
        error_message = f'No such user {username}'
        return render_template('login.html', error_message=error_message)
    
    saved_password = r.get(f'uid:{user_id}:password')
    if saved_password != password:
        error_message = 'Wrong password!'
        return render_template('login.html', error_message=error_message)

    session['username'] = username
    return redirect('/home')


def create_user(username, password):
    r = redis_link()
    user_id = r.incr('global:nextUserId')
    r.set(f'username:{username}:id', user_id)
    r.set(f'uid:{user_id}:username', username)
    r.set(f'uid:{user_id}:password', password)

    r.sadd('global:users', user_id)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    error_message = None
    r = redis_link()
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

    user_id = r.get(f"username:{username}:id")
    if user_id:
        error_message = 'Sorry the selected username is already in use.'
        return render_template('signup.html', error_message=error_message)
    
    create_user(username, password)
    session['username'] = username
    return redirect('/home')


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect('/')

@app.route('/home', methods=['GET', 'POST'])
def home():
    if not session:
        return redirect('/')
    return render_template('home.html')
