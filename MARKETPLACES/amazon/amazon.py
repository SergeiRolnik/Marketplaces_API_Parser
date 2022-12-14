import requests
import time
from loguru import logger
from PARSER.config import SLEEP_TIME
from MARKETPLACES.amazon.config import PRODUCT_PRICING_URL, FBA_INVENTORY_URL, MERCHANT_FULFILLMENT_URL


class AmazonApi:

    def __init__(self, marketplace_id, api_key):
        self.marketplace_id = marketplace_id
        self.api_key = api_key

    def get_headers(self):  # !!! возможно переписать в зависимости от способа авторизации
        headers = {
            'Api-Key': self.api_key,
            'Content-Type': 'application/json'
                }
        return headers

    def post(self, url, params):
        response = requests.post(url=url, headers=self.get_headers(), data=params)
        if response.ok:
            return response.json()
        else:
            logger.error(f'Ошибка в выполнении запроса Статус код:{response.status_code} URL:{url}')

    def get(self, url, params):
        response = requests.get(url=url, headers=self.get_headers(), params=params)
        if response.ok:
            return response.json()
        else:
            logger.error(f'Ошибка в выполнении запроса Статус код:{response.status_code} URL:{url}')

    # --- GET PRICES ---
    def get_prices(self, asins: list) -> list:  # GET /product-pricing-api-v0-use-case-guide
        NUMBER_OF_SEARCH_ENTRIES = 20  # accepts a list of up to 20 SKUs or ASINs as a query parameter
        products = []
        for i in range(0, len(asins), NUMBER_OF_SEARCH_ENTRIES):
            asins_chunk = asins[i: i + NUMBER_OF_SEARCH_ENTRIES]
            params = {
                'MarketplaceId': self.marketplace_id,  # (*) Marketplace id. Specifies the mp for which prices are returned
                'Asins': asins_chunk,  # A list of up to 20 Amazon Standard Identification Number (ASIN) values
                'Skus': [],  # A list of up to 20 seller SKU values used to identify items in the given marketplace
                'ItemType': 'Asin',   # (*) Indicates whether ASIN values or seller SKU values are used to identify items
                'ItemCondition': '',  # Filters the offer listings based on item condition. Possible values: New, Used, Collectible, Refurbished, Club.
                # 'CustomerType': 'Consumer',  # Indicates whether to request pricing from consumer or business buyers
                'OfferType': 'B2C'  # Indicates whether to request pricing info for the seller's B2C or B2B offers
                # defaults: CustomerType = Consumer, OfferType = B2C
            }
            response = self.get(PRODUCT_PRICING_URL, params)
            if response:
                products += [
                    {
                        'product_id': product['ASIN'],
                        'price': [item['BuyingPrice']['ListingPrice']
                                  for item in product['Product']['Offers']
                                  if 'BuyingPrice' in item.keys()][0]['Amount']
                        # вставить также CurrencyCode, например, USD ???
                    }
                    for product in response['payload']]
            time.sleep(SLEEP_TIME)
        return products

    # --- GET STOCKS --- (получить остатки по списку номеров sku)
    def get_stocks_skus(self, skus: list, start_date: str) -> list:  # GET /fba/inventory/v1/summaries
        NUMBER_OF_SKUS = 50  # You may specify up to 50 SKUs.
        products = []
        for i in range(0, len(skus), NUMBER_OF_SKUS):
            skus_chunk = skus[i: i + NUMBER_OF_SKUS]
            params = {
                'details': True,  # BOOLEAN: true to return inventory summaries with additional summarized inventory details and quantities. Otherwise, returns inventory summaries only (default value).
                'granularityType': 'Marketplace',  # STRING(*): The granularity type for the inventory aggregation level.
                'granularityId': '',  # STRING(*): The granularity ID for the inventory aggregation level.
                'startDateTime': start_date,  # STRING(DATE/TIME): If specified, all inventory summaries that have changed since then are returned.
                'sellerSkus': skus_chunk,  # ARRAY: A list of seller SKUs for which to return inventory summaries. You may specify up to 50 SKUs.
                'nextToken': '',  # STRING: String token returned in the response of your previous request.
                'marketplaceIds': [self.marketplace_id]  # ARRAY(*): The marketplace ID for the marketplace for which to return inventory summaries.
            }
            response = self.get(FBA_INVENTORY_URL, params)
            if response:
                products += [
                    {
                        'product_id': product['asin'],
                        'stock': product['totalQuantity']
                    }
                    for product in response['payload']['inventorySummaries']]
        return products

    # --- GET STOCKS --- (получить все остатки)
    def get_stocks_all(self, start_date: str) -> list:  # GET /fba/inventory/v1/summaries
        products = []
        next_token = ''
        while True:
            params = {
                'details': True,  # BOOLEAN: true to return inventory summaries with additional summarized inventory details and quantities. Otherwise, returns inventory summaries only (default value).
                'granularityType': 'Marketplace',  # STRING(*): The granularity type for the inventory aggregation level.
                'granularityId': '',  # STRING(*): The granularity ID for the inventory aggregation level.
                'startDateTime': start_date, # STRING(DATE/TIME): If specified, all inventory summaries that have changed since then are returned.
                'sellerSkus': [],  # ARRAY: A list of seller SKUs for which to return inventory summaries. You may specify up to 50 SKUs.
                'nextToken': next_token,  # STRING: String token returned in the response of your previous request.
                'marketplaceIds': [self.marketplace_id]  # ARRAY(*): The marketplace ID for the marketplace for which to return inventory summaries.
            }
            response = self.get(FBA_INVENTORY_URL, params)
            if response:
                products += [
                    {
                        'product_id': product['asin'],
                        'stock': product['totalQuantity']
                    }
                    for product in response['payload']['inventorySummaries']]
                next_token = response['pagination'].get('nextToken')
            if not next_token:
                break
        return products

# Merchant Fulfillment API v0 model
# The Selling Partner API
# for Merchant Fulfillment helps you build applications that let sellers purchase shipping
# for non-Prime and Prime orders using Amazon’s Buy Shipping Services.

    # --- UPDATE PRICES ---
    def update_prices(self) -> list:
        pass

    # --- UPDATE STOCKS ---
    def update_stocks(self) -> list:
        pass




