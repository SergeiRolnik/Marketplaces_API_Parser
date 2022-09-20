from API.MARKETPLACES.ozon.ozon import OzonApi
from API.MARKETPLACES.wb.wb import WildberriesApi
from API.MARKETPLACES.yandex.yandex import YandexMarketApi
from API.MARKETPLACES.sber.sber import SberApi
import concurrent.futures
from loguru import logger
from db import run_sql, run_sql_account_list
from datetime import date


def create_mp_object(mp_id: int, client_id: str, api_key: str, campaign_id: str):
    if mp_id == 1:
        return OzonApi(client_id, api_key)
    elif mp_id == 2:
        return YandexMarketApi(client_id, api_key, campaign_id)
    elif mp_id == 3:
        return WildberriesApi(client_id, api_key)
    elif mp_id == 4:
        return SberApi(api_key)


def append_cols(products: list, account_id: int, api_id: str):  # добавить account_id, api_id и дату к списку товаров
    for product in products:
        product['account_id'] = account_id
        product['date'] = str(date.today())
        product['api_id'] = api_id
    return products


def process_account_data(account_id: int):
    sql = 'SELECT mp_id, client_id_api, api_key, campaigns_id FROM account_list WHERE id=%s'
    result = run_sql_account_list(sql, (str(account_id),))
    mp_id, client_id, api_key, campaign_id = result[0]
    mp_object = create_mp_object(mp_id, client_id, api_key, campaign_id)

    # --------------------------------------- STOCKS ------------------------------------------------------
    # отправляем запрос в API площадки, получаем список словарей в формате:
    # [{'warehouse_id': ..., 'offer_id': ..., 'product_id': ..., 'stock_fbo': ... , 'stock_fbs': ... }, ...]
    if mp_id == 1:  # ОЗОН
        all_products = mp_object.get_stocks_info()
        # список словарей [{'offer_id': ... , 'product_id': ... , 'stock_fbo': ..., 'stock_fbs': ... }, .... ]
        all_products_values = append_cols(all_products, account_id, api_key)
        sql = 'INSERT INTO ' \
              'total_stock (offer_id, product_id, fbo_present, fbs_present, account_id, api_id, date) ' \
              'VALUES (%(offer_id)s, %(product_id)s, %(stock_fbo)s, %(stock_fbs)s, %(account_id)s, %(api_id)s, %(date)s)'
        run_sql(sql, all_products_values)
        products = mp_object.get_stocks_fbo(all_products) + \
                   mp_object.get_stocks_fbs(all_products)
        products = append_cols(products, account_id, api_key)
    elif mp_id == 2:  # ЯМ
        products = mp_object.get_stocks()
        products = append_cols(products, account_id, api_key)
    elif mp_id == 3:  # ВБ
        products_fbo = mp_object.get_stocks_fbo()
        products_fbs = mp_object.get_stocks_fbs()  # ниже используется также для получения цен
        products_fbs_stocks = [  # выбираем нужные поля
            {
                'warehouse_id': product['warehouse_id'],
                'offer_id': product['offer_id'],
                'product_id': product['product_id'],
                'stock_fbo': product['stock_fbo'],
                'stock_fbs': product['stock_fbs']
            }
            for product in products_fbs
        ]
        products = append_cols(products_fbo, account_id, client_id) + \
                   append_cols(products_fbs_stocks, account_id, api_key)
    sql = 'INSERT INTO ' \
          'stock_by_wh (warehouse_id, offer_id, product_id, fbo_present, fbs_present, account_id, api_id, date) ' \
          'VALUES (%(warehouse_id)s, %(offer_id)s, %(product_id)s, %(stock_fbo)s, %(stock_fbs)s, %(account_id)s, %(api_id)s, %(date)s)'
    run_sql(sql, products)

    # ------------------------------------------ PRICES ------------------------------------------------
    # отправляем запрос в API площадки, получаем список словарей в формате:
    # [{'offer_id': ..., 'product_id': ..., 'price': ... }, ...]
    products = mp_object.get_prices()
    if mp_id == 3:  # для ВБ дополнительно взять цены из get_stocks_fbs()
        products_fbs_prices = [  # выбираем нужные поля
            {
                'offer_id': product['offer_id'],
                'product_id': product['product_id'],
                'price': product['price']
            }
            for product in products_fbs
        ]
        products = append_cols(products, account_id, client_id) + \
                   append_cols(products_fbs_prices, account_id, api_key)

    elif mp_id == 1 or 2:
        products = append_cols(products, account_id, api_key)

    # --- TESTING ---
    products = products[1:10]

    sql = 'INSERT INTO ' \
          'price_table (offer_id, product_id, price, account_id, api_id, date) ' \
          'VALUES (%(offer_id)s, %(product_id)s, %(price)s, %(account_id)s, %(api_id)s, %(date)s)'
    run_sql(sql, products)
    return {'account_id': account_id, 'result': 'OK'}  # !!! что выводить как результат выполнения функции?


def main():
    logger.remove()
    logger.add(sink='logfile.log', format="{time} {level} {message}", level="INFO")

    sql = 'SELECT * FROM account_list'  # цикл по всем аккаунтам
    accounts = run_sql_account_list(sql, ())
    accounts = [account[0] for account in accounts]  # список номеров аккаунтов (account_id)

    # для теста
    accounts = [1]  # Озон
    # accounts = [3]  # ВБ

    response = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        results = [executor.submit(process_account_data, account) for account in accounts]
        for result in results:
            response.append(result.result())

    print('message', response)

    return response


if __name__ == '__main__':
    main()
