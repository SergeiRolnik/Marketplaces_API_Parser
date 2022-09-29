import requests
from datetime import date
import time
from API.db import run_sql
from loguru import logger
from API.MARKETPLACES.wb.config import \
    URL_WILDBERRIES_INFO, \
    URL_WILDBERRIES_PRICES, \
    URL_WILDBERRIES_STOCKS_FBO, \
    URL_WILDBERRIES_STOCKS_FBS, \
    SLEEP_TIME, \
    CHUNK_SIZE


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

    def get(self, url: str, params: dict, stream: bool):
        response = requests.get(url=url, headers=self.get_headers(), params=params, stream=stream)
        if response.status_code == 200:
            logger.info(f'Запрос выполнен успешно Статус код:{response.status_code} URL:{url}')
            return response
        else:
            logger.error(f'Ошибка в выполнении запроса Статус код:{response.status_code} URL:{url}')

    def post(self, url: str, params):
        response = requests.post(url=url, headers=self.get_headers(), json=params)
        if response.status_code == 200:
            logger.info(f'Запрос выполнен успешно Статус код:{response.status_code} URL:{url}')
            return response
        else:
            logger.error(f'Ошибка в выполнении запроса Статус код:{response.status_code} URL:{url}')

    # --- ФУНКЦИИ STOCKS
    def get_stocks_fbo(self):  # GET /api/v2/stocks (--- функция для сбора остатков FBO ---)
        NUMBER_OF_RECORDS_PER_PAGE = 1000
        count = 0
        total = 0
        product_list = []
        while True:
            params = {
                'skip': count * NUMBER_OF_RECORDS_PER_PAGE,  # cколько записей пропустить (для пагинации)
                'take': NUMBER_OF_RECORDS_PER_PAGE           # cколько записей выдать (для пагинации)
                    }
            response = self.get(URL_WILDBERRIES_STOCKS_FBO, params, False)
            response = response.json()
            products = response.get('stocks')
            if products:
                total = response.get('total')
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
            time.sleep(SLEEP_TIME)
            if count * NUMBER_OF_RECORDS_PER_PAGE == CHUNK_SIZE:
                yield product_list
                product_list.clear()
            if total <= count * NUMBER_OF_RECORDS_PER_PAGE:
                if product_list:
                    yield product_list
                break
        # формат [{'warehouse_id': ..., 'offer_id': ..., 'product_id': ..., 'stock_fbo': ... , 'stock_fbs': ...}, ...]

    # также можно собирать цены --- STOCKS / PRICES ---
    def get_stocks_fbs(self):  # GET /api/v1/supplier/stocks (--- функция для сбора остатков FBS ---)
        params = {
            'key': self.supplier_api_key,  # оба параметра обязательные
            'dateFrom': date.today()
        }
        response = self.get(URL_WILDBERRIES_STOCKS_FBS, params, True)  # stream=True
        chunks = iter(response.json())
        products = []
        for chunk in chunks:
            product = {
                    'warehouse_id': chunk['warehouse'],
                    'offer_id': chunk['supplierArticle'],
                    'product_id': str(chunk['nmId']),
                    'stock_fbo': 0,
                    'stock_fbs': chunk['quantityFull'],
                    'price': chunk['Price']
                }
            products.append(product)
            if len(products) == CHUNK_SIZE:
                yield products
                products.clear()
        if products:
            yield products
            # формат [{'warehouse_id': ..., 'offer_id': ..., 'stock_fbo': ... , 'stock_fbs': ..., 'price', ....}, ...]

    def update_stocks(self, stocks: list):  # POST /api/v2/stocks (обновление остатков)
        # stocks - список словарей типа {'barcode': str, 'stock': int, 'warehouseId': int}
        return self.post(URL_WILDBERRIES_STOCKS_FBO, stocks).json()

    # --- ФУНКЦИИ PRICES
    def get_prices(self):  # GET /public/api/v1/info (номенклатуры,цены, скидки и промокоды)
        params = {'quantity': 0}  # 2 - товар с нулевым остатком, 1 - с ненулевым остатком, 0 - с любым остатком
        response = self.get(URL_WILDBERRIES_INFO, params, True)  # stream=True
        chunks = iter(response.json())
        products = []
        for chunk in chunks:
            product = {
                    'offer_id': '',  # !!! надо найти offer_id по nmId
                    'product_id': str(chunk.get('nmId')),
                    'price': chunk.get('price')
                }
            products.append(product)
            if len(products) == CHUNK_SIZE:
                yield products
                products.clear()
        if products:
            yield products  # список словарей [{'offer_id': ...., 'product_id': ...., 'price': ....}, ....]

    def update_prices(self, prices: list):  # POST /public/api/v1/prices (обновление цен)
        # prices - список словарей типа {'nmId': int, 'price': int}
        return self.post(URL_WILDBERRIES_PRICES, prices).json()

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
