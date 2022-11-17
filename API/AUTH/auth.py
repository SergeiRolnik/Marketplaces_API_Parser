from flask import Flask, request, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from datetime import datetime, timedelta
from functools import wraps
from shared.db import DB_DSN

app = Flask(__name__)
app.config['SECRET_KEY'] = 'some secrete word'
app.config['SQLALCHEMY_DATABASE_URI'] = DB_DSN
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(50), unique=True)
    name = db.Column(db.String(50))
    password = db.Column(db.String(100))


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'x-access-token' in request.headers:
            token = request.headers['x-access-token']
        if not token:
            return jsonify({'message': 'Нет токена'}), 401
        try:
            jwt.decode(token, app.config['SECRET_KEY'], algorithms="HS256")
        except:
            return jsonify({'message': 'Неверный токен'}), 401
        return f(*args, **kwargs)
    return decorated

# СОЗДАТЬ ПОЛЬЗОВАТЕЛЯ
@app.route('/user', methods=['POST'])
def create_user():
    data = request.get_json()
    hashed_password = generate_password_hash(data['password'], method='sha256')
    new_user = User(public_id=str(uuid.uuid4()), name=data['name'], password=hashed_password)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'message': 'Создан новый пользователь'})


# ЗАЛОГИНИТЬСЯ И ПОЛУЧИТЬ ТОКЕН
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
            {'public_id': user.public_id, 'exp': datetime.utcnow() + timedelta(hours=24)},
            app.config['SECRET_KEY'],
            algorithm="HS256"
        )
        return jsonify({'token': token})
    return make_response('Неверный логин или пароль', 401)


# ПОЛУЧИТЬ ВСЕХ ПОЛЬЗОВАТЕЛЕЙ (ДЛЯ ТЕСТИРОВАНИЯ ТОКЕНА)
@app.route('/user', methods=['GET'])
@token_required
def get_all_users():
    users = User.query.all()
    users_list = [
        {
            'public_id': user.public_id,
            'name': user.name,
            'password': user.password
        }
        for user in users]
    return jsonify({'users': users_list})


if __name__ == '__main__':
    app.run(debug=True)
