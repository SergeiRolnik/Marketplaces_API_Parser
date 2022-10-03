from API.MARKETPLACES.ozon.ozon import OzonApi
from API.MARKETPLACES.wb.wb import WildberriesApi
from API.MARKETPLACES.yandex.yandex import YandexMarketApi
from API.MARKETPLACES.sber.sber import SberApi
import concurrent.futures
from loguru import logger
from db import run_sql, run_sql_account_list, run_sql_get_offer_ids
from datetime import date
from config import TEST_ACCOUNTS


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
    today = str(date.today())
    for product in products:
        product['account_id'] = account_id
        product['date'] = today
        product['api_id'] = api_id
    return products


def insert_into_db(table_name: str, products: list):
    fields = ','.join(list(products[0].keys()))
    fields = fields.replace('stock_fbo', 'fbo_present')
    fields = fields.replace('stock_fbs', 'fbs_present')
    values = ','.join([f'%({value})s' for value in list(products[0].keys())])
    sql = f'INSERT INTO {table_name} ({fields}) VALUES ({values})'
    run_sql(sql, products)


# добавить к списку offer_id (для ЯМ и ВБ), на вход список словарей {'product_id':.., 'price': ...}
def append_offer_ids(products: list) -> list:
    product_ids = [product['product_id'] for product in products]
    sql = "SELECT offer_id, product_id FROM stock_by_wh WHERE product_id IN (%s)" % str(product_ids).strip('[]')
    offer_product_ids = run_sql_get_offer_ids(sql)
    products = sorted(products, key=lambda item: item['product_id'])
    offer_product_ids = sorted(offer_product_ids, key=lambda item: item['product_id'])
    # объединяем два списка словарей по ключу product_id
    products = [{**product, **offer_product_id} for product, offer_product_id in zip(products, offer_product_ids)]
    return products


def process_account_data(account_id: int):
    sql = 'SELECT mp_id, client_id_api, api_key, campaigns_id FROM account_list WHERE id=%s'
    result = run_sql_account_list(sql, (str(account_id),))
    mp_id, client_id, api_key, campaign_id = result[0]
    mp_object = create_mp_object(mp_id, client_id, api_key, campaign_id)
    print('В обработке account_id:', account_id, 'mp_id:', mp_id)

    if mp_id == 1:  # -------------------------------------- ОЗОН ----------------------------------------

        # --- ALL PRODUCTS --- (данные для таблицы total_stock)
        for stocks_chunk in mp_object.get_stocks_info():
            stocks_chunk = append_cols(stocks_chunk, account_id, api_key)
            insert_into_db('total_stock', stocks_chunk)

            # --- STOCKS FBS ---
            offer_ids = [product['offer_id'] for product in stocks_chunk]
            fbs_skus = mp_object.get_product_info_list(offer_ids)

            products_fbs = mp_object.get_stocks_fbs(fbs_skus)
            products_fbs = append_cols(products_fbs, account_id, api_key)
            insert_into_db('stock_by_wh', products_fbs)

        # --- STOCKS FBO ---
        for products_fbo_chunk in mp_object.get_stocks_fbo():
            products_fbo_chunk = append_cols(products_fbo_chunk, account_id, api_key)
            insert_into_db('stock_by_wh', products_fbo_chunk)

        # --- PRICES ---
        for prices_chunk in mp_object.get_prices():
            prices_chunk = append_cols(prices_chunk, account_id, api_key)
            insert_into_db('price_table', prices_chunk)

    elif mp_id == 2:  # ------------------------ ЯМ ------------------------------------------------------------

        # --- STOCKS ---
        for shop_skus_chunk in mp_object.get_info():
            products = mp_object.get_stocks(shop_skus_chunk)
            products = append_cols(products, account_id, api_key)
            insert_into_db('stock_by_wh', products)

        # --- PRICES ---
        for prices_chunk in mp_object.get_prices():
            prices_chunk = append_offer_ids(prices_chunk)  # находим offer_id по product_id в таблице stock_by_wh
            prices_chunk = append_cols(prices_chunk, account_id, api_key)
            insert_into_db('price_table', prices_chunk)

    elif mp_id == 3:  # ---------------------------------- ВБ --------------------------------------------------

        # --- STOCKS FBO ---
        for products_fbo_chunk in mp_object.get_stocks_fbo():
            products_fbo_chunk = append_cols(products_fbo_chunk, account_id, api_key)
            insert_into_db('stock_by_wh', products_fbo_chunk)

        # --- STOCKS FBS / PRICES FBS (ИСПОЛЬЗУЕТСЯ ОДИН И ТОТ ЖЕ МЕТОД)
        for products_fbs_chunk in mp_object.get_stocks_fbs():

            # --- STOCKS ---
            products_fbs_stocks = [
                {
                    'warehouse_id': product['warehouse_id'],
                    'offer_id': product['offer_id'],
                    'product_id': product['product_id'],
                    'stock_fbo': product['stock_fbo'],
                    'stock_fbs': product['stock_fbs']
                }
                for product in products_fbs_chunk
            ]
            products_fbs_stocks = append_cols(products_fbs_stocks, account_id, api_key)
            insert_into_db('stock_by_wh', products_fbs_stocks)

            # --- PRICES ---
            prices_fbs = [
                {
                    'offer_id': product['offer_id'],
                    'product_id': product['product_id'],
                    'price': product['price']
                }
                for product in products_fbs_chunk
            ]
            prices_fbs = append_cols(prices_fbs, account_id, api_key)
            insert_into_db('price_table', prices_fbs)

        # --- PRICES FBO ---
        for prices_fbo in mp_object.get_prices():
            prices_fbo = append_offer_ids(prices_fbo)  # находим offer_id по product_id в таблице stock_by_wh
            prices_fbo = append_cols(prices_fbo, account_id, api_key)
            if prices_fbo:
                insert_into_db('price_table', prices_fbo)  # !!! ПРОВЕРИТЬ ПОЧЕМУ НЕ ПОДГРУЖАЮТСЯ offer_id

    return {'account_id': account_id, 'result': 'OK'}


def main():
    logger.remove()
    logger.add(sink='logfile.log', format="{time} {level} {message}", level="INFO")

    sql = 'SELECT id FROM marketplaces_list'
    result = run_sql_account_list(sql, ())
    mp_ids = [item[0] for item in result]
    unique_fields = {  # поля в таблице account_list по которым проводится фильтрация дупликатов
        1: 'client_id_api, api_key',  # Озон
        2: 'client_id_api, api_key, campaigns_id',  # ЯМ
        3: 'client_id_api, api_key'  # ВБ
    }
    mp_ids = list(set(mp_ids) & set(list(unique_fields.keys())))  # отбираем только те МП, где указаны уникальные поля

    accounts = []
    for mp_id in mp_ids:  # проходим по всем аккаунтам и выбираем только уникальные значение client_id_api, api_key
        sql = f'SELECT MIN(id) FROM account_list WHERE mp_id={mp_id} GROUP BY {unique_fields[mp_id]}'
        result = run_sql_account_list(sql, ())
        mp_accounts = [item[0] for item in result]
        accounts += mp_accounts

    if TEST_ACCOUNTS:  # список номеров аккаунтов в таблице account_list для тестирования (указать в config.py)
        accounts = TEST_ACCOUNTS

    response = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        results = [executor.submit(process_account_data, account) for account in accounts]
        for result in results:
            response.append(result.result())
    print('message', response)
    return response


if __name__ == '__main__':
    main()
