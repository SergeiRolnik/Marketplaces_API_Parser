import requests
from datetime import date
import time
from API.db import run_sql
from loguru import logger
from API.MARKETPLACES.wb.config import \
    URL_WILDBERRIES_INFO, \
    URL_WILDBERRIES_PRICES, \
    URL_WILDBERRIES_STOCKS_FBO, \
    URL_WILDBERRIES_STOCKS_FBS


class WildberriesApi:
    def __init__(self, api_key: str, supplier_api_key: str):
        self.api_key = api_key                    # API-ключ для доступа к методам /public/api/v1 и /api/v2
        self.supplier_api_key = supplier_api_key  # API-ключ для доступа к методам /api/v1/supplier

    def get_headers(self) -> dict:
        headers = {
            'Authorization': self.api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
                }
        return headers

    def get(self, url: str, params: dict):
        response = requests.get(url=url, headers=self.get_headers(), params=params)
        if response.status_code == 200:
            logger.info(f'Запрос выполнен успешно Статус код:{response.status_code} URL:{url}')
            return response.json()
        else:
            logger.error(f'Ошибка в выполнении запроса Статус код:{response.status_code} URL:{url}')

    def post(self, url: str, params):
        response = requests.post(url=url, headers=self.get_headers(), json=params)
        if response.status_code == 200:
            logger.info(f'Запрос выполнен успешно Статус код:{response.status_code} URL:{url}')
            return response.json()
        else:
            logger.error(f'Ошибка в выполнении запроса Статус код:{response.status_code} URL:{url}')

    # --- ФУНКЦИИ STOCKS
    def get_stocks_fbo(self):  # GET /api/v2/stocks (--- функция для сбора остатков FBO ---)
        NUMBER_OF_RECORDS_PER_PAGE = 3
        count = 0
        product_list = []
        while True:
            params = {
                'skip': count * NUMBER_OF_RECORDS_PER_PAGE,  # cколько записей пропустить (для пагинации)
                'take': NUMBER_OF_RECORDS_PER_PAGE           # cколько записей выдать (для пагинации)
                    }
            response = self.get(URL_WILDBERRIES_STOCKS_FBO, params)

            print('response', response)
            total = response.get('total')
            if not response or total == 0:
                break
            products = response.get('stocks')
            product_list = [
                {
                    'warehouse_id': product['warehouseId'],
                    'offer_id': product['article'],
                    'product_id': '',  # в методе /api/v2/stocks нет nmId
                    'stock_fbo': product['stock'],
                    'stock_fbs': 0
                }
                for product in products
            ]
            count += 1
            if total <= count * NUMBER_OF_RECORDS_PER_PAGE:
                break

            # --- TESTING ---
            if count > 2:
                break

            time.sleep(3)
        return product_list
        # формат [{'warehouse_id': ..., 'offer_id': ..., 'product_id': ..., 'stock_fbo': ... , 'stock_fbs': ...}, ...]

    # также можно собирать цены --- STOCKS / PRICES ---
    def get_stocks_fbs(self):  # GET /api/v1/supplier/stocks (--- функция для сбора остатков FBS ---)
        params = {
            'key': self.supplier_api_key,  # оба параметра обязательные
            'dateFrom': date.today()
        }
        products = self.get(URL_WILDBERRIES_STOCKS_FBS, params)
        products = [
            {
                'warehouse_id': product['warehouse'],
                'offer_id': product['supplierArticle'],
                'product_id': str(product['nmId']),
                'stock_fbo': 0,
                'stock_fbs': product['quantityFull'],
                'price': product['Price']
            }
            for product in products
        ]
        return products
        # формат [{'warehouse_id': ..., 'offer_id': ..., 'stock_fbo': ... , 'stock_fbs': ..., 'price', ....}, ...]

    def update_stocks(self, stocks: list):  # POST /api/v2/stocks (обновление остатков)
        # stocks - список словарей типа {'barcode': str, 'stock': int, 'warehouseId': int}
        return self.post(URL_WILDBERRIES_STOCKS_FBO, stocks)

    # --- ФУНКЦИИ PRICES
    def get_prices(self) -> list:  # GET /public/api/v1/info (номенклатуры,цены, скидки и промокоды)
        params = {'quantity': 0}  # 2 - товар с нулевым остатком, 1 - с ненулевым остатком, 0 - с любым остатком
        products = self.get(URL_WILDBERRIES_INFO, params)
        products = [
            {
                'offer_id': '',  # !!! надо найти offer_id по nmId
                'product_id': str(product.get('nmId')),  # нет barcode, поэтому в качестве product_id вставляем nmId
                'price': product.get('price')
            }
            for product in products
        ]
        return products
        # список словарей [{'offer_id': ...., 'product_id': ...., 'price': ....}, ....]

    def update_prices(self, prices: list):  # POST /public/api/v1/prices (обновление цен)
        # prices - список словарей типа {'nmId': int, 'price': int}
        return self.post(URL_WILDBERRIES_PRICES, prices)

    # ПОДГОТОВИТЬ СПИСКИ ДЛЯ ОБНОВЛЕНИЯ ОСТАТКОВ НА ПЛОЩАДКЕ
    def make_update_stocks_list(self, products: list, warehouse_id: str):
        update_stocks_list = []
        for product in products:  # products - список словарей {'offer_id: ....., 'stock': .....}
            offer_id = product['offer_id']
            stock = product['stock']
            # обращение к БД, чтобы по id найти barcode (возможно, нужно обратиться к соотв. методу WB)
            sql = 'SELECT barcode FROM product_list WHERE offer_id=%s'
            result = run_sql(sql, (offer_id, ))
            barcode = result[0][0]
            update_stocks_list.append({
                'barcode': barcode,
                'stock': stock,
                'warehouseId': int(warehouse_id)
            })
        return update_stocks_list

    # функция обрабатывает ответ с каждой площадки
    # в результате клиенту отправляется список словарей {'product_id': ..., 'account_id': ...., 'updated': True/False}
    def process_mp_response(self, response: dict, account_id: int, products: list):
        # processed_response = []

        # формат ответа WB при успешном выполнении запроса
        # {'additionalErrors': None, 'data': {'errors': None}, 'errorText': '', 'error': False}
        # в ответе от WB товары не перечисляются, поэтому, если нет ошибок, выводим, что для всех товаров все ок
        # for product in products:
        #     processed_response.append(
        #         {'offer_id': product['offer_id'], 'account_id': account_id, 'updated': not response['error']})

        return response
