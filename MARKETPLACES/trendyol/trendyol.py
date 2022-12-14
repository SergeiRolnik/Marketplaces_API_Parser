import requests
from loguru import logger
from fake_useragent import UserAgent
from MARKETPLACES.trendyol.config import PRODUCT_INFO_URL, PRICE_AND_STOCK_UPDATE_URL


class TrendyolApi:

    ua = UserAgent()
    user_agent = ua.random

    def __init__(self, api_key: str):
        self.api_key = api_key

    def get_headers(self) -> dict:
        headers = {
            'Authorization': f'Basic {self.api_key}',
            'User-Agent': self.user_agent,
            'Content-Type': 'application/json'
        }
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

    def get_price_and_stock(self):  # https://api.trendyol.com/sapigw/suppliers/{supplierId}/products?**approved=true**
        params = {
            'approved': True,  # The product is used for approved or unapproved control,Must be true for approved products	boolean
            'barcode': '',  # Unique barcode must be sent for inquiry	string
            'startDate': 0,  # It fetches the next products from a specific date-Timestamp.	long
            'endDate': 0,  # Bring a previous date from a specific date - Timestamp.	long
            'page': 0,  # Only return information on the specified page	int
            'dateQueryType': '',  #	Date date filter can work on CREATED DATE or LAST_MODIFIED_DATE	string
            'size': 0,  # Specifies the maximum number to list on a page.	int
            'supplierId': 0,  #	ID information of the relevant supplier should be sent long
            'onSale': True,  # onSale=true must be submitted to list products for sale	boolean
            'rejected': False,  # rejected=true or false must be submitted to list products that rejected	boolean
            'blacklisted': True,  # blacklisted=true or false must be submitted to list products that blacklisted	boolean
            'brandIds': []  # It should be used to list products with the specified brandId	array
        }
        return self.get(PRODUCT_INFO_URL, params)

    def update_price_and_stock(self, products: list) -> dict:  # на вход {offer_id / stock / price}
        items = [
            {
                'barcode': product['offer_id'],
                'quantity': product['stock'],
                'salePrice': product['price'],
                'listPrice': product['price']
            }
            for product in products]
        params = {'items': items}
        return self.post(PRICE_AND_STOCK_UPDATE_URL, params)

