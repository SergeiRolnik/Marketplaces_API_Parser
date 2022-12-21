from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Client(db.Model):
    __tablename__ = 'client'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    address = db.Column(db.String(50))
    balance = db.Column(db.Integer)
    login = db.Column(db.String(50))
    password = db.Column(db.String(100))
    salt = db.Column(db.String(100))
    active_hex = db.Column(db.String(200))
    status = db.Column(db.Integer)


class Account(db.Model):
    __tablename__ = 'account_list'
    id = db.Column(db.Integer, primary_key=True)
    mp_id = db.Column(db.Integer)
    client_id = db.Column(db.Integer, db.ForeignKey(Client.id))
    name = db.Column(db.String(50))
    status_1 = db.Column(db.String(50))


class AccountServiceData(db.Model):
    __tablename__ = 'account_service_data'
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey(Account.id))
    attribute_id = db.Column(db.Integer)
    attribute_value = db.Column(db.String(200))


class Warehouse(db.Model):
    __tablename__ = 'wh_table'
    id = db.Column(db.Integer, primary_key=True)
    wh_type = db.Column(db.String(50))
    warehouse_id = db.Column(db.Integer)
    is_rfbs = db.Column(db.String(10))
    name = db.Column(db.String(50))
    account_id = db.Column(db.Integer)
    api_id = db.Column(db.String(200))


class Supplier(db.Model):
    __tablename__ = 'suppliers'
    id = db.Column(db.Integer, primary_key=True)
    company = db.Column(db.String(50))
    resource_url = db.Column(db.String(100))
    connection_method = db.Column(db.String(50))
    api_key = db.Column(db.String(200))
    url_stocks = db.Column(db.String(100))
    url_prices = db.Column(db.String(100))


class SupplierClient(db.Model):
    __tablename__ = 'supplier_client'
    supplier_id = db.Column(db.Integer, db.ForeignKey(Supplier.id))
    client_id = db.Column(db.Integer, db.ForeignKey(Client.id))
    last_request_date = db.Column(db.Date)
    pk1 = db.PrimaryKeyConstraint(supplier_id, client_id)


class SupplierData(db.Model):
    __tablename__ = 'suppliers_data'
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey(Supplier.id))
    offer_id = db.Column(db.String(50))
    price = db.Column(db.Float)
    stock = db.Column(db.Integer)
    brand = db.Column(db.String(50))
    category = db.Column(db.String(50))
    date = db.Column(db.Date)


class StockByWarehouse(db.Model):
    __tablename__ = 'stock_by_wh'
    id = db.Column(db.Integer, primary_key=True)
    fbo_present = db.Column(db.Float)
    fbo_reserved = db.Column(db.Float)
    fbs_present = db.Column(db.Float)
    fbs_reserved = db.Column(db.Float)
    account_id = db.Column(db.Integer)
    date = db.Column(db.Date)
    warehouse_id = db.Column(db.String(50))
    product_id = db.Column(db.String(50))
    offer_id = db.Column(db.String(50))
    db_i = db.Column(db.String(50))
    api_id = db.Column(db.String(50))


class Price(db.Model):
    __tablename__ = 'price_table'
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer)
    product_id = db.Column(db.String(50))
    offer_id = db.Column(db.String(50))
    price = db.Column(db.Float)
    # ------- !!! вставить дополнительные столбцы  -----------
    db_i = db.Column(db.String(50))
    date = db.Column(db.Date)
    api_id = db.Column(db.String(50))


class ProductList(db.Model):
    __tablename__ = 'product_list'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.String(50))
    mapping = db.Column(db.String(50))
    api_id = db.Column(db.String(200))


class SupplierRules(db.Model):
    __tablename__ = 'supplier_rules'
    id = db.Column(db.Integer, primary_key=True)
    rule = db.Column(db.JSON())
    client_id = db.Column(db.Integer)
