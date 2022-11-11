import requests
import time
from loguru import logger
from PARSER.config import CHUNK_SIZE, SLEEP_TIME
from .config import \
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
    URL_OZON_PRODUCT_INFO_LIST


def change_to_float(var: str):
    if var == '':
        return None
    else:
        return float(var)


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
        response = requests.post(url=url, headers=self.get_headers(), json=params, timeout=10)
        if response.status_code == 200:
            # logger.info(f'Запрос выполнен успешно Статус код:{response.status_code} URL:{url}')
            return response.json()
        else:
            logger.error(f'Ошибка в выполнении запроса Статус код:{response.status_code} URL:{url}')

    def append_product_id(self, products: list) -> list:
        offer_ids = [product['offer_id'] for product in products]
        unique_offer_ids = list(set(offer_ids))
        offer_product_ids = []
        for i in range(0, len(unique_offer_ids), 1000):  # макс. длинна списка для поиска в методе # /v2/product/list
            offer_ids_chunk = unique_offer_ids[i: i + 1000]
            offer_product_ids_generator = self.get_product_list(offer_ids_chunk, [])
            offer_product_ids_chunk = next(offer_product_ids_generator)
            for product in offer_product_ids_chunk:
                for offer_id in offer_ids:
                    if offer_id == product['offer_id']:
                        offer_product_ids.append({'offer_id': offer_id, 'product_id': product['product_id']})
        # сортировка списков словарей по offer_id
        products = sorted(products, key=lambda item: item['offer_id'])
        offer_product_ids = sorted(offer_product_ids, key=lambda item: item['offer_id'])
        # объединяем два списка словарей по ключу offer_id
        products = [{**product, **offer_product_id} for product, offer_product_id in zip(products, offer_product_ids)]
        # изменить тип product_id с int на str (для записи в БД)
        products = [{key: (str(value) if key == 'product_id' else value) for key, value in product.items()}
                    for product in products]
        return products

    def append_offer_id(self, products: list) -> list:
        product_ids = [product['product_id'] for product in products]
        offer_product_ids = []
        for i in range(0, len(product_ids), 1000):  # макс. длинна списка для поиска в методе # /v2/product/list
            product_ids_chunk = product_ids[i: i + 1000]
            offer_product_ids_generator = self.get_product_list([], product_ids_chunk)
            offer_product_ids_chunk = next(offer_product_ids_generator)
            offer_product_ids += offer_product_ids_chunk
        # сортировка списков словарей по product_id
        products = sorted(products, key=lambda item: item['product_id'])
        offer_product_ids = sorted(offer_product_ids, key=lambda item: item['product_id'])
        # объединяем два списка словарей по ключу product_id
        products = [{**product, **offer_product_id} for product, offer_product_id in zip(products, offer_product_ids)]
        # изменить тип product_id с int на str (для записи в БД)
        products = [{key: (str(value) if key == 'product_id' else value) for key, value in product.items()}
                    for product in products]
        return products

    # --- ФУНКЦИИ STOCKS ---
    def get_stocks_fbo(self) -> list:  # /v1/analytics/stock_on_warehouses
        NUMBER_OF_RECORDS_PER_PAGE = 100
        products = []
        count = 0
        while True:
            params = {
                'limit': NUMBER_OF_RECORDS_PER_PAGE,          # кол-во ответов на странице, по умолчанию 100
                'offset': count * NUMBER_OF_RECORDS_PER_PAGE  # количество элементов, которое будет пропущено в ответе
            }
            response = self.post(URL_OZON_STOCKS_ON_WAREHOUSES, params)
            if response.get('wh_items'):
                for warehouse in response['wh_items']:
                    for product in warehouse['items']:
                        products.append(
                            {
                                'warehouse_id': warehouse['id'],
                                'warehouse_name': warehouse['name'],
                                'offer_id': product['offer_id'],
                                'fbo_present': product['stock']['for_sale'],
                                'fbs_present': 0
                            }
                        )
            else:
                if products:
                    products = self.append_product_id(products)
                yield products
                break
            time.sleep(SLEEP_TIME)
            count += 1
            if count * NUMBER_OF_RECORDS_PER_PAGE % CHUNK_SIZE == 0:
                products = self.append_product_id(products)
                yield products
                products.clear()

    def get_stocks_fbs(self, fbs_skus: list) -> list:  # /v1/product/info/stocks-by-warehouse/fbs
        # получить fbs_sku в ответе методов /v2/product/info (get_product_info) и /v2/product/info/list
        NUMBER_OF_SEARCH_ENTRIES = 500
        products = []
        for i in range(0, len(fbs_skus), NUMBER_OF_SEARCH_ENTRIES):
            fbs_skus_chunk = fbs_skus[i: i + NUMBER_OF_SEARCH_ENTRIES]
            params = {'fbs_sku': fbs_skus_chunk}  # SKU продавца (схемы FBS и rFBS), макс. 500
            response = self.post(URL_OZON_STOCKS_BY_WAREHOUSE_FBS, params)
            if response:
                products += [
                    {
                        'warehouse_id': product['warehouse_id'],
                        'product_id': product['product_id'],
                        'fbo_present': 0,
                        'fbs_present': product['present']
                    }
                    for product in response['result']]
            time.sleep(SLEEP_TIME)
        products = self.append_offer_id(products)
        return products

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
                    fbo_present = 0
                    fbs_present = 0
                    for stock in product.get('stocks'):
                        if stock['type'] == 'fbo':
                            fbo_present = stock['present']
                        if stock['type'] == 'fbs':
                            fbs_present = stock['present']
                    product_list.append(
                        {
                            'offer_id': product['offer_id'],
                            'product_id': str(product['product_id']),
                            'fbo_present': fbo_present,
                            'fbs_present': fbs_present
                        }
                    )
            time.sleep(SLEEP_TIME)
            count += 1
            if count * NUMBER_OF_RECORDS_PER_PAGE % CHUNK_SIZE == 0:
                yield product_list
                product_list.clear()
            if total <= count * NUMBER_OF_RECORDS_PER_PAGE:
                if product_list:
                    yield product_list
                break

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
                                # price
                                'price': change_to_float(product['price']['price']),
                                'old_price': change_to_float(product['price']['old_price']),
                                'premium_price': change_to_float(product['price']['premium_price']),
                                'recommended_price': change_to_float(product['price']['premium_price']),
                                'retail_price': change_to_float(product['price']['retail_price']),
                                'vat': change_to_float(product['price']['vat']),
                                'min_ozon_price': change_to_float(product['price']['min_ozon_price']),
                                'marketing_price': change_to_float(product['price']['marketing_price']),
                                'marketing_seller_price': change_to_float(product['price']['marketing_seller_price']),
                                # price index
                                'price_index': change_to_float(product['price_index']),
                                # commissions
                                'sales_percent': product['commissions']['sales_percent'],
                                'fbo_fulfillment_amount': product['commissions']['fbo_fulfillment_amount'],
                                'fbo_direct_flow_trans_min_amount': product['commissions']['fbo_direct_flow_trans_min_amount'],
                                'fbo_direct_flow_trans_max_amount': product['commissions']['fbo_direct_flow_trans_max_amount'],
                                'fbo_deliv_to_customer_amount': product['commissions']['fbo_deliv_to_customer_amount'],
                                'fbo_return_flow_amount': product['commissions']['fbo_return_flow_amount'],
                                'fbo_return_flow_trans_min_amount': product['commissions']['fbo_return_flow_trans_min_amount'],
                                'fbo_return_flow_trans_max_amount': product['commissions']['fbo_return_flow_trans_max_amount'],
                                'fbs_first_mile_min_amount': product['commissions']['fbs_first_mile_min_amount'],
                                'fbs_first_mile_max_amount': product['commissions']['fbs_first_mile_max_amount'],
                                'fbs_direct_flow_trans_min_amount': product['commissions']['fbs_direct_flow_trans_min_amount'],
                                'fbs_direct_flow_trans_max_amount': product['commissions']['fbs_direct_flow_trans_max_amount'],
                                'fbs_deliv_to_customer_amount': product['commissions']['fbs_deliv_to_customer_amount'],
                                'fbs_return_flow_amount': product['commissions']['fbs_return_flow_amount'],
                                'fbs_return_flow_trans_min_amount': product['commissions']['fbs_return_flow_trans_min_amount'],
                                'fbs_return_flow_trans_max_amount': product['commissions']['fbs_return_flow_trans_max_amount'],
                                'volume_weight': product['volume_weight']
                    })
            time.sleep(SLEEP_TIME)
            count += 1
            if count * NUMBER_OF_RECORDS_PER_PAGE % CHUNK_SIZE == 0:
                yield product_list
                product_list.clear()
            if total <= count * NUMBER_OF_RECORDS_PER_PAGE:
                if product_list:
                    yield product_list
                break

    # --- ФУНКЦИИ PRODUCT INFO ---
    def get_product_list(self, offer_ids: list, product_ids: list) -> list:  # /v2/product/list (Список товаров)
        MAX_INTEGER = 9223372036854775807  # макcимальное значение product_id (если превышает, метод выдает ошибку)
        product_ids = [0 if product > MAX_INTEGER else product for product in product_ids]
        NUMBER_OF_RECORDS_PER_PAGE = 1000
        last_id = ''
        total = 0
        count = 0
        products = []
        request_filter = dict()
        request_filter['offer_id'] = offer_ids
        request_filter['product_id'] = product_ids
        request_filter['visibility'] = 'ALL'
        while True:
            params = {'filter': request_filter, 'last_id': last_id, 'limit': NUMBER_OF_RECORDS_PER_PAGE}
            response = self.post(URL_OZON_PRODUCTS, params)
            if response:
                last_id = response['result']['last_id']
                total = response['result']['total']
                products += [
                    {
                        'product_id': product['product_id'],
                        'offer_id': product['offer_id']
                     }
                    for product in response['result']['items']]
                time.sleep(SLEEP_TIME)
                count += 1
                if count * NUMBER_OF_RECORDS_PER_PAGE % CHUNK_SIZE == 0:
                    yield products
                    products.clear()
            if total <= count * NUMBER_OF_RECORDS_PER_PAGE:
                if products:
                    yield products  # список словарей {'product_id': ... , 'offer_id': ...}
                break

    def get_product_info(self, product_id: int) -> dict:  # POST /v2/product/info (Информация о товарах)
        params = {'offer_id': '', 'product_id': product_id, 'sku': 0}
        response = self.post(URL_OZON_PRODUCT_INFO, params)
        product = response['result']
        return product

    def get_product_info_list(self, offer_ids: list, fbs=False) -> list:  # /v2/product/info/list
        NUMBER_OF_SEARCH_ENTRIES = 1000                                   # Получить список товаров по идентификаторам
        products = []
        for i in range(0, len(offer_ids), NUMBER_OF_SEARCH_ENTRIES):  # макс. кол-во товаров в фильтре - 1000
            offer_ids_chunk = offer_ids[i: i + NUMBER_OF_SEARCH_ENTRIES]
            params = {'offer_id': offer_ids_chunk, 'product_id': [], 'sku': []}
            response = self.post(URL_OZON_PRODUCT_INFO_LIST, params)
            if response:
                for product in response['result']['items']:
                    if fbs:  # --- отбираем только товары на складах FBS
                        for source in product['sources']:
                            if source['source'] == 'fbs' and source['is_enabled']:
                                products.append(source['sku'])
                    else:    # --- отбираем все товары
                        fbo_sku, fbs_sku = '', ''
                        if product.get('sources'):
                            fbo_sku = list(filter(lambda item: item['source'] == 'fbo', product['sources']))[0]['sku']
                            fbo_sku = str(fbo_sku)
                            fbs_sku = list(filter(lambda item: item['source'] == 'fbs', product['sources']))[0]['sku']
                            fbs_sku = str(fbs_sku)
                        products.append(
                            {
                                'product_id': product['id'],
                                'name': product['name'],
                                'offer_id': product['offer_id'],
                                'barcode': product['barcode'],
                                'category_id': product['category_id'],
                                'images': product['images'],
                                'created_at': product['created_at'],
                                'vat': product['vat'],
                                'visible': product['visible'],
                                'has_price': product['visibility_details']['has_price'],
                                'has_stock': product['visibility_details']['has_stock'],
                                'active_product': product['visibility_details']['active_product'],
                                'reason': str(product['visibility_details']['reasons']),
                                'price_index': product['price_index'],
                                'images360': str(product['images360']),
                                'color_image': product['color_image'],
                                'primary_image': product['primary_image'],
                                'fbo_sku': fbo_sku,
                                'fbs_sku': fbs_sku,
                            }
                        )
            time.sleep(SLEEP_TIME)
        return products

    def get_warehouses(self) -> list:  # POST /v1/warehouse/list список складов
        warehouses = []
        response = self.post(URL_OZON_WAREHOUSES, {})
        if response:
            for warehouse in response['result']:
                warehouse['wh_type'] = None
                warehouse.pop('status')
                for key, value in warehouse.items():
                    if isinstance(value, bool) or isinstance(value, list):
                        warehouse[key] = str(value)
                    if key == 'first_mile_type':
                        warehouse[key] = value['first_mile_type']
                    if key == 'is_rfbs' and value:
                        warehouse['wh_type'] = 'FBS'
                    else:
                        warehouse['wh_type'] = 'FBO'
        return warehouses

    # --- ФУНКЦИИ UPDATE (API STOCKS/PRICES) ---
    def update_stocks_fbs(self, stocks: list) -> list:
        params = {'stocks': stocks}  # список объектов {'offer_id': str, 'product_id': int, 'stock': int}
        return self.post(URL_OZON_STOCKS_FBS, params)

    def update_stocks(self, stocks: list) -> list:
        params = {
            'stocks': stocks}  # список объектов {'offer_id': str, 'product_id': int, 'stock': int, 'warehouse_id': int}
        return self.post(URL_OZON_STOCKS, params)

    def update_prices(self, prices: list) -> list:  # POST /v1/product/import/prices
        NUMBER_OF_SEARCH_ENTRIES = 1000  # за один запрос можно изменить цены для 1000 товаров
        prices_updated = []
        for i in range(0, len(prices), NUMBER_OF_SEARCH_ENTRIES):
            prices_chunk = prices[i: i + NUMBER_OF_SEARCH_ENTRIES]
            params = {'prices': prices_chunk}
            response = self.post(URL_OZON_PRICES, params)
            prices_updated += response['result']

        # {
        #     "prices": [
        #         {
        #             "auto_action_enabled": "UNKNOWN",
        #             "currency_code": "RUB",
        #             "min_price": "800",
        #             "offer_id": "",
        #             "old_price": "0",
        #             "price": "1448",
        #             "product_id": 1386
        #         }
        #     ]
        # }

        return prices_updated
        # список словарей {"product_id": 1386, "offer_id": "PH8865", "updated": true, "errors": []}

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
