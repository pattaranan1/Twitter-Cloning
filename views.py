from flask import Flask, request, render_template, redirect, session
import redis
import time
import sys

app = Flask(__name__)
app.config['SECRET_KEY'] = "SPN STOP ASSIGN WORK PLEASE"

def redis_link():
    return redis.StrictRedis(
        host='127.0.0.1', 
        port=6379, 
        db=0, 
        charset="utf-8", 
        decode_responses=True)

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

@app.route('/home')
def home():
    if not session:
        return redirect('/')
    
    r = redis_link()
    user_id = r.get(f"username:{session['username']}:id")

    posts = get_posts(user_id)
    return render_template('home.html', posts=posts)


def elapsed(t):
    d = time.time() - t 

    if d < 60:
        return f'{int(d)}s' 
    if d < 3600:
        m = int(d/60)
        return f"{m}m"
    if d < 3600 * 24:
        h = int(d/3600)
        return f"{h}h"

    this_year = time.localtime().tm_year 
    created_year = time.localtime(d).tm_year

    if this_year - created_year < 1:
        return time.strftime("%b %e", time.localtime(d))
    return time.strftime("%b %e, %Y", time.localtime(d))

def get_posts(user_id, size=1000):
    
    r = redis_link()
    key =  'global:timeline' if user_id == -1 else f'uid:{user_id}:posts'
    posts = r.lrange(key, 0, size)

    total_post = []
    for post in posts:    
        text = r.get(f'post:{post}:text')
        uid = r.get(f'post:{post}:uid')
        created_at = float(r.get(f'post:{post}:created_at'))
        total_post.append({'text':text, 'username': r.get(f'uid:{uid}:username'), 'elapsed': elapsed(created_at)})
    return total_post


def get_last_users():
    r = redis_link();
    users = r.sort('global:users', get='uid:*:username', start=0, num=50);
    return users

def new_post(text, user_id):
    r = redis_link()
    post_id = r.incr('global:nextPostId')

    text = text.replace('\n', '')
    r.set(f'post:{post_id}:uid', user_id)
    r.set(f'post:{post_id}:created_at', time.time())
    r.set(f'post:{post_id}:text', text)
    
    followers = r.smembers(f'uid:{user_id}:followers')
    followers.add(user_id)

    for follower in followers:
        r.lpush(f'uid:{follower}:posts', post_id)

    r.lpush('global:timeline', post_id)
    r.ltrim('global:timeline', 0, 1000)

@app.route('/post', methods=["POST"])
def post():
    if not session:
        return redirect('/')

    r = redis_link()
    user_id = r.get(f"username:{session['username']}:id")
    
    new_post(request.form['post'], user_id)

    return redirect('/home')

@app.route('/timeline')
def timeline():
    if not session:
        return redirect('/')
    return render_template('timeline.html', posts=get_posts(-1, 10), users=get_last_users())