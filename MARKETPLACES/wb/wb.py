import requests
from datetime import date
import time
from loguru import logger
from itertools import zip_longest
from PARSER.config import CHUNK_SIZE, SLEEP_TIME
from shared.db import run_sql_get_product_ids, run_sql, run_sql_api
from MARKETPLACES.wb.config import \
    URL_WILDBERRIES_INFO, \
    URL_WILDBERRIES_PRICES, \
    URL_WILDBERRIES_STOCKS_FBO, \
    URL_WILDBERRIES_STOCKS_FBS, \
    URL_WILDBERRIES_WAREHOUSES


class WildberriesApi:
    def __init__(self, api_key: str, supplier_api_key: str):
        self.api_key = api_key                    # API-ключ для доступа к методам /public/api/v1 и /api/v2  (mp_id = 15)
        self.supplier_api_key = supplier_api_key  # API-ключ для доступа к методам /api/v1/supplier  (mp_id = 3)

    def get_headers(self) -> dict:
        headers = {
            'Authorization': self.api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
                }
        return headers

    def get(self, url: str, params: dict, stream: bool):
        response = requests.get(url=url, headers=self.get_headers(), params=params, stream=stream)
        if response.status_code == 200:
            return response
        else:
            logger.error(f'Ошибка в выполнении запроса Статус код:{response.status_code} URL:{url}')

    def post(self, url: str, params):
        response = requests.post(url=url, headers=self.get_headers(), json=params)
        if response.status_code == 200:
            return response
        else:
            logger.error(f'Ошибка в выполнении запроса Статус код:{response.status_code} URL:{url}')

    def append_product_ids(self, products: list) -> list:  # ИСПОЛЬЗУЕТСЯ ТОЛЬКО ДЛЯ update_prices
        offer_ids = [product['offer_id'] for product in products]
        sql = "SELECT offer_id, product_id FROM product_list WHERE product_id IN (%s)" % str(offer_ids).strip('[]')
        offer_product_ids = run_sql_get_product_ids(sql)
        products = sorted(products, key=lambda item: item['offer_id'])
        offer_product_ids = sorted(offer_product_ids, key=lambda item: item['offer_id'])
        products = [{**k, **v} for k, v in zip_longest(products, offer_product_ids, fillvalue={'product_id': None})]
        return products

    # --- ФУНКЦИИ WAREHOUSES ---
    def get_warehouses(self):
        warehouses = []
        response = self.get(URL_WILDBERRIES_WAREHOUSES, {}, False)  # stream=False
        if response:
            warehouses = [
                {
                    'warehouse_id': warehouse['id'],
                    'name': warehouse['name']
                }
                for warehouse in response.json()]
        return warehouses

    # --- ФУНКЦИИ STOCKS
    def get_stocks_fbo(self):  # GET /api/v2/stocks (--- функция для сбора остатков FBO ---)
        NUMBER_OF_RECORDS_PER_PAGE = 1000
        count = 0
        total = 0
        products = []
        while True:
            params = {
                'skip': count * NUMBER_OF_RECORDS_PER_PAGE,
                'take': NUMBER_OF_RECORDS_PER_PAGE
                    }
            response = self.get(URL_WILDBERRIES_STOCKS_FBO, params, False)  # stream=False
            if response:
                response = response.json()
                if response.get('stocks'):
                    total = response.get('total')
                    products += [
                        {
                            'warehouse_id': product['warehouseId'],
                            'warehouse_name': product['warehouseName'],
                            'product_name': product['name'],
                            'category': product['subject'],
                            'barcode': product['barcode'],
                            'offer_id': product['article'],
                            'product_id': str(product['nmId']),
                            'fbo_present': product['stock'],
                            'fbs_present': 0
                        }
                        for product in response['stocks']]
            count += 1
            time.sleep(SLEEP_TIME)
            if count * NUMBER_OF_RECORDS_PER_PAGE % CHUNK_SIZE == 0:
                yield products
                products.clear()
            if total <= count * NUMBER_OF_RECORDS_PER_PAGE:
                if products:
                    yield products
                break

    # также можно собирать цены --- STOCKS / PRICES ---
    def get_stocks_fbs(self):  # GET /api/v1/supplier/stocks (--- функция для сбора остатков FBS ---)
        products = []
        params = {
            'key': self.supplier_api_key,
            'dateFrom': date.today()
        }
        response = self.get(URL_WILDBERRIES_STOCKS_FBS, params, True)  # stream=True

        if response:
            chunks = iter(response.json())
            for chunk in chunks:
                product = {
                        'warehouse_id': chunk['warehouse'],
                        'warehouse_name': chunk['warehouseName'],
                        'barcode': chunk['barcode'],
                        'product_name': chunk['subject'],
                        'product_category': chunk['category'],
                        'offer_id': chunk['supplierArticle'],
                        'product_id': str(chunk['nmId']),
                        'fbo_present': 0,
                        'fbs_present': chunk['quantityFull'],
                        'price': chunk['Price']
                    }
                products.append(product)

                if len(products) % CHUNK_SIZE == 0:
                    yield products
                    products.clear()

            if products:
                yield products

    def get_stocks_fbs_test(self):  # GET /api/v1/supplier/stocks (--- TESTING ---)
        products = []
        params = {
            'key': self.supplier_api_key,
            'dateFrom': date.today()
        }
        response = self.get(URL_WILDBERRIES_STOCKS_FBS, params, False)  # stream=True
        print('response get_stocks_fbs_test', response.json())
        if response:
            products = [
                {
                    'warehouse_id': product['warehouse'],
                    'warehouse_name': product['warehouseName'],
                    'barcode': product['barcode'],
                    'product_name': product['subject'],
                    'product_category': product['category'],
                    'offer_id': product['supplierArticle'],
                    'product_id': str(product['nmId']),
                    'fbo_present': 0,
                    'fbs_present': product['quantityFull'],
                    'price': product['Price']
                }
                for product in response.json()]
        return products

    # --- ФУНКЦИИ PRICES
    def get_prices(self):  # GET /public/api/v1/info
        products = []
        params = {'quantity': 0}  # 2 - товар с нулевым остатком, 1 - с ненулевым остатком, 0 - с любым остатком
        response = self.get(URL_WILDBERRIES_INFO, params, True)  # stream=True
        if response:
            chunks = iter(response.json())
            for chunk in chunks:
                product = {
                        'product_id': str(chunk.get('nmId')),
                        'price': chunk.get('price')
                    }
                products.append(product)
                if len(products) % CHUNK_SIZE == 0:
                    yield products
                    products.clear()
            if products:
                yield products  # список словарей {'product_id': ...., 'price': ....}

    def get_prices_test(self):  # GET /public/api/v1/info
        products = []
        params = {'quantity': 0}  # 2 - товар с нулевым остатком, 1 - с ненулевым остатком, 0 - с любым остатком
        response = self.get(URL_WILDBERRIES_INFO, params, False)
        if response:
            for product in response.json():
                products.append(
                    {
                        'product_id': str(product.get('nmId')),
                        'price': product.get('price')
                    }
                )
        return products

    # --- ФУНКЦИИ UPDATE (API STOCKS/PRICES) ---
    def update_stocks(self, stocks: list):  # POST /api/v2/stocks
        # stocks - список словарей типа {'barcode': str, 'stock': int, 'warehouseId': int}
        return self.post(URL_WILDBERRIES_STOCKS_FBO, stocks).json()

    def update_prices(self, prices: list):  # POST /public/api/v1/prices
        # на вход список словарей {'offer_id':..., 'price':...}
        prices = self.append_product_ids(prices)  # на выходе список словарей {'product_id':..., 'offer_id':..., 'price':...}
        prices = [{'nmId': product['product_id'], 'price': product['price']} for product in prices]
        return self.post(URL_WILDBERRIES_PRICES, prices).json()

    # ПОДГОТОВИТЬ СПИСКИ ДЛЯ ОБНОВЛЕНИЯ ОСТАТКОВ НА ПЛОЩАДКЕ
    def make_update_stocks_list(self, products: list, warehouse_id: str):
        update_stocks_list = []
        for product in products:  # products - список словарей {'offer_id: ....., 'stock': .....}
            offer_id = product['offer_id']
            stock = product['stock']
            # обращение к БД, чтобы по id найти barcode (возможно, нужно обратиться к соотв. методу WB)
            sql = 'SELECT barcode FROM product_list WHERE offer_id=%s'
            result = run_sql_api(sql, (offer_id, ))
            barcode = result[0][0]
            update_stocks_list.append({
                'barcode': barcode,
                'stock': stock,
                'warehouseId': int(warehouse_id)
            })
        return update_stocks_list

    # функция обрабатывает ответ с каждой площадки
    def process_mp_response(self, response: dict, account_id: int, products: list):
        return response
