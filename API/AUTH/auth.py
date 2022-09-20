from flask import Flask, request, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
from functools import wraps

app = Flask(__name__)

app.config['SECRET_KEY'] = 'some secrete word'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(50), unique=True)
    name = db.Column(db.String(50))
    password = db.Column(db.String(100))


db.create_all() # нужно только для создания таблицы пользователей


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'x-access-token' in request.headers:
            token = request.headers['x-access-token']
        if not token:
            return jsonify({'message': 'Нет токена'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'])
        except:
            return jsonify({'message': 'Неверный токен'}), 401
        return f(*args, **kwargs)
    return decorated


@app.route('/user', methods=['POST'], endpoint='create_user')
def create_user():
    data = request.get_json()
    hashed_password = generate_password_hash(data['password'], method='sha256')
    new_user = User(public_id=str(uuid.uuid4()), name=data['name'], password=hashed_password)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'message': 'Создан новый пользователь'})


@app.route('/login', methods=['POST'])
def login():
    auth = request.authorization
    if not auth or not auth.username or not auth.password:
        return make_response('Введите логин и пароль', 401)
    user = User.query.filter_by(name=auth.username).first()
    if not user:
        return make_response('Пользователя нет в базе данных', 401)
    if check_password_hash(user.password, auth.password):
        token = jwt.encode(
            {
            'public_id': user.public_id,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
            },
            app.config['SECRET_KEY']
        )
        return jsonify({'token': token.decode('UTF-8')})
    return make_response('Неверный логин или пароль', 401)


@app.route('/user', methods=['GET'])
@token_required
def get_all_users():
    users = User.query.all()
    users_list = []
    for user in users:
        user_data = {}
        user_data['public_id'] = user.public_id
        user_data['name'] = user.name
        user_data['password'] = user.password
        users_list.append(user_data)
    return jsonify({'users': users_list})


if __name__ == '__main__':
    app.run(debug=True)
