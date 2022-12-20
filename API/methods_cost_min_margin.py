from flask import abort
from flask_restful import Resource, reqparse
from datetime import date
from shared.db import run_sql_insert_many, get_table_cols
from API.config import MAX_NUMBER_OF_PRODUCTS, PRINT_DB_INSERTS


def insert_into_db(table_name: str, dataset: list, account_id: int, warehouse_id: str, api_id: str, add_date=False):
    if dataset:
        for row in dataset:
            if table_name != 'client_margin':  # для таблицы margin не записываем account_id
                row['account_id'] = account_id
            row['api_id'] = api_id
            if warehouse_id:
                row['warehouse_id'] = warehouse_id
            if add_date:
                row['date'] = str(date.today())
        dataset_fields = list(dataset[0].keys())
        table_fields = get_table_cols(table_name)
        actual_fields = list(set(dataset_fields) & set(table_fields))
        fields_difference = list(set(dataset_fields) - set(table_fields))
        dataset = [{key: val for key, val in row.items() if key not in fields_difference} for row in dataset]
        fields = ','.join(actual_fields)
        values = ','.join([f'%({value})s' for value in actual_fields])
        sql = f'INSERT INTO {table_name} ({fields}) VALUES ({values})'
        run_sql_insert_many(sql, dataset)

        if PRINT_DB_INSERTS:
            print(len(dataset), 'records inserted in', table_name, ' / account_id=', account_id)


parser_price = reqparse.RequestParser()
parser_price.add_argument('api_id', type=str, required=True)
parser_price.add_argument('offer_id', type=str, action='append', required=True)
parser_price.add_argument('price', type=float, action='append', required=True)

parser_margin = reqparse.RequestParser()
parser_margin.add_argument('api_id', type=str, required=True)
parser_margin.add_argument('offer_id', type=str, action='append', required=True)
parser_margin.add_argument('min_margin', type=float, action='append', required=True)


# --- ADD PRICES/COST TO DB ---
class AddPricesToDB(Resource):
    # @token_required
    def post(self):
        args = parser_price.parse_args()
        api_id = args['api_id']
        offer_id_list = args['offer_id']
        price_list = args['price']

        # валидация данных
        error_message = ''
        if not offer_id_list or not price_list:
            error_message += f'В запросе должен быть хотя бы один товар.'
        if len(offer_id_list) != len(price_list):
            error_message += f'Длина списка offer_id должна совпадать с длиной списка price.'
        if len(offer_id_list) > MAX_NUMBER_OF_PRODUCTS:
            error_message += f'В запросе > {MAX_NUMBER_OF_PRODUCTS} товаров.  Уменьшите кол-во товаров.'
        if error_message:
            abort(400, error_message)

        products = [{'offer_id': product[0], 'price': product[1]} for product in zip(offer_id_list, price_list)]
        insert_into_db('price_table', products, 0, '', api_id, add_date=True)
        return {'message': f'В таблицу price_table добавлены цены {len(products)} товаров'}, 201


# --- ADD MARGINS TO DB ---
class AddMarginsToDB(Resource):
    # @token_required
    def post(self):
        args = parser_margin.parse_args()
        api_id = args['api_id']
        offer_id_list = args['offer_id']
        margin_list = args['min_margin']

        # валидация данных
        error_message = ''
        if not offer_id_list or not margin_list:
            error_message += f'В запросе должен быть хотя бы один товар.'
        if len(offer_id_list) != len(margin_list):
            error_message += f'Длина списка offer_id должна совпадать с длиной списка margin.'
        if len(offer_id_list) > MAX_NUMBER_OF_PRODUCTS:
            error_message += f'В запросе > {MAX_NUMBER_OF_PRODUCTS} товаров.  Уменьшите кол-во товаров.'
        if error_message:
            abort(400, error_message)

        products = [{'offer_id': product[0], 'min_margin': product[1]} for product in zip(offer_id_list, margin_list)]
        insert_into_db('client_margin', products, 0, '', api_id, add_date=True)
        return {'message': f'В таблицу margin добавлена маржа для {len(products)} товаров'}, 201


class TestAPI(Resource):
    def get(self):
        return {'message': 'Cost and margins methods OK'}