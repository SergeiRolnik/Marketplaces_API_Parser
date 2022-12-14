from flask import Flask, request, jsonify, make_response, redirect, url_for, Response, json
import os
import hashlib
import jwt
from datetime import datetime, timedelta
from functools import wraps
from shared.config import ATTR_VIRT
from shared.db import DB_DSN
from shared.models import *

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = DB_DSN
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'x-access-token' in request.headers:
            token = request.headers['x-access-token']
        if not token:
            # return jsonify({'message': 'Нет токена'}), 401
            return Response(json.dumps({'message': 'Нет токена'}), status=401)
        try:
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms="HS256")
            kwargs['client_id'] = payload['client_id']  # --- проброс client_id в метод ---
        except:
            # return jsonify({'message': 'Неверный токен'}), 401
            return Response(json.dumps({'message': 'Неверный токен'}), status=401)
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


def get_client_from_token(token):
    payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms="HS256")
    client_id = payload['client_id']
    client = Client.query.filter_by(id=client_id).first()
    return client


# СОЗДАТЬ ПОЛЬЗОВАТЕЛЯ + ПОЛУЧИТЬ ТОКЕН
@app.route('/clients', methods=['POST'])
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
    return redirect(url_for('create_account', token=token))


# ЗАЛОГИНИТЬСЯ + ПОЛУЧИТЬ ТОКЕН
@app.route('/clients/login', methods=['POST'])
def login():
    auth = request.authorization
    login = auth.username
    password = auth.password
    if not auth or not login or not password:
        return 'Введите логин и пароль'
    client = Client.query.filter_by(login=login).first()
    if not client:
        return 'Клиента нет в базе данных'
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(client.salt), 100000, dklen=16)
    if key.hex() == client.active_hex:
        token = generate_token(client.id, key)
        return redirect(url_for('create_account', token=token))
    return 'Неверный логин или пароль'


# МЕТОД СОЗДАНИЯ АККАУНТА (СЮДА ПЕРЕДАЕМ ТОКЕН)
@app.route('/accounts', methods=['GET'])
def create_account():
    data = request.args
    token = data['token']
    client = get_client_from_token(token)
    client_id = client.id

    # создать виртуальный аккаунт
    new_account = Account(client_id=client_id, mp_id=5, name=f'{client.name}_virtual', status_1='Active')
    db.session.add(new_account)
    db.session.commit()
    account_id = new_account.id

    # записать токен в таблицу account_service_data
    new_account_service_data = AccountServiceData(account_id=account_id, attribute_id=ATTR_VIRT, attribute_value=token)
    db.session.add(new_account_service_data)
    db.session.commit()

    return redirect(url_for('create_virtual_warehouse', token=token))


# СОЗДАТЬ ВИРТУАЛЬНЫЙ СКЛАД
@app.route('/warehouses', methods=['GET'])
def create_virtual_warehouse():
    data = request.args
    token = data['token']
    client = get_client_from_token(token)
    client_id = client.id
    account = Account.query.filter_by(client_id=client_id).filter_by(mp_id=5).first()
    account_id = account.id
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
            'message': f'Для клиента {client_id} cозданы виртуальный аккаунт и склад',
            'account_id': account_id,
            'warehouse_id': new_warehouse.warehouse_id,
            'token': token
        }
    )


# ПОЛУЧИТЬ СПИСОК ВСЕХ КЛИЕНТОВ (ДЛЯ ТЕСТИРОВАНИЯ ТОКЕНА)
@app.route('/clients', methods=['GET'])
@token_required
def get_all_clients():
    clients = Client.query.all()
    token = request.headers['x-access-token']
    client = get_client_from_token(token)  # вытаскиваем из токена клиента, который сделал запрос
    clients_list = [
        {
            'client_id': client.id,
            'name': client.name,
            'login': client.login,
        }
        for client in clients]
    return jsonify({'client_who_sent_request': client.name, 'clients': clients_list})


if __name__ == '__main__':
    app.run(debug=True)
