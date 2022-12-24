from flask import Flask, jsonify, request, make_response
from flask.views import MethodView
from shared.config import *
from shared.models import *
from shared.auth import token_required, app


# --- CLIENTS ---
class ClientView(MethodView):

    def get(self):
        clients = Client.query.all()
        if clients:
            clients = [
                {
                    'client_id': client.id,
                    'name': client.name,
                    'address': client.address
                }
                for client in clients]
            return jsonify({'clients': clients}), 200
        else:
            return jsonify({'message': 'clients do not exist'}), 404

    # def post(self):  # --- метод добавления клиента уже есть в shared.auth.py ---
    #     data = request.json
    #     new_client = Client(name=data['name'], address=data['address'])
    #     db.session.add(new_client)
    #     new_warehouse = Warehouse(wh_type='virtual', warehouse_id=str(new_client.id) + '_virtual', name='virtual')
    #     db.session.add(new_warehouse)  # номер виртуального склада присваивается автоматически client_id + _virtual
    #     db.session.commit()
    #     return jsonify({'message': 'client added', 'client_id': new_client.id, 'warehouse_id': new_warehouse.id}), 201

    def delete(self, client_id):
        client = Client.query.filter_by(id=client_id).first()
        if client:
            db.session.delete(client)
            db.session.commit()
            return jsonify({'message': 'client deleted'}), 200
        else:
            return jsonify({'message': 'client does not exist'}), 404

    def patch(self, client_id):
        data = request.json
        client = Client.query.filter_by(id=client_id).first()
        if client:
            for key, value in data.items():
                setattr(client, key, value)
            db.session.commit()
            return jsonify({'message': 'client updated'}), 200
        else:
            return jsonify({'message': 'client does not exist'}), 404


# --- ACCOUNTS ---
class AccountView(MethodView):

    def get(self):
        accounts = Account.query.all()
        if accounts:
            accounts = [
                {
                    'account_id': account.id,
                    'mp_id': account.mp_id,
                    'client_id': account.client_id,
                    'name': account.name,
                    'status': account.status
                }
                for account in accounts]
            return jsonify({'accounts': accounts}), 200
        else:
            return jsonify({'message': 'accounts do not exist'}), 404

    def post(self):
        data = request.json
        new_account = Account(
            mp_id=data['mp_id'],
            client_id=data['client_id'],
            name=data['name'],
            status=data['status']
        )
        db.session.add(new_account)
        db.session.commit()
        return jsonify({'message': 'account added', 'account_id': new_account.id}), 201

    def delete(self, account_id):
        account = Account.query.filter_by(id=account_id).first()
        if account:
            db.session.delete(account)
            db.session.commit()
            return jsonify({'message': 'account deleted'}), 200
        else:
            return jsonify({'message': 'account does not exist'}), 404

    def patch(self, account_id):
        data = request.json
        account = Account.query.filter_by(id=account_id).first()
        if account:
            for key, value in data.items():
                setattr(account, key, value)
            db.session.commit()
            return jsonify({'message': 'account updated'}), 200
        else:
            return jsonify({'message': 'account does not exist'}), 404


# --- WAREHOUSES ---
class WarehouseView(MethodView):

    def get(self):
        warehouses = Warehouse.query.all()
        if warehouses:
            warehouses = [
                {
                    'id': warehouse.id,
                    'warehouse_id': warehouse.warehouse_id,
                    'wh_type': warehouse.wh_type,
                    'name': warehouse.name,
                    'is_rfbs': warehouse.is_rfbs
                }
                for warehouse in warehouses]
            return jsonify({'warehouses': warehouses}), 200
        else:
            return jsonify({'message': 'warehouses do not exist'}), 404

    def post(self):
        data = request.json
        new_warehouse = Warehouse(
            warehouse_id=data['warehouse_id'],
            wh_type=data['wh_type'],
            name=data['name'],
            is_rfbs=data['is_rfbs']
        )
        db.session.add(new_warehouse)
        db.session.commit()
        return jsonify({'message': 'warehouse added', 'warehouse_id': new_warehouse.id}), 201

    def delete(self, account_id):
        warehouse = Warehouse.query.filter_by(id=account_id).first()
        if warehouse:
            db.session.delete(warehouse)
            db.session.commit()
            return jsonify({'message': 'warehouse deleted'}), 200
        else:
            return jsonify({'message': 'warehouse does not exist'}), 404

    def patch(self, account_id):
        data = request.json
        warehouse = Warehouse.query.filter_by(id=account_id).first()
        if warehouse:
            for key, value in data.items():
                setattr(warehouse, key, value)
            db.session.commit()
            return jsonify({'message': 'warehouse updated'}), 200
        else:
            return jsonify({'message': 'warehouse does not exist'}), 404


# client routes
app.add_url_rule('/clients', view_func=ClientView.as_view('view_clients'), methods=['GET'])
app.add_url_rule('/clients', view_func=ClientView.as_view('add_client'), methods=['POST'])
app.add_url_rule('/clients/<int:client_id>', view_func=ClientView.as_view('delete_client'), methods=['DELETE'])
app.add_url_rule('/clients/<int:client_id>', view_func=ClientView.as_view('update_client'), methods=['POST', 'PATCH'])

# account routes
app.add_url_rule('/accounts', view_func=AccountView.as_view('view_accounts'), methods=['GET'])
app.add_url_rule('/accounts', view_func=AccountView.as_view('add_account'), methods=['POST'])
app.add_url_rule('/accounts/<int:account_id>', view_func=AccountView.as_view('delete_account'), methods=['DELETE'])
app.add_url_rule('/accounts/<int:account_id>', view_func=AccountView.as_view('update_account'), methods=['POST', 'PATCH'])

# warehouse routes
app.add_url_rule('/warehouses', view_func=WarehouseView.as_view('view_warehouses'), methods=['GET'])
app.add_url_rule('/warehouses', view_func=WarehouseView.as_view('add_warehouse'), methods=['POST'])
app.add_url_rule('/warehouses/<int:warehouse_id>', view_func=WarehouseView.as_view('delete_warehouse'), methods=['DELETE'])
app.add_url_rule('/warehouses/<int:warehouse_id>', view_func=WarehouseView.as_view('update_warehouse'), methods=['POST', 'PATCH'])

app.run()
