from functools import wraps
from flask import g, Flask, request, render_template, redirect, session
import redis
import time
import sys

app = Flask(__name__)
app.config['SECRET_KEY'] = "SPN STOP ASSIGN WORK PLEASE"


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session:
            return redirect('/')
        return f(*args, **kwargs)
    return decorated_function

def redis_link():
    return redis.StrictRedis(
        host='127.0.0.1', 
        port=6379, 
        db=0, 
        charset="utf-8", 
        decode_responses=True)

@app.before_request
def before_request():
    g.db = redis_link()

@app.route('/')
def root():
    if session:
        return redirect('/home')
    return render_template('login.html', error_message=None)

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    user_id = g.db.get(f'username:{username}:id')

    if not user_id:
        error_message = f'No such user {username}'
        return render_template('login.html', error_message=error_message)
    
    saved_password = g.db.get(f'uid:{user_id}:password')
    if saved_password != password:
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

    user_id = g.db.get(f"username:{username}:id")
    if user_id:
        error_message = 'Sorry the selected username is already in use.'
        return render_template('signup.html', error_message=error_message)
    
    create_user(username, password)
    session['username'] = username
    return redirect('/home')

def create_user(username, password):
    user_id = g.db.incr('global:nextUserId')
    g.db.set(f'username:{username}:id', user_id)
    g.db.set(f'uid:{user_id}:username', username)
    g.db.set(f'uid:{user_id}:password', password)

    g.db.sadd('global:users', user_id)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect('/')

@app.route('/home')
@login_required
def home():   
    user_id = g.db.get(f"username:{session['username']}:id")

    posts = get_posts(user_id)

    count_following = g.db.scard(f'uid:{user_id}:following') 
    count_followers = g.db.scard(f'uid:{user_id}:followers')

    return render_template('home.html', posts=posts, username=session['username'], following=count_following, followers=count_followers,error_message=None)

@app.route('/post', methods=["POST"])
@login_required
def post():
    user_id = g.db.get(f"username:{session['username']}:id")
    new_post(request.form['post'], user_id)
    return redirect('/home')

def new_post(text, user_id):
    post_id = g.db.incr('global:nextPostId')

    text = text.replace('\n', '')
    g.db.set(f'post:{post_id}:uid', user_id)
    g.db.set(f'post:{post_id}:created_at', time.time())
    g.db.set(f'post:{post_id}:text', text)
    
    followers = g.db.smembers(f'uid:{user_id}:followers')
    followers.add(user_id)

    for follower in followers:
        g.db.lpush(f'uid:{follower}:posts', post_id)

    g.db.lpush('global:timeline', post_id)
    g.db.ltrim('global:timeline', 0, 1000)

def get_posts(user_id, size=1000):
    key =  'global:timeline' if user_id == -1 else f'uid:{user_id}:posts'
    posts = g.db.lrange(key, 0, size)

    total_post = []
    for post in posts:    
        text = g.db.get(f'post:{post}:text')
        uid = g.db.get(f'post:{post}:uid')
        created_at = float(g.db.get(f'post:{post}:created_at'))
        total_post.append({'text':text, 'username': g.db.get(f'uid:{uid}:username'), 'elapsed': elapsed(created_at)})
    return total_post

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
    created_year = time.localtime(t).tm_year

    if this_year - created_year < 1:
        return time.strftime("%b %e", time.localtime(t))
    return time.strftime("%b %e, %Y", time.localtime(t))

@app.route('/timeline')
@login_required
def timeline():
    return render_template('timeline.html', posts=get_posts(-1, 10), users=get_last_users())

def get_last_users():
    users = g.db.sort('global:users', get='uid:*:username', start=0, num=50);
    return users

@app.route('/profile/<username>')
@login_required
def profile(username):
    user_id = g.db.get(f"username:{username}:id")

    if not user_id:
        error_message = f'Profile {username} not exists'
        return render_template('profile.html', username=username, error_message=error_message)

    return render_template('profile.html', username=username, profile=get_profile(user_id, username), posts=get_posts(user_id), error_message=None)

def get_profile(user_id, username): 
    my_user_id = g.db.get(f"username:{session['username']}:id")

    profile = {'user_id': user_id}
    profile['self'] = True if user_id == my_user_id else False
    profile['is_following'] = g.db.sismember(f'uid:{my_user_id}:following', user_id)

    return profile

@app.route('/follow')
@login_required
def follow():
    my_user_id = g.db.get(f"username:{session['username']}:id")
    username = follow_user(request.values['uid'], my_user_id, request.values['f'])
    return redirect(f'/profile/{username}')

def follow_user(user_id, my_user_id, f):
    if my_user_id == user_id:
       return g.db.get(f'uid:{user_id}:username')

    if f == '1':
        g.db.sadd(f'uid:{user_id}:followers', my_user_id);
        g.db.sadd(f'uid:{my_user_id}:following', user_id);
    elif f == '0':
        g.db.srem(f'uid:{user_id}:followers', my_user_id);
        g.db.srem(f'uid:{my_user_id}:following', user_id);
    else:
        error_message = 'Invalid operation'
        return render_template('home.html', error_message=error_message) 
    return g.db.get(f'uid:{user_id}:username')