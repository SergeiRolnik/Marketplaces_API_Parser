from flask import Flask, request, abort
from flask_restful import Api, Resource, reqparse
from loguru import logger
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import datetime
from itertools import groupby
from datetime import date
from MARKETPLACES.ozon.ozon import OzonApi
from MARKETPLACES.wb.wb import WildberriesApi
from MARKETPLACES.yandex.yandex import YandexMarketApi
from MARKETPLACES.sber.sber import SberApi
from shared.db import run_sql_api, run_sql_insert_many, get_table_cols
from shared.config import APP_ENV
from API.config import MAX_NUMBER_OF_PRODUCTS, NUMBER_OF_PRODUCTS_TO_PROCESS, PRINT_DB_INSERTS

logger.remove()
logger.add(sink='logfile.log', format="{time} {level} {message}", level="INFO")
app = Flask(__name__)
api = Api(app)


# группировка списка словарей по одному из ключей, например, account_id
def group_list_by_key(product_list: list, groupby_key: str, list_name: str) -> list:
    product_list = sorted(product_list, key=lambda k: k[groupby_key])
    product_list_grouppedby_key = []
    for key, value in groupby(product_list, lambda k: k[groupby_key]):
        products = list(value)
        for item in products:
            item.pop(groupby_key)
        product_list_grouppedby_key.append({groupby_key: key, list_name: products})
    return product_list_grouppedby_key


# функция применяет выборку к списку товаров products в соотв. с фильтром
def apply_filter(products: list, filters: dict) -> list:
    categories = filters.get('categories')
    brands = filters.get('brands')
    if categories:
        s_string = str(len(categories) * '%s,')[0:-1]
        sql = 'SELECT offer_id FROM product_list WHERE category_id IN (' + s_string + ')'
        result = run_sql_api(sql, tuple(categories))
        products_in_categories = list(sum(result, ()))  # преобразеум список кортежей в список
        products = [product for product in products if product['offer_id'] in products_in_categories]
    elif brands:
        pass
    else:
        pass  # код для другого фильтра
    return products


# функция применяет действие к списку товаров products в соотв. с правилом
def apply_action(products: list, actions: dict, product_list: str) -> list:
    account_list = []

    if product_list == 'stocks':  # правила для перемещения остатков

        if actions.get('send_stocks_to_accounts'):  # правило распределения по % соотношению
            for account in actions['send_stocks_to_accounts']:
                # account - словарь {'account_id': 105, 'warehouse_id': 777, 'percentage': 30}
                products_for_account = [{'offer_id': product['offer_id'], 'stock': int(product['stock'] * account['percentage'] / 100)}
                for product in products]
                account_list.append({
                    'account_id': account['account_id'],
                    'warehouse_id': account['warehouse_id'],
                    'stocks': products_for_account
                })

        elif actions.get('if_stock_less_or_equal_than_one_set_stock_at_zero'):  # правило обнуления всех остатков при остатке <= max_stock
            for account in actions['if_stock_less_or_equal_than_one_set_stock_at_zero']:
                # account - словарь {'account_id': 105, 'warehouse_id': 777}
                products_for_account = [{'offer_id': product['offer_id'], 'stock': 0} for product in products]
                account_list.append({
                    'account_id': account['account_id'],
                    'warehouse_id': account['warehouse_id'],
                    'stocks': products_for_account
                })

        else:
            pass  # логика для других правил

    if product_list == 'prices':  # правила для обновления цен

        if actions.get('set_price_at'):
            set_price_at = actions['set_price_at']
            for product in products:
                if product['price'] > actions['conditions']['max_price']:
                    product['price'] = set_price_at  # установить определенный уровень цены
                else:
                    product.pop()  # если цена товара не выше определенного уровня, ее не надо менять
            # сгруппировать список словарей по account_id
            account_list = group_list_by_key(products, 'account_id', 'prices')

        else:
            pass  # логика для других правил

    return account_list
    # на выходе - список словарей:
    # {'account_id': 1001, 'warehouse_id': 777, 'stocks': [{'offer_id': 'ABC', 'stock': 100}, ...]}
    # или
    # {'account_id': 1001, 'prices': [{'offer_id': 'ABC', 'price': 999}, ...]}


# функция создает соотв. объект класса для отправки запроса на площадку
def create_mp_object(mp_id: int, client_id: str, api_key: str, campaign_id: str):
    if mp_id == 1:
        return OzonApi(client_id, api_key)
    elif mp_id == 2:
        return YandexMarketApi(client_id, api_key, campaign_id)
    elif mp_id == 3:
        return WildberriesApi(client_id, api_key)  # вместо api_key подставляем client_id в соотв. с данными в таблице account_list
    elif mp_id == 4:
        return SberApi(api_key)


def insert_into_db(table_name: str, dataset: list, account_id: int, warehouse_id: str, api_id: str, add_date=False):
    if dataset:
        for row in dataset:
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


def validate(data: dict) -> dict:
    products = data['products']
    error_message = ''
    error_code = 0
    if len(products) > MAX_NUMBER_OF_PRODUCTS:
        error_message = f'В запросе более {MAX_NUMBER_OF_PRODUCTS} товаров.  Уменьшите кол-во товаров.'
        error_code = 400
    # другая валидация, если необходимо
    return {'message': error_message, 'code': error_code}


def map_offer_ids(account: dict) -> list:
    account_id = account['account_id']
    if 'prices' in account.keys():
        products = account['prices']
    if 'stocks' in account.keys():
        products = account['stocks']
    sql = 'SELECT supplier_offer_id, mp_offer_id FROM mapping_offers WHERE account_id=%s'
    mappings = run_sql_api(sql, (str(account_id), ))
    mappings = {mapping[0]: mapping[1] for mapping in mappings}
    df = pd.DataFrame.from_dict(products)
    df['offer_id'] = df['offer_id'].map(mappings)
    df = df[df['offer_id'].notna()]  # удалить те offer_id для которых нет маппинга в таблице mapping_offers
    return df.to_dict('records')


# отправляем данные по одной партии товаров на разные аккаунты/площадки в разных потоках
def process_account_data(account: dict):

    # account - словарь {'account_id': 1001, 'warehouse_id': 777, 'stocks': [{'offer_id': 'ABC', 'stock': 100}, ...]}
    # или
    # account - словарь {'account_id': 1001, 'prices': [{'offer_id': 'ABC', 'price': 100}, ...]}

    account_id = account['account_id']
    warehouse_id = account.get('warehouse_id')  # если есть склад

    # из БД (account_list) по account_id получаем mp_id, client_id, api_key, campaign_id
    sql = 'SELECT mp_id, client_id_api, api_key, campaigns_id FROM account_list WHERE id=%s'
    result = run_sql_api(sql, (str(account_id), ))
    mp_id, client_id, api_key, campaign_id = result[0]

    # инициализируем объект соотв. класса для обращения в API площадки
    mp_object = create_mp_object(mp_id, client_id, api_key, campaign_id)

    # ------------------------------------- UPDATE STOCKS --------------------------------------------
    if account.get('stocks'):
        # формируем список товар-количество для отправки в API площадки
        update_stocks_list = mp_object.make_update_stocks_list(map_offer_ids(account), warehouse_id)  # маппинг

        if mp_id == 2:  # для ЯМ
            response = 'Данные по остаткам сохранены в файл ym_data.json'
        else:
            # обращаемся к соотв. методу обновления остатков API МП и возвращаем результат (кроме ЯМ)
            mp_response = mp_object.update_stocks(update_stocks_list)
            # обрабытываем ответ площадки и формируем ответ клиенту (для теста ответ МП оставляем без изменений)
            response = mp_object.process_mp_response(mp_response, account_id, account['stocks'])

    # -------------------------------------- UPDATE PRICES -------------------------------------------
    if account.get('prices'):
        mp_response = mp_object.update_prices(map_offer_ids(account))  # маппинг
        response = mp_object.process_mp_response(mp_response, account_id, account['prices'])

    sql = 'SELECT mp_name FROM marketplaces_list WHERE id=%s'
    result = run_sql_api(sql, (str(mp_id), ))
    mp_name = result[0][0]

    return {'marketplace': mp_name, 'response': response}


parser = reqparse.RequestParser()
parser.add_argument('data', type=dict, location='json', required=True)


# --- ADD STOCKS TO DB ---
class AddStocksToDB(Resource):
    # @token_required
    def post(self):
        args = parser.parse_args()
        data = args['data']
        validation_result = validate(data)
        if validation_result['code'] != 0:
            abort(validation_result['code'], validation_result['error_message'])
        account_id = data['account_id']
        warehouse_id = str(data['warehouse_id'])
        products = data['products']
        api_id = run_sql_api('SELECT api_key FROM account_list WHERE id=%s', (str(account_id),))[0][0]
        insert_into_db('stock_by_wh', products, account_id, warehouse_id, api_id, add_date=True)
        return {'message': f'В базе данных обновлены остатки {len(products)} товаров'}


# --- ADD PRICES TO DB ---
class AddPricesToDB(Resource):
    # @token_required
    def post(self):
        args = parser.parse_args()
        data = args['data']
        validation_result = validate(data)
        if validation_result['code'] != 0:
            abort(validation_result['code'], validation_result['error_message'])
        account_id = data['account_id']
        products = data['products']
        api_id = run_sql_api('SELECT api_key FROM account_list WHERE id=%s', (str(account_id), ))[0][0]
        insert_into_db('price_table', products, account_id, api_id, add_date=True)
        return {'message': f'В базе данных обновлены цены {len(products)} товаров'}


class CreateStockRule(Resource):
    # @token_required
    def post(self):
        args = parser.parse_args()
        data = args['data']
        client_id = data['client_id']  # ВЗЯТЬ ИЗ ТОКЕНА
        filters = data['filters']
        actions = data['actions']
        rule = {"filters": filters, "actions": actions}
        # добавить правило в БД
        sql = 'INSERT INTO stock_rules (client_id, rule) VALUES (%s, %s) RETURNING id'
        result = run_sql_api(sql, (client_id, rule))
        rule_id = result[0][0]
        return {'message': f'Правило добавлено. rule_id={rule_id}'}


class CreatePriceRule(Resource):  # --- ПРОТЕСТИТЬ ---
    # @token_required
    def post(self):
        args = parser.parse_args()
        data = args['data']
        client_id = data['client_id']  # ВЗЯТЬ ИЗ ТОКЕНА
        filters = data['filters']
        actions = data['actions']
        rule = {"filters": filters, "actions": actions}
        # добавить правило в БД
        sql = 'INSERT INTO price_rules (client_id, rule) VALUES (%s, %s) RETURNING id'
        result = run_sql_api(sql, (client_id, rule))
        rule_id = result[0][0]
        return {'message': f'Правило добавлено. rule_id={rule_id}'}


# --- UPDATE STOCKS --- (ДОБАВИТЬ МАППИНГ OFFER_ID) ---
class SendStocksToMarketplaces(Resource):
    # @token_required
    def post(self):
        args = parser.parse_args()
        data = args['data']
        account_id = data['account_id']
        rule_id = data['rule_id']

        # проверить есть ли такое правило в таблице stock_rules для данного account_id
        sql = 'SELECT rule FROM stock_rules WHERE id=%s AND account_id=%s'
        result = run_sql_api(sql, (str(rule_id), str(account_id), ))
        if not result:
            abort(400, 'Правила с таким id не существует')
        rule = result[0][0]
        account_id = rule['account_id']
        warehouse_id = rule['warehouse_id']  # номер склада-источника

        # достать из БД (таблица stock_by_wh) все товары по указанному account_id и warehouse_id
        sql = '''
        SELECT account_id, warehouse_id, offer_id, fbo_present 
        FROM stock_by_wh WHERE account_id=%s AND warehouse_id=%s
        '''
        stocks = run_sql_api(sql, (account_id, warehouse_id, ))
        # stocks - список кортежей (account_id, warehouse_id, offer_id, stock)
        stocks = [
            {
                'account_id': product[0],
                'warehouse_id': product[1],
                'offer_id': product[2],
                'stock': product[3]
            }
            for product in stocks]
        total_num_of_stocks = len(stocks)
        stocks = apply_filter(stocks, rule.get('filters'))  # применить указанные в правиле фильтры

        response_to_client = []
        # делим все товары на части
        for i in range(0, total_num_of_stocks, NUMBER_OF_PRODUCTS_TO_PROCESS):
            stocks_batch = stocks[i: i + NUMBER_OF_PRODUCTS_TO_PROCESS]
            actions = rule['actions']
            accounts = apply_action(stocks_batch, actions, 'stocks')  # применить правило/действие(action)
            # accounts - список словарей: {'account_id': 1001, 'warehouse_id': 777, 'products': [{'offer_id': 'ABC', 'stock': 100}, ...]}

            # запускаем многопоточность (отдельный поток для каждого аккаунта)
            with ThreadPoolExecutor() as executor:
                futures = [executor.submit(process_account_data, account) for account in accounts]
                for future in futures:
                    response_to_client.append(future.result())

        logger.info(f'Запрос выполнен успешно. URL:{request.base_url}')
        return response_to_client


# --- UPDATE PRICES --- (ДОБАВИТЬ МАППИНГ OFFER_ID) ---
class SendPricesToMarketplaces(Resource):
    # @token_required
    def post(self):
        args = parser.parse_args()
        data = args['data']
        client_id = data['client_id']
        rule_id = data['rule_id']

        # проверить есть ли такое правило в таблице price_rules для данного client_id
        sql = 'SELECT rule FROM price_rules WHERE id=%s AND client_id=%s'
        result = run_sql_api(sql, (str(rule_id), str(client_id), ))
        if not result:
            abort(400, 'Правила с таким id не существует')
        rule = result[0][0]

        # получить список account_id по client_id
        sql = 'SELECT account_id FROM account_list WHERE client_id=%s'
        result = run_sql_api(sql, (str(client_id), ))
        account_ids = list(result[0])
        account_ids = str(account_ids).strip('[]')

        # достать из таблицы price_table все товары по указанному account_id
        sql = f'SELECT account_id, offer_id, price FROM price_table WHERE account_id IN ({account_ids})'
        prices = run_sql_api(sql, ())  # prices - список кортежей (offer_id, price)
        prices = [
            {
                'account_id': product[0],
                'offer_id': product[1],
                'price': product[2]
            }
            for product in prices]
        total_num_of_prices = len(prices)
        prices = apply_filter(prices, rule.get('filters'))  # применить указанные в правиле фильтры

        response_to_client = []
        # делим все товары на части
        for i in range(0, total_num_of_prices, NUMBER_OF_PRODUCTS_TO_PROCESS):
            prices_batch = prices[i: i + NUMBER_OF_PRODUCTS_TO_PROCESS]
            accounts = apply_action(prices_batch, rule.get('actions'), 'prices')  # применить правило/действие(action)
            # accounts - список словарей: {'account_id': 1001, 'prices': [{'offer_id': 'ABC', 'price': 100}, ...]}

            # запускаем многопоточность (отдельный поток для каждого аккаунта)
            with ThreadPoolExecutor() as executor:
                futures = [executor.submit(process_account_data, account) for account in accounts]
                for future in futures:
                    response_to_client.append(future.result())

        logger.info(f'Запрос выполнен успешно. URL:{request.base_url}')
        return response_to_client


class TestAPI(Resource):
    def post(self):
        return {'message': 'Все ОК'}


# --- STOCKS ROUTES ---
api.add_resource(AddStocksToDB, '/stocks')
api.add_resource(CreateStockRule, '/stock_rules')
api.add_resource(SendStocksToMarketplaces, '/send_stocks')

# --- PRICES ROUTES ---
api.add_resource(AddPricesToDB, '/prices')
api.add_resource(CreatePriceRule, '/price_rules')
api.add_resource(SendPricesToMarketplaces, '/send_prices')

# --- TEST ROUTE ---
api.add_resource(TestAPI, '/test')

if __name__ == '__main__':
    app.run(debug=True)
