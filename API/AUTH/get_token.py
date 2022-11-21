from flask import Flask, request, jsonify, make_response, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os
import hashlib
import jwt
from datetime import datetime, timedelta
from functools import wraps
from shared.db import DB_DSN

app = Flask(__name__)
app.config['SECRET_KEY'] = 'some secrete word'
app.config['SQLALCHEMY_DATABASE_URI'] = DB_DSN
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class Client(db.Model):
    __tablename__ = 'client'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    address = db.Column(db.String(200))
    balance = db.Column(db.Integer)
    login = db.Column(db.String(200))
    password = db.Column(db.String(32))  # в таблице client столбец называется pass
    salt = db.Column(db.String(32))
    active_hex = db.Column(db.String(32))
    status = db.Column(db.Integer)


class Account(db.Model):
    __tablename__ = 'account_list'
    id = db.Column(db.Integer, primary_key=True)
    mp_id = db.Column(db.Integer)
    client_id = db.Column(db.Integer, db.ForeignKey(Client.id))
    name = db.Column(db.String(50))
    status = db.Column(db.String(50))


class Warehouse(db.Model):
    __tablename__ = 'wh_table'
    id = db.Column(db.Integer, primary_key=True)
    wh_type = db.Column(db.String(50))
    warehouse_id = db.Column(db.Integer)
    name = db.Column(db.String(50))
    is_rfbs = db.Column(db.String(10))
    api_id = db.Column(db.String(200))


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


def generate_token(client_id, key):
    token = jwt.encode(
        {
            'client_id': client_id,
            'active_hex': key.hex(),
            'exp': datetime.utcnow() + timedelta(days=30)
        },
        app.config['SECRET_KEY'],
        algorithm="HS256"
    )
    return token


# СОЗДАТЬ ПОЛЬЗОВАТЕЛЯ + ПОЛУЧИТЬ ТОКЕН
@app.route('/client', methods=['POST'])
def create_client():
    data = request.get_json()
    name = data['name']
    login = data['login']
    password = data['password']
    client = Client.query.filter_by(login=login).first()
    if client:
        return 'Пользователь с таким логином уже существует'
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000, dklen=16)
    # поле password не нужно, так как "засоленый" пароль зашифрован в key (записываем в столбец active_hex)
    new_client = Client(name=name, login=login, salt=salt.hex(), active_hex=key.hex())
    db.session.add(new_client)
    db.session.commit()
    token = generate_token(new_client.id, key)
    return redirect(url_for('create_account', token=token, client_id=new_client.id))


# МЕТОД СОЗДАНИЯ АККАУНТА (СЮДА ПЕРЕДАЕМ ТОКЕН И ИДЕНТИФИКАТОР КЛИЕНТА)
@app.route('/account', methods=['GET'])
def create_account():
    data = request.args
    token = data['token']
    client_id = data['client_id']

    # ------------------------------------------------------------------------------------------------
    # создать запись в таблице account_list (mp_id = 5) + соотв. запись в таблице account_service_data
    # на выходе получаем account_id
    # ------------------------------------------------------------------------------------------------

    account_id = 999  # для теста
    return redirect(url_for('create_virtual_warehouse', token=token, account_id=account_id))


# СОЗДАТЬ ВИРТУАЛЬНЫЙ СКЛАД
@app.route('/warehouse', methods=['GET'])
def create_virtual_warehouse():
    data = request.args
    account_id = data['account_id']
    token = data['token']
    new_warehouse = Warehouse(
        warehouse_id=str(account_id) + '_virtual',  # придумать как присваивается warehouse_id
        wh_type='virtual',
        name='my virtual warehouse',
        is_rfbs='True',
        api_id=token
    )
    db.session.add(new_warehouse)
    db.session.commit()
    return jsonify(
        {
            'message': 'Созданы виртуальный аккаунт и склад',
            'account_id': account_id,
            'warehouse_id': new_warehouse.warehouse_id,
            'token': token
        }
    )


# ПОЛУЧИТЬ СПИСОК ВСЕХ КЛИЕНТОВ (ДЛЯ ТЕСТИРОВАНИЯ ТОКЕНА)
@app.route('/client', methods=['GET'])
@token_required
def get_all_clients():
    clients = Client.query.all()
    clients_list = [
        {
            'client_id': client.id,
            'name': client.name,
            'login': client.login,
        }
        for client in clients]
    return jsonify({'clients': clients_list})


if __name__ == '__main__':
    app.run(debug=True)
