import requests
import json
from datetime import datetime
from loguru import logger
import time
from pprint import pprint
from PARSER.config import CHUNK_SIZE, SLEEP_TIME
from MARKETPLACES.yandex.config import \
    BASE_URL, \
    URL_YANDEX_INFO, \
    URL_YANDEX_PRICES, \
    URL_YANDEX_STOCKS, \
    URL_YANDEX_SHOW_PRICES


class YandexMarketApi:
    def __init__(self, api_key: str, client_id: str, campaign_id: str):
        self.client_id = client_id  # в таблице account_list client_id_api and api_key поменяны местами
        self.api_key = api_key      # соответсвенно в __init__ тоже меняем порядок
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
        if response.status_code == 200:
            # logger.info(f'Запрос выполнен успешно. Статус код:{response.status_code} URL:{url}')
            return response.json()
        else:

            print(response.json())  # --- TESTING ----

            logger.error(f'Ошибка в выполнении запроса. Статус код:{response.status_code} URL:{url}')

    def post(self, url: str, params: dict):
        response = requests.post(url=url, headers=self.get_headers(), json=params)
        if response.status_code == 200:
            # logger.info(f'Запрос выполнен успешно. Статус код:{response.status_code} URL:{url}')
            return response.json()
        else:

            print(response.json())  # --- TESTING ----

            logger.error(f'Ошибка в выполнении запроса. Статус код:{response.status_code} URL:{url}')

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
        for i in range(0, len(shop_skus), 500):
            shop_skus_chunk = shop_skus[i: i + 500]  # shop_skus_chunk - части списка skus по 500 шт.
            params = {
                'campaignId': self.campaign_id,
                'shopSkus': shop_skus_chunk  # список идент. магазина SKU, макс. 500, обязательный параметр(!)
            }
            response = self.post(self.get_url(URL_YANDEX_STOCKS), params)
            if response and response.get('status') == 'OK':
                for product in response['result']['shopSkus']:
                    for warehouse in product.get('warehouses', []):
                        products.append(
                            {
                                'warehouse_id': warehouse['id'],
                                'warehouse_name': warehouse['name'],
                                'offer_id': product['shopSku'],
                                'product_id': str(product['marketSku']),
                                'fbo_present': sum(item['count'] for item in warehouse['stocks'] if item['type'] == 'AVAILABLE'),
                                'fbs_present': 0  # для ЯМ записываем только остатки FBY
                            }
                        )
        return products
        # список словарей {'warehouse_id':..., 'offer_id':..., 'product_id':..., 'stock_fbo':..., 'stock_fbs':... }

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

    def update_prices(self, offers: list) -> list:  # POST /offer-prices/updates
        params = {'offers': offers}
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