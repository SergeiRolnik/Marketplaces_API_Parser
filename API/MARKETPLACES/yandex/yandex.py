import requests
import json
from datetime import datetime
from loguru import logger
import time
from API.MARKETPLACES.yandex.config import \
    BASE_URL, \
    URL_YANDEX_INFO, \
    URL_YANDEX_PRICES, \
    URL_YANDEX_STOCKS, \
    URL_YANDEX_SHOW_PRICES, \
    SLEEP_TIME, \
    CHUNK_SIZE


class YandexMarketApi:
    def __init__(self, client_id: str, api_key: str, campaign_id: str):
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
        if response.status_code == 200:
            logger.info(f'Запрос выполнен успешно Статус код:{response.status_code} URL:{url}')
            return response.json()
        else:
            logger.error(f'Ошибка в выполнении запроса Статус код:{response.status_code} URL:{url}')

    def post(self, url: str, params: dict):
        response = requests.post(url=url, headers=self.get_headers(), json=params)
        if response.status_code == 200:
            logger.info(f'Запрос выполнен успешно Статус код:{response.status_code} URL:{url}')
            return response.json()
        else:
            logger.error(f'Ошибка в выполнении запроса Статус код:{response.status_code} URL:{url}')

    def get_info(self) -> list:  # GET /campaigns/{campaignId}/offer-mapping-entries (список товаров)
        NUMBER_OF_RECORDS_PER_PAGE = 200
        page_token = ''
        count = 0
        while True:
            params = {
                'campaignId': self.campaign_id,
                'limit': NUMBER_OF_RECORDS_PER_PAGE,  # кол-во товаров на странице, макс. 200
                'page_token': page_token  # идентификатор страницы c результатами, передавать nextPageToken
            }
            response = self.get(self.get_url(URL_YANDEX_INFO), params)
            if not response or response.get('status') == 'ERROR':
                break
            shop_skus = [product['offer']['shopSku'] for product in response['result']['offerMappingEntries']]
            page_token = response['result']['paging'].get('nextPageToken')
            time.sleep(SLEEP_TIME)
            count += 1
            if count * NUMBER_OF_RECORDS_PER_PAGE == CHUNK_SIZE:
                yield shop_skus
                shop_skus.clear()
            if not page_token:
                if shop_skus:
                    yield shop_skus
                break

    def get_stocks(self, shop_skus: list):  # POST /stats/skus (--- остатки по складам FBY ---)
        product_list = []
        for i in range(0, len(shop_skus), 500):
            shop_skus_chunk = shop_skus[i: i + 500]  # shop_skus_chunk - части списка skus по 500 шт.
            params = {
                'campaignId': self.campaign_id,
                'shopSkus': shop_skus_chunk  # список идент. магазина SKU, макс. 500, обяз. параметр, д.б. хотя бы один
            }
            response = self.post(self.get_url(URL_YANDEX_STOCKS), params)
            if response:
                products = response['result'].get('shopSkus')
                for product in products:
                    warehouses = product.get('warehouses')
                    if warehouses:  # если указаны склады
                        for warehouse in warehouses:
                            product_list.append({
                                'warehouse_id': warehouse['id'],
                                'offer_id': product['shopSku'],
                                'product_id': str(product['marketSku']),
                                'stock_fbo':
                                    sum(item['count'] for item in warehouse['stocks'] if item['type'] == 'AVAILABLE'),
                                'stock_fbs': 0  # для ЯМ записываем только остатки FBY
                            })
        return product_list
        # формат [{'warehouse_id': ..., 'offer_id': ..., 'product_id': ..., 'stock_fbo': ..., 'stock_fbs': ... }, ...]

    # --- ФУНКЦИЯ PRICES ---
    def get_prices(self) -> list:  # GET /offer-prices
        NUMBER_OF_RECORDS_PER_PAGE = 2000
        page_token = ''
        product_list = []
        count = 0
        while True:
            params = {
                'campaignId': self.campaign_id,
                'page_token': page_token,
                'limit': NUMBER_OF_RECORDS_PER_PAGE  # кол-во записей, макс. 2000
            }
            response = self.get(self.get_url(URL_YANDEX_SHOW_PRICES), params)
            if not response or response.get('status') == 'ERROR':
                break
            products = response['result']['offers']
            for product in products:
                product_list.append({
                    'offer_id': '',  # !!! надо вычислять offer_id (shopSku) по marketSku
                    'product_id': str(product.get('marketSku')),  # без get выскакивают ошибки
                    'price': product['price'].get('value')   # без get выскакивают ошибки
                })
            page_token = response['result']['paging'].get('nextPageToken')
            count += 1
            time.sleep(SLEEP_TIME)
            if count * NUMBER_OF_RECORDS_PER_PAGE == CHUNK_SIZE:
                yield product_list
                product_list.clear()
            if not page_token:
                if product_list:
                    yield product_list
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
