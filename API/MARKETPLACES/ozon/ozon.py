import requests
import time
from loguru import logger
from API.MARKETPLACES.ozon.config import \
    URL_OZON_PRODUCTS, \
    URL_OZON_PRODUCT_INFO, \
    URL_OZON_STOCKS, \
    URL_OZON_STOCKS_FBS, \
    URL_OZON_PRICES, \
    URL_OZON_WAREHOUSES, \
    URL_OZON_STOCKS_INFO, \
    URL_OZON_STOCKS_ON_WAREHOUSES, \
    URL_OZON_PRICES_INFO,\
    URL_OZON_STOCKS_BY_WAREHOUSE_FBS,\
    URL_OZON_PRODUCT_INFO_LIST, \
    SLEEP_TIME


class OzonApi:

    def __init__(self, client_id, api_key):
        self.client_id = client_id
        self.api_key = api_key

    def get_headers(self):
        headers = {
            'Client-Id': self.client_id,
            'Api-Key': self.api_key,
            'Content-Type': 'application/json'
                }
        return headers

    def post(self, url, params):
        response = requests.post(url=url, headers=self.get_headers(), json=params, timeout=5)
        if response.status_code == 200:
            logger.info(f'Запрос выполнен успешно Статус код:{response.status_code} URL:{url}')
            return response.json()
        else:
            logger.error(f'Ошибка в выполнении запроса Статус код:{response.status_code} URL:{url}')

    # --- ФУНКЦИИ STOCKS ---
    def get_stocks_fbo(self, all_products: list) -> list:  # /v1/analytics/stock_on_warehouses
        # all_products - список [{'offer_id': ... 'product_id': ..., 'stock_fbo': ..., 'stock_fbs': ... }, .... ]
        NUMBER_OF_RECORDS_PER_PAGE = 1000
        products = []
        count = 0
        total = 0
        while True:
            params = {
                'limit': NUMBER_OF_RECORDS_PER_PAGE,          # кол-во ответов на странице, по умолчанию 100
                'offset': count * NUMBER_OF_RECORDS_PER_PAGE  # количество элементов, которое будет пропущено в ответе
            }
            response = self.post(URL_OZON_STOCKS_ON_WAREHOUSES, params)
            if response and not response.get('code'):
                warehouses = response.get('wh_items')
                total = len(response.get('total_items'))
                for warehouse in warehouses:
                    for product in warehouse['items']:
                        offer_id = product['offer_id']
                        product_id_filter = list(filter(lambda item: item['offer_id'] == offer_id, all_products))
                        product_id = product_id_filter[0]['product_id']
                        products.append(
                            {
                                'warehouse_id': warehouse['id'],
                                'offer_id': offer_id,
                                'product_id': product_id,
                                'stock_fbo': product['stock']['for_sale'],
                                'stock_fbs': 0
                            }
                        )
            time.sleep(SLEEP_TIME)
            count += 1
            if total <= count * NUMBER_OF_RECORDS_PER_PAGE:
                break
        return products
        # формат [{'warehouse_id': ..., 'offer_id': ..., 'product_id': ..., 'stock_fbo': ... , 'stock_fbs': ... }, ...]

    def get_stocks_fbs(self, all_products: list) -> list:  # /v1/product/info/stocks-by-warehouse/fbs
        # получить fbs_sku в ответе методов /v2/product/info (get_product_info) и /v2/product/info/list
        # all_products - список [{'offer_id': ... 'product_id': ..., 'stock_fbo': ..., 'stock_fbs': ... }, .... ]
        offer_ids = [product['offer_id'] for product in all_products]
        fbs_skus = self.get_product_info_list(offer_ids)
        product_list = []
        for i in range(0, len(fbs_skus), 500):
            fbs_skus_chunk = fbs_skus[i: i + 500]  # fbs_skus_chunk - части списка fbs_skus по 500 шт.
            params = {'fbs_sku': fbs_skus_chunk}  # SKU продавца (схемы FBS и rFBS), макс. 500
            response = self.post(URL_OZON_STOCKS_BY_WAREHOUSE_FBS, params)
            if response and not response.get('code'):
                products = response['result']
                for product in products:
                    product_id = str(product['product_id'])
                    offer_id_filter = list(filter(lambda item: item['product_id'] == product_id, all_products))
                    offer_id = offer_id_filter[0]['offer_id']
                    product_list.append(
                        {
                            'warehouse_id': product['warehouse_id'],
                            'offer_id': offer_id,
                            'product_id': product_id,
                            'stock_fbo': 0,
                            'stock_fbs': product['present']
                        }
                    )
            time.sleep(SLEEP_TIME)
        return product_list
        # формат [{'warehouse_id': ..., 'offer_id': ..., 'product_id': ..., 'stock_fbo': ... , 'stock_fbs': ... }, ...]

    def get_stocks_info(self) -> list:  # POST /v3/product/info/stocks (результат попадает в таблицу total_stock)
        NUMBER_OF_RECORDS_PER_PAGE = 1000
        last_id = ''
        product_list = []
        count = 0
        total = 0
        while True:
            params = {
                'filter': {'offer_id': [], 'product_id': [], 'visibility': 'ALL'},
                'last_id': last_id,
                'limit': NUMBER_OF_RECORDS_PER_PAGE  # количество значений на странице, мин. — 1, макс. — 1000
                    }
            response = self.post(URL_OZON_STOCKS_INFO, params)
            if response:
                products = response['result']['items']
                last_id = response['result']['last_id']
                total = response['result']['total']
                for product in products:
                    stock_fbo = 0
                    stock_fbs = 0
                    for stock in product.get('stocks'):
                        if stock['type'] == 'fbo':
                            stock_fbo = stock['present']
                        if stock['type'] == 'fbs':
                            stock_fbs = stock['present']
                    product_list.append(
                        {
                            'offer_id': product['offer_id'],
                            'product_id': str(product['product_id']),
                            'stock_fbo': stock_fbo,
                            'stock_fbs': stock_fbs
                        }
                    )
            time.sleep(SLEEP_TIME)
            count += 1
            if total <= count * NUMBER_OF_RECORDS_PER_PAGE:
                break
        return product_list
        # список словарей [{'offer_id': ... , 'product_id': ... , 'stock_fbo': ..., 'stock_fbs': ... }, .... ]

    # --- ФУНКЦИИ PRICES ---
    def get_prices(self) -> list:   # POST /v4/product/info/prices
        NUMBER_OF_RECORDS_PER_PAGE = 1000
        last_id = ''
        product_list = []
        count = 0
        total = 0
        while True:
            params = {
                'filter': {'offer_id': [], 'product_id': [], 'visibility': 'ALL'},
                'last_id': last_id,
                'limit': NUMBER_OF_RECORDS_PER_PAGE  # кол-во значений на странице, мин. — 1, макс. — 1000
            }
            response = self.post(URL_OZON_PRICES_INFO, params)
            if response:
                products = response['result']['items']
                last_id = response['result']['last_id']
                total = response['result']['total']
                for product in products:
                    product_list.append({
                                'offer_id': product['offer_id'],
                                'product_id': str(product['product_id']),
                                'price': product['price']['price']  # !!! добавать другие поля, вкл. commissions
                    })
            time.sleep(SLEEP_TIME)
            count += 1
            if total <= count * NUMBER_OF_RECORDS_PER_PAGE:
                break
        return product_list

    def update_prices(self, prices: list) -> list:  # POST /v1/product/import/prices
        params = {'prices': prices}
        return self.post(URL_OZON_PRICES, params)['result']

    def update_stocks_fbs(self, stocks: list) -> list:
        params = {'stocks': stocks}  # список объектов {'offer_id': str, 'product_id': int, 'stock': int}
        return self.post(URL_OZON_STOCKS_FBS, params)

    def update_stocks(self, stocks: list) -> list:
        params = {'stocks': stocks}  # список объектов {'offer_id': str, 'product_id': int, 'stock': int, 'warehouse_id': int}
        return self.post(URL_OZON_STOCKS, params)

    # --- ФУНКЦИИ PRODUCT INFO ---
    def get_product_list(self) -> dict:  # /v2/product/list
        params = {
            'filter': {'offer_id': [], 'product_id': [], 'visibility': 'ALL'},
            'last_id': '',
            'limit': 10
                }
        return self.post(URL_OZON_PRODUCTS, params)['result']['items']

    def get_product_info(self, product_id: int) -> dict:
        params = {
            'offer_id': '',
            'product_id': product_id,
            'sku': 0
                }
        return self.post(URL_OZON_PRODUCT_INFO, params)['result']

    def get_product_info_list(self, offer_ids: list) -> list:  # /v2/product/info/list
        fbs_skus = []
        for i in range(0, len(offer_ids), 1000):
            offer_ids_chunk = offer_ids[i: i + 1000]  # offer_ids_chunk - части списка offer_ids по 1000 шт.
            params = {
                'offer_id': offer_ids_chunk,  # макс. кол-во товаров: 1000
                'product_id': [],
                'sku': []
                    }
            response = self.post(URL_OZON_PRODUCT_INFO_LIST, params)
            if response and not response.get('code'):
                for product in response['result']['items']:
                    for item in product['sources']:
                        if item['source'] == 'fbs' and item['is_enabled']:  # отбираем только fbs_sku
                            fbs_skus.append(item['sku'])
            time.sleep(SLEEP_TIME)
        return fbs_skus

    def get_warehouses(self) -> list:
        return self.post(URL_OZON_WAREHOUSES, {})['result']

    # ПОДГОТОВИТЬ СПИСКИ ДЛЯ ОБНОВЛЕНИЯ ОСТАТКОВ НА ПЛОЩАДКЕ
    def make_update_stocks_list(self, products: list, warehouse_id: str):
        update_stocks_list = []

        for product in products:  # products - список словарей {'offer_id: ....., 'stock': .....}
            offer_id = product['offer_id']
            stock = product['stock']

            # обращение к БД, по внутреннему идентификатору товара (id) найти product_id
            # product_id = run_sql_query('SELECT product_id FROM product_list WHERE id=' + str(product_id))
            update_stocks_list.append({
                'offer_id': offer_id,
                # 'product_id': product_id,
                'stock': stock,
                'warehouse_id': int(warehouse_id)
            })

        return update_stocks_list

    # функция обрабатывает ответ с каждой площадки
    def process_mp_response(self, response: dict, account_id: int, products: list):
        return response
