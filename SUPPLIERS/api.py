from flask import Flask, jsonify, request, make_response
from flask.views import MethodView
from datetime import datetime
from shared.models import *
from shared.auth import token_required, app


# --- SEND SUPPLIERS DATA TO stock_by_wh and price_table ---
class SendSuppliersData(MethodView):
    @token_required
    def post(self, client_id, rule_id):  # client_id пробрасывается из декоратора token_required
        rule = SupplierRules.query.filter_by(id=rule_id).filter_by(client_id=client_id).first()
        if not rule:
            return jsonify({'message': 'rule does not exist'}), 404
        rule = rule.rule
        # сделать join из таблиц suppliers_data + supplier_client для заданного client_id
        query = db.session.query(SupplierData, SupplierClient).\
            join(SupplierClient, SupplierData.supplier_id == SupplierClient.supplier_id)
        records = query.filter_by(client_id=client_id).all()

        # применить фильтры (возможно переписать)
        categories = rule['filters']['categories']
        if categories:
            records = [record for record in records if record[0].category in categories]
        brands = rule['filters']['brands']
        if brands:
            records = [record for record in records if record[0].brand in brands]

        stocks = [
            {
                'offer_id': record[0].offer_id,
                'fbo_present': record[0].stock,
                'date': record[0].date
            }
            for record in records]
        prices = [
            {
                'offer_id': record[0].offer_id,
                'price': record[0].price,
                'date': record[0].date
            }
            for record in records]

        # найти номер виртуального склада
        account = Account.query.filter_by(client_id=client_id, mp_id=5).first()
        warehouse = Warehouse.query.filter_by(account_id=account.id).first()

        for stock in stocks:  # !!! ПЕРЕДЕЛАТЬ ЧТОБЫ ДОБАВЛЯТЬ СРАЗУ ВСЕ ЗАПИСИ (db.session.add_all(data))
            new_stock = StockByWarehouse(
                offer_id=stock['offer_id'],
                fbo_present=stock['fbo_present'],
                warehouse_id=warehouse.warehouse_id,  # вставляем номер вирт. склада
                date=stock['date'],
                api_id=warehouse.api_id  # вставляем номер api_id с таблицы wh_table (или лучше брать token???)
            )
            db.session.add(new_stock)
            db.session.commit()

        for price in prices:  # !!! ПЕРЕДЕЛАТЬ ЧТОБЫ ДОБАВЛЯТЬ СРАЗУ ВСЕ ЗАПИСИ (db.session.add_all(data))
            new_price = Price(
                offer_id=price['offer_id'],
                price=price['price'],
                date=price['date'],
                api_id=warehouse.api_id  # вставляем номер api_id с таблицы wh_table (или лучше брать token???)
            )
            db.session.add(new_price)
            db.session.commit()

        return jsonify({'message': 'stocks and price are added to stock_by_wh и price_table'}), 201


# --- SUPPLIERS --- как защищать/декорировать эти методы (@token_required???)
class SupplierView(MethodView):

    def get(self, supplier_id):
        supplier = Supplier.query.filter_by(id=supplier_id).first()
        if supplier:
            supplier = {
                    'company': supplier.company,
                    'resource_url': supplier.resource_url,
                    'connection_method': supplier.connection_method,
                    'api_key': supplier.api_key,
                    'url_stocks': supplier.url_stocks,
                    'url_prices': supplier.url_prices,
                }
            return jsonify({'supplier': supplier}), 200
        else:
            return jsonify({'message': 'supplier does not exist'}), 404

    def post(self):
        data = request.json
        new_supplier = Supplier(
            company=data['company'],
            resource_url=data['resource_url'],
            connection_method=data['connection_method'],
            api_key=data['api_key'],
            url_stocks=data['url_stocks'],
            url_prices=data['url_prices']
        )
        db.session.add(new_supplier)
        db.session.commit()
        return jsonify({'message': 'supplier added', 'supplier_id': new_supplier.id}), 201

    def delete(self, supplier_id):
        supplier = Supplier.query.filter_by(id=supplier_id).first()
        if supplier:
            db.session.delete(supplier)
            db.session.commit()
            return jsonify({'message': 'supplier deleted'}), 200
        else:
            return jsonify({'message': 'supplier does not exist'}), 404

    def patch(self, supplier_id):
        data = request.json
        supplier = Supplier.query.filter_by(id=supplier_id).first()
        if supplier:
            for key, value in data.items():
                setattr(supplier, key, value)
            db.session.commit()
            return jsonify({'message': 'supplier updated'}), 200
        else:
            return jsonify({'message': 'supplier does not exist'}), 404


# --- SUPPLIER CLIENT ---
class SupplierClientView(MethodView):

    @token_required
    def get(self, client_id):
        suppliers = SupplierClient.query.filter_by(client_id=client_id).all()
        if suppliers:
            suppliers = [
                {
                    'supplier_id': supplier.supplier_id,
                    'client_id': supplier.client_id,
                    'last_request_date': supplier.last_request_date,
                }
                for supplier in suppliers]
            return jsonify(suppliers), 200
        else:
            return jsonify({'message': 'suppliers do not exist for this client'}), 404

    @token_required
    def post(self, client_id, supplier_id):
        new_supplier_client = SupplierClient(
            supplier_id=supplier_id,
            client_id=client_id,
            last_request_date=datetime.today()
        )
        db.session.add(new_supplier_client)
        db.session.commit()
        return jsonify({'message': 'supplier added', 'supplier_id': new_supplier_client.supplier_id}), 201

    @token_required
    def delete(self, client_id, supplier_id):
        supplier_client = SupplierClient.query.filter_by(client_id=client_id, supplier_id=supplier_id).first()
        if supplier_client:
            db.session.delete(supplier_client)
            db.session.commit()
            return jsonify({'message': 'supplier deleted'}), 200
        else:
            return jsonify({'message': 'supplier does not exist'}), 404


# --- SUPPLIER RULES ---
class SupplierRulesView(MethodView):

    @token_required
    def get(self, client_id):
        rules = SupplierRules.query.filter_by(client_id=client_id).all()
        if rules:
            rules = [
                {
                    'rule_id': rule.id,
                    'rule': rule.rule,
                }
                for rule in rules]
            return jsonify({'client_id': client_id, 'rules': rules}), 200
        else:
            return jsonify({'message': 'no rules listed for this client'}), 404

    @token_required
    def post(self, client_id):
        rule = request.json
        new_rule = SupplierRules(
            rule=rule,
            client_id=client_id
        )
        db.session.add(new_rule)
        db.session.commit()
        return jsonify({'message': 'rule added', 'rule_id': new_rule.id}), 201

    @token_required
    def delete(self, client_id, rule_id):
        rule = SupplierRules.query.filter_by(id=rule_id).filter_by(client_id=client_id).first()
        if rule:
            db.session.delete(rule)
            db.session.commit()
            return jsonify({'message': 'rule deleted'}), 200
        else:
            return jsonify({'message': 'rule does not exist'}), 404

    @token_required
    def patch(self, client_id, rule_id):
        data = request.json
        rule = SupplierRules.query.filter_by(id=rule_id).filter_by(client_id=client_id).first()
        if rule:
            for key, value in data.items():
                setattr(rule, key, value)
            db.session.commit()
            return jsonify({'message': 'rule updated'}), 200
        else:
            return jsonify({'message': 'rule does not exist'}), 404


# send suppliers_data to stock_by_wh and price_table
app.add_url_rule('/suppliers/rules/<int:rule_id>', view_func=SendSuppliersData.as_view('send_suppliers'), methods=['POST'])

# supplier routes
app.add_url_rule('/suppliers/<int:supplier_id>', view_func=SupplierView.as_view('view_suppliers'), methods=['GET'])
app.add_url_rule('/suppliers', view_func=SupplierView.as_view('add_supplier'), methods=['POST'])
app.add_url_rule('/suppliers/<int:supplier_id>', view_func=SupplierView.as_view('delete_supplier'), methods=['DELETE'])
app.add_url_rule('/suppliers/<int:supplier_id>', view_func=SupplierView.as_view('update_supplier'), methods=['POST', 'PATCH'])

# supplier_client routes
app.add_url_rule('/supplier_client', view_func=SupplierClientView.as_view('view_supplier_client'), methods=['GET'])
app.add_url_rule('/supplier_client/<int:supplier_id>', view_func=SupplierClientView.as_view('add_supplier_client'), methods=['POST'])
app.add_url_rule('/supplier_client/<int:supplier_id>', view_func=SupplierClientView.as_view('delete_supplier_client'), methods=['DELETE'])
# app.add_url_rule('/supplier_client', view_func=SupplierClientView.as_view('update_supplier_client'), methods=['PATCH'])

# supplier rules routes
app.add_url_rule('/suppliers/rules', view_func=SupplierRulesView.as_view('view_rules'), methods=['GET'])
app.add_url_rule('/suppliers/rules', view_func=SupplierRulesView.as_view('add_rule'), methods=['POST'])
app.add_url_rule('/suppliers/rules/<int:rule_id>', view_func=SupplierRulesView.as_view('delete_rule'), methods=['DELETE'])
app.add_url_rule('/suppliers/rules/<int:rule_id>', view_func=SupplierRulesView.as_view('update_rule'), methods=['PATCH'])

app.run()
