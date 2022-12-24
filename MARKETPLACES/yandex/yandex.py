import requests
import json
from datetime import datetime
from loguru import logger
import time
from itertools import zip_longest
from PARSER.config import CHUNK_SIZE, SLEEP_TIME
from shared.db import run_sql_get_product_ids
from MARKETPLACES.yandex.config import \
    BASE_URL, \
    URL_YANDEX_INFO, \
    URL_YANDEX_PRICES, \
    URL_YANDEX_STOCKS, \
    URL_YANDEX_SHOW_PRICES, \
    URL_YANDEX_RECOMMENDED_PRICES


class YandexMarketApi:
    def __init__(self, api_key: str, client_id: str, campaign_id: str):
        self.client_id = client_id
        self.api_key = api_key
        self.campaign_id = campaign_id

    def get_headers(self) -> dict:
        headers = {
            'Authorization': f'OAuth oauth_token={self.api_key}, oauth_client_id={self.client_id}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
                }
        return headers

    def get_url(self, method_url: str) -> str:
        return BASE_URL + self.campaign_id + method_url

    def get(self, url: str, params: dict):
        response = requests.get(url=url, headers=self.get_headers(), params=params)

        # print('headers', self.get_headers())
        # print('url', url)
        # print('data', params)

        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f'Ошибка в выполнении запроса. Статус код:{response.status_code} URL:{url}')

    def post(self, url: str, params: dict):
        response = requests.post(url=url, headers=self.get_headers(), json=params)

        # print('headers', self.get_headers())
        # print('url', url)
        # print('data', params)
        # print('response', response)

        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f'Ошибка в выполнении запроса. Статус код:{response.status_code} URL:{url}')

    def append_product_ids(self, products: list) -> list:  # ИСПОЛЬЗУЕТСЯ ТОЛЬКО ДЛЯ update_prices
        offer_ids = [product['offer_id'] for product in products]
        sql = "SELECT offer_id, product_id FROM product_list WHERE product_id IN (%s)" % str(offer_ids).strip('[]')
        offer_product_ids = run_sql_get_product_ids(sql)
        products = sorted(products, key=lambda item: item['offer_id'])
        offer_product_ids = sorted(offer_product_ids, key=lambda item: item['offer_id'])
        products = [{**k, **v} for k, v in zip_longest(products, offer_product_ids, fillvalue={'product_id': None})]
        return products

    def get_dict_value(self, dictionary: dict, key1: str, key2: str):
        try:
            if key1 and key2:
                value = dictionary[key1][key2]
            elif key1 and not key2:
                value = dictionary[key1]
            else:
                value = None
        except KeyError:
            value = None
        return value

    def get_info(self) -> list:  # GET /campaigns/{campaignId}/offer-mapping-entries (список товаров)
        NUMBER_OF_RECORDS_PER_PAGE = 200
        page_token = ''
        count = 0
        products = []
        while True:
            params = {
                'campaignId': self.campaign_id,
                'limit': NUMBER_OF_RECORDS_PER_PAGE,  # кол-во товаров на странице, макс. 200
                'page_token': page_token  # идентификатор страницы c результатами, передавать nextPageToken
            }
            response = self.get(self.get_url(URL_YANDEX_INFO), params)
            if not response:
                break
            if response.get('status') == 'OK':
                products += [
                        {
                            'offer_id': self.get_dict_value(product, 'offer', 'shopSku'),
                            'product_id': self.get_dict_value(product, 'mapping', 'marketSku'),
                            'name': self.get_dict_value(product, 'offer', 'name')  # !!! ВОЗМОЖНО ДОБАВИТЬ ПОЛЯ
                        }
                        for product in response['result']['offerMappingEntries']
                ]
                page_token = response['result']['paging'].get('nextPageToken')
            time.sleep(SLEEP_TIME)
            count += 1
            if count * NUMBER_OF_RECORDS_PER_PAGE % CHUNK_SIZE == 0:
                yield products
                products.clear()
            if not page_token:
                if products:
                    yield products
                break

    def get_stocks(self, shop_skus: list):  # POST /stats/skus (остатки по складам FBY)
        products = []
        sales_percents = []  # список словарей offer_id, sales_percent
        for i in range(0, len(shop_skus), 500):
            shop_skus_chunk = shop_skus[i: i + 500]  # shop_skus_chunk - части списка skus по 500 шт.
            params = {
                'campaignId': self.campaign_id,
                'shopSkus': shop_skus_chunk  # список идент. магазина SKU, макс. 500, обязательный параметр(!)
            }
            response = self.post(self.get_url(URL_YANDEX_STOCKS), params)
            if not response:
                continue
            if response.get('status') == 'OK':
                for product in response['result']['shopSkus']:

                    # --- ДОБАВЛЯЕМ sales_percent ----------------------------------------
                    sales_percents.append(
                        {
                            'offer_id': product['shopSku'],
                            # 'product_id': str(product['marketSku']),
                            'sales_percent': list(filter(lambda x: x['type'] == 'FEE', product['tariffs']))[0]['percent']
                        }
                    )

                    for warehouse in product.get('warehouses', []):
                        products.append(
                            {
                                'warehouse_id': warehouse['id'],
                                'warehouse_name': warehouse['name'],
                                'offer_id': product.get('shopSku'),
                                'product_id': str(product.get('marketSku')),  # ошибка KeyError 15/11/2022
                                'fbo_present': sum(item['count'] for item in warehouse['stocks'] if item['type'] == 'AVAILABLE'),
                                'fbs_present': 0  # для ЯМ записываем только остатки FBY
                            }
                        )
        return products, sales_percents
        # список словарей {'warehouse_id':..., 'offer_id':..., 'product_id':..., 'fbo_present':..., 'fbs_present':... }

    # --- ФУНКЦИЯ PRICES ---
    def get_prices(self) -> list:  # GET /offer-prices
        NUMBER_OF_RECORDS_PER_PAGE = 2000
        page_token = ''
        count = 0
        products = []
        while True:
            params = {
                'campaignId': self.campaign_id,
                'page_token': page_token,
                'limit': NUMBER_OF_RECORDS_PER_PAGE  # кол-во записей, макс. 2000
            }
            response = self.get(self.get_url(URL_YANDEX_SHOW_PRICES), params)
            if not response:
                break
            if response.get('status') == 'OK':
                result = response['result']
                products += [
                    {
                        'product_id': str(product.get('marketSku')),
                        'price': self.get_dict_value(product, 'price', 'value')
                    }
                    for product in result['offers']]
                page_token = self.get_dict_value(result, 'paging', 'nextPageToken')
            time.sleep(SLEEP_TIME)
            count += 1
            if count * NUMBER_OF_RECORDS_PER_PAGE % CHUNK_SIZE == 0:
                yield products
                products.clear()
            if not page_token:
                if products:
                    yield products
                break

    # !!! НОВАЯ ФУНКЦИЯ (ЗАГРУЖАЕТ РЕКОММЕНДОВАННЫЕ ЦЕНЫ)  добавлена 15.12.22
    def get_recommended_prices(self, market_skus: list) -> list:  # GET /offer-prices/suggestions
        MAX_NUMBER_OF_PRODUCTS = 1000
        products = []

        # ------  REMOVE DUPLICATES FROM market_skus ---------
        seen = set()
        new_market_skus = []
        for d in market_skus:
            t = tuple(d.items())
            if t not in seen:
                seen.add(t)
                new_market_skus.append(d)
        market_skus = new_market_skus

        for i in range(0, len(market_skus), MAX_NUMBER_OF_PRODUCTS):
            market_skus_chunk = market_skus[i: i + MAX_NUMBER_OF_PRODUCTS]
            params = {'offers': market_skus_chunk}
            response = self.post(self.get_url(URL_YANDEX_RECOMMENDED_PRICES), params)
            if not response:
                break
            if response.get('status') == 'OK':
                result = response['result']
                for product in result['offers']:
                    recommended_price = None  # если нет цены BUYBOX, оставляем поле recommended_price пустым
                    for item in product['priceSuggestion']:
                        if item['type'] == 'BUYBOX':
                            recommended_price = item['price']
                            break
                    products.append({'product_id': str(product.get('marketSku')), 'recommended_price': recommended_price})
            time.sleep(SLEEP_TIME)
        return products

    # --- ФУНКЦИИ UPDATE (API STOCKS/PRICES) ---
    def update_prices(self, prices: list) -> list:  # POST /offer-prices/updates
        # prices = self.append_product_ids(prices)
        products = []
        for product in prices:
            products.append(
                {
                    'marketSku': product['product_id'],
                    'price': {
                        'currencyId': 'RUR',
                        'value': product['price'],
                        # 'discountBase': product['price'] * 1.1,
                        # 'vat': 7
                        }
                }
            )
        params = {'offers': products}
        return self.post(self.get_url(URL_YANDEX_PRICES), params)

    def make_update_stocks_list(self, products: list, warehouse_id: str):
        update_stocks_list = []
        for product in products:  # products - список словарей {'offer_id: ....., 'stock': .....}
            offer_id = product['offer_id']
            stock = product['stock']
            updated_at = datetime.now().astimezone().replace(microsecond=0).isoformat()  # дата формирования ответа
            update_stocks_list.append({
                    'offer_id': offer_id,
                    'stock': stock,
                    'warehouse_id': warehouse_id,
                    'updated_at': updated_at
                })
        # запись в json файл, чтобы ЯМ мог потом считать остатки через API
        file = open('API/ym_data.json', 'a', encoding='utf-8')
        json.dump(update_stocks_list, file, indent=4)
        file.close()
        return update_stocks_list

    def process_mp_response(self, response: dict, account_id: int, products: list):
        processed_response = []
        return processed_response
