from flask import Flask, request, abort
from flask_restful import Api, Resource, reqparse
from loguru import logger
import concurrent.futures
import datetime
from MARKETPLACES.ozon.ozon import OzonApi
from MARKETPLACES.wb.wb import WildberriesApi
from MARKETPLACES.yandex.yandex import YandexMarketApi
from MARKETPLACES.sber.sber import SberApi
from API.db import run_sql
from API.config import MAX_NUMBER_OF_PRODUCTS, NUMBER_OF_PRODUCTS_TO_PROCESS

logger.remove()
logger.add(sink='logfile.log', format="{time} {level} {message}", level="INFO")
app = Flask(__name__)
api = Api(app)

# функция применяет выборку к списку товаров products в соотв. с фильтром
def apply_filter(products: list, filters: dict):

    categories = filters['categories']
    brands = filters['brands']

    if categories:
        s_string = str(len(categories) * '%s,')[0:-1]
        sql = 'SELECT offer_id FROM product_list WHERE category_id IN (' + s_string + ')'
        result = run_sql(sql, tuple(categories))
        products_in_categories = list(sum(result, ()))  # преобразеум список кортежей в список
        filtered_products = [product for product in products if product['offer_id'] in products_in_categories]

    elif brands:
        pass

    else:
        pass # код для другого фильтра

    return filtered_products

# функция применяет действие к списку товаров products в соотв. с правилом
def apply_action(products: list, actions: dict):

    account_list = []

    if actions['send_stocks_to_accounts']:  # правило распеределения по % соотношению
        for account in actions['send_stocks_to_accounts']:
            # account - словарь {'account_id': 105, 'warehouse_id': 777, 'percentage': 30}
            products_for_account = [{'offer_id': product['offer_id'], 'stock': int(product['stock'] * account['percentage'] / 100)}
            for product in products]
            account_list.append({
                'account_id': account['account_id'],
                'warehouse_id': account['warehouse_id'],
                'products': products_for_account
            })

    elif actions['if_stock_less_or_equal_than_one_set_stock_at_zero']:  # правило обнуления всех остатков при остатке <= max_stock
        for account in actions['if_stock_less_or_equal_than_one_set_stock_at_zero']:
            # account - словарь {'account_id': 105, 'warehouse_id': 777}
            products_for_account = [{'offer_id': product['offer_id'], 'stock': 0} for product in products]
            account_list.append({
                'account_id': account['account_id'],
                'warehouse_id': account['warehouse_id'],
                'products': products_for_account
            })

    else: # логика для других правил
        pass

    return account_list
    # на выходе - список словарей:
    # {'account_id': 1001, 'warehouse_id': 777, 'products': [{'offer_id': 'ABC', 'stock': 100}, ...]}

# функция создает соотв. объект класса для отправки запроса на площадку
def create_mp_object(mp_id: int, client_id: str, api_key: str, campaign_id: str):
    if mp_id == 1:
        return OzonApi(client_id, api_key)
    elif mp_id == 2:
        return YandexMarketApi(client_id, api_key, campaign_id)
    elif mp_id == 3:
        return WildberriesApi(client_id)  # вместо api_key подставляем client_id в соотв. с данными в таблице account_list
    elif mp_id == 4:
        return SberApi(api_key)

# отправляем данные по одной партии товаров на разные аккаунты/площадки в разных потоках
def process_account_data(account: dict):

    # account - словарь {'account_id': 1001, 'warehouse_id': 777, 'products': [{'offer_id': 'ABC', 'stock': 100}, ...]}
    account_id = account['account_id']
    warehouse_id = account['warehouse_id']

    # из БД master_db по account_id получаем mp_id, client_id, api_key, campaign_id
    sql = 'SELECT mp_id, client_id_api, api_key, campaigns_id FROM account_list WHERE id=%s'
    result = run_sql(sql, (str(account_id), ))
    mp_id, client_id, api_key, campaign_id = result[0]

    # инициализируем объект соотв. класса для обращения в API площадки
    mp_object = create_mp_object(mp_id, client_id, api_key, campaign_id)

    # формируем список товар-количество для отправки в API площадки
    products = [{'offer_id': product['offer_id'], 'stock': product['stock']} for product in account['products']]
    update_stocks_list = mp_object.make_update_stocks_list(products, warehouse_id)

    if mp_id == 2: # для ЯМ
        response = 'Данные по остаткам сохранены в файл ym_data.json'
    else:
        # обращаемся к соотв. методу обновления остатков API МП и возвращаем результат (кроме ЯМ)
        mp_response = mp_object.update_stocks(update_stocks_list)
        # обрабытываем ответ площадки и формируем ответ клиенту (для теста ответ МП оставляем без изменений)
        response = mp_object.process_mp_response(mp_response, account_id, products)

    sql = 'SELECT mp_name FROM marketplaces_list WHERE id=%s'
    result = run_sql(sql, (str(mp_id), ))
    mp_name = result[0][0]

    return {'marketplace': mp_name, 'response': response}

parser = reqparse.RequestParser()
parser.add_argument("data", type=dict, location="json", required=True)

class AddStocksToDB(Resource):
    # @token_required
    def post(self):
        args = parser.parse_args()
        data = args['data']
        account_id = data['account_id']
        warehouse_id = str(data['warehouse_id'])
        products = data['products']
        total_num_of_products = len(products)

        # валидация вводимых клиентом данных
        if total_num_of_products > MAX_NUMBER_OF_PRODUCTS:
            abort(400, f'В запросе более {MAX_NUMBER_OF_PRODUCTS} товаров.  Уменьшите кол-во товаров.')

        date_now = str(datetime.date.today())
        # преобразовать данные c запроса клиента в список кортежей [( ....), (.....), ....] (удобно для записи в БД)
        products = [tuple(product.values()) + (account_id, warehouse_id, date_now) for product in products]

        # записать остатки в таблицу stock_by_wh (переписать код, чтобы добавлять сразу все записи в одном sql запросе)
        for product in products:
            sql = 'INSERT INTO stock_by_wh (offer_id, fbo_present, account_id, warehouse_id, date) ' \
                  'VALUES (%s, %s, %s, %s, %s) RETURNING id'
            result = run_sql(sql, product) # добавлено RETURNING id, чтобы не вылезала ошибка в функции run_sql

        return {'message': f'В базу данных добавлено {len(products)} товаров'}

class CreateRule(Resource):
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
        result = run_sql(sql, (client_id, rule))
        rule_id = result[0][0]

        return {'message': f'Правило добавлено. rule_id={rule_id}'}

class SendStocksToMarketplaces(Resource):
    # @token_required
    def post(self):
        args = parser.parse_args()
        data = args['data']
        warehouse_id = str(data['warehouse_id']) # номер склада-источника
        rule_id = str(data['rule_id']) # порядковый номер заполненного правила

        # проверить есть ли такое правило в БД (ПРОВЕРИТЬ СООТВЕТСТВИЕ rule_id КЛИЕНТУ)
        sql = 'SELECT rule FROM stock_rules WHERE id=%s'
        result = run_sql(sql, (rule_id,))
        if not result:
            abort(400, 'Правила с таким id не существует')
        rule = result[0][0]

        # достать из БД (таблица stock_by_wh) все товары по указанному warehouse_id (склад-источник)
        sql = 'SELECT offer_id, fbo_present FROM stock_by_wh WHERE warehouse_id=%s'
        products = run_sql(sql, (warehouse_id, ))  # products - список кортежей [(offer_id, stock), ..... ]
        # преобразовать список кортежей в список словарей (для удобства обработки)
        products = [{'offer_id': product[0], 'stock': int(product[1])} for product in products]
        total_num_of_products = len(products)

        # если в правиле указаны фильтры, сделать выборку
        filters = rule['filters']
        for filter in filters.values():
            if len(filter) != 0:
                products = apply_filter(products, filters)

        response_to_client = [] # здесь будем хранить ответ клиенту
        # делим все товары на части/партии размером NUMBER_OF_PRODUCTS_TO_PROCESS, цикл по партиям товаров
        for i in range(0, total_num_of_products, NUMBER_OF_PRODUCTS_TO_PROCESS):
            products_batch = products[i: i + NUMBER_OF_PRODUCTS_TO_PROCESS] # products_batch - одна партия товара

            # применить правило/действие(action)
            actions = rule['actions']
            accounts = apply_action(products_batch, actions)
            # accounts - список словарей: {'account_id': 1001, 'warehouse_id': 777, 'products': [{'offer_id': 'ABC', 'stock': 100}, ...]}

            # запускаем многопоточность (отдельный поток для каждого аккаунта)
            with concurrent.futures.ThreadPoolExecutor() as executor:
                results = [executor.submit(process_account_data, account) for account in accounts]
                # получаем результат выполнения функции process_account_data и записываем в ответ клиенту
                for result in results:
                    response_to_client.append(result.result()) # соединяем результаты выполнения всех потоков

        logger.info(f'Запрос выполнен успешно. URL:{request.base_url}')
        return response_to_client


class TestAPI(Resource):
    def post(self):
        return {'message': 'Все ОК'}


api.add_resource(AddStocksToDB, '/stocks')
api.add_resource(CreateRule, '/rules')
api.add_resource(SendStocksToMarketplaces, '/send_stocks')
api.add_resource(TestAPI, '/test')

if __name__ == '__main__':
    app.run(debug=True)