import requests
from loguru import logger
from MARKETPLACES.sber.config import STOCK_UPDATE_URL, PRICE_UPDATE_URL


class SberApi:

    def __init__(self, api_key: str):
        self.api_key = api_key  # !!! токен передается не в заголовке, а в теле запроса

    def get_headers(self) -> dict:
        headers = {'Content-Type': 'application/json'}
        return headers

    def get(self, url: str, params: dict):
        response = requests.get(url=url, headers=self.get_headers(), params=params)
        if response.ok:  # вместо response.status_code чтобы включить код 201
            return response.json()
        else:
            logger.error(f'Ошибка в выполнении запроса Статус код:{response.status_code} URL:{url}')

    def post(self, url: str, params: dict):
        response = requests.post(url=url, headers=self.get_headers(), data=params)
        if response.ok:
            return response.json()
        else:
            logger.error(f'Ошибка в выполнении запроса Статус код:{response.status_code} URL:{url}')

    def dumps(self, params: dict) -> dict:  # !!! нужна ли эта функция???
        return params
        # return json.dumps(params, ensure_ascii=False)

    # def get_info(self) -> dict:  # нет метода, который дает список товаров
    #     # вставить код
    #     return self.get(URL_SBER_INFO, self.dumps(params))

    def update_stocks(self, stocks: list) -> dict:  # на вход {offer_id / stock}
        stocks = [
            {
                'offerId': product['offer_id'],
                'quantity': product['stock']
            }
            for product in stocks]
        params = {
                    'meta': {},
                    'data': {
                        'token': self.api_key,
                        'stocks': stocks  # список словарей {'offerId': str, 'quantity': int}
                            },
                }
        return self.post(STOCK_UPDATE_URL, self.dumps(params))

    def update_prices(self, prices: list) -> dict:  # на вход {offer_id / price}
        prices = [
            {
                'offerId': product['offer_id'],
                'price': product['price'],
                'isDeleted': False
            }
            for product in prices]
        params = {
                    'meta': {},
                    'data': {
                        'token': self.api_key,
                        'prices': prices  # список словарей {'offerId': str, 'price': int, 'isDeleted': bool}
                            }
                }
        return self.post(PRICE_UPDATE_URL, self.dumps(params))
