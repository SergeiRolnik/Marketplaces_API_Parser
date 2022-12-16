import requests
from fake_useragent import UserAgent
from itertools import zip_longest


# имя функции для каждого поставщика указано в БД (таблица suppliers, столбец supplier_func)
def get_products_from_samson_api(api_url, url_stocks, url_prices, api_key):
    ua = UserAgent()
    user_agent = ua.random

    headers = {
      'Accept': 'application/json',
      'User-Agent': user_agent,
      'Accept-Encoding': 'gzip'
    }

    params = {
      'api_key': api_key,
      'pagination_count': '10',
      'pagination_page': '5'
    }

    # --- STOCKS ---
    response = requests.get(url=api_url + url_stocks, params=params, headers=headers)
    stocks = response.json()['data']
    stocks = [{'offer_id': str(product['sku']), 'stock': product['stock_list'][3]['value']} for product in stocks]

    # --- PRICES ---
    response = requests.get(url=api_url + url_prices, params=params, headers=headers)
    prices = response.json()['data']
    prices = [{'offer_id': str(product['sku']), 'price': product['price_list'][0]['value']} for product in prices]

    # склеить stocks и prices по offer_id
    products = [{**keys, **values} for keys, values in
                zip_longest(stocks, prices, fillvalue={'price': None})]  # !!! проверить правильно ли указано fillvalue

    return products  # список словарей {'offer_id':..., 'stock':..., 'price':...}


# имя функции для каждого поставщика указано в БД (таблица suppliers, столбец supplier_func)
def get_products_from_another_supplier_api(url, api_key):
    headers = {
        # здесь свой код
    }

    params = {
        'api_key': api_key
        # здесь свой код
    }

    response = requests.get(url=url, params=params, headers=headers)
    products = response.json()['data']  # заменить на свой код
    # здесь свой код
    return products
