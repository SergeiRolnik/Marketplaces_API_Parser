from MARKETPLACES.ozon.ozon import OzonApi
from MARKETPLACES.wb.wb import WildberriesApi
from MARKETPLACES.yandex.yandex import YandexMarketApi
from MARKETPLACES.sber.sber import SberApi
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


def append_cols_products(products: list, account_id: int, api_id: str):  # добавить account_id, api_id к списку товаров
    for product in products:
        product['account_id'] = account_id
        product['api_id'] = api_id
    return products


def insert_into_db(table_name: str, records: list):
    if records:
        fields = ','.join(list(records[0].keys()))
        fields = fields.replace('reason', 'resason')  # !!! исправить название поля в таблице product_list
        fields = fields.replace('stock_fbo', 'fbo_present')
        fields = fields.replace('stock_fbs', 'fbs_present')
        values = ','.join([f'%({value})s' for value in list(records[0].keys())])
        sql = f'INSERT INTO {table_name} ({fields}) VALUES ({values})'
        run_sql(sql, records)


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


def remove_duplicates(warehouses: list) -> list:
    unique_warehouses = []
    for warehouse in warehouses:
        if warehouse not in unique_warehouses:
            unique_warehouses.append(warehouse)
    return unique_warehouses


def process_account_data(account_id: int):
    sql = 'SELECT mp_id, client_id_api, api_key, campaigns_id FROM account_list WHERE id=%s'
    result = run_sql_account_list(sql, (str(account_id),))
    mp_id, client_id, api_key, campaign_id = result[0]
    mp_object = create_mp_object(mp_id, client_id, api_key, campaign_id)
    print('В обработке account_id:', account_id, 'mp_id:', mp_id)

    if mp_id == 1:  # -------------------------------------- ОЗОН ----------------------------------------

        # --- WAREHOUSES FBS --- !!! проверить почему в данных по складу is_rfbs = false
        warehouses = mp_object.get_warehouses()  # POST /v1/warehouse/list список складов
        insert_into_db('wh_table', warehouses)
        warehouses.clear()

        test = input('OK')

        # --- PRODUCTS ---
        for products_chunk in mp_object.get_product_list([], []):  # /v2/product/list (список всех товаров)
            offer_ids = [product['offer_id'] for product in products_chunk]
            products = mp_object.get_product_info_list(offer_ids, False)  # /v2/product/info/list (подробная информация о товарах по списку offer_id)
            products = append_cols_products(products, account_id, api_key)
            insert_into_db('product_list', products)

        # --- ALL STOCKS --- (данные для таблицы total_stock)
        for stocks_chunk in mp_object.get_stocks_info():  # POST /v3/product/info/stocks
            stocks_chunk = append_cols(stocks_chunk, account_id, api_key)
            insert_into_db('total_stock', stocks_chunk)

            # --- STOCKS FBS ---
            offer_ids = [product['offer_id'] for product in stocks_chunk]
            fbs_skus = mp_object.get_product_info_list(offer_ids, True)  # /v2/product/info/list (отбираем товары по списку offer_ids на складах FBS)
            products_fbs = mp_object.get_stocks_fbs(fbs_skus)  # /v1/product/info/stocks-by-warehouse/fbs
            products_fbs = append_cols(products_fbs, account_id, api_key)
            insert_into_db('stock_by_wh', products_fbs)

        # --- STOCKS FBO ---
        for products_fbo_chunk in mp_object.get_stocks_fbo():  # /v1/analytics/stock_on_warehouses
            products_fbo_chunk = append_cols(products_fbo_chunk, account_id, api_key)
            insert_into_db('stock_by_wh', products_fbo_chunk)

            # --- WAREHOUSES FBO ---
            warehouses_chunk = [
                {
                    'warehouse_id': warehouse['warehouse_id'],
                    'name': warehouse['warehouse_name'],
                    'wh_type': 'FBO',
                    'account_id': account_id
                }
                for warehouse in products_fbo_chunk]
            warehouses += remove_duplicates(warehouses_chunk)
        insert_into_db('wh_table', remove_duplicates(warehouses))

        # --- PRICES ---
        for prices_chunk in mp_object.get_prices():  # POST /v4/product/info/prices
            prices_chunk = append_cols(prices_chunk, account_id, api_key)
            insert_into_db('price_table', prices_chunk)

    elif mp_id == 2:  # ------------------------ ЯМ ------------------------------------------------------------

        warehouses = []
        # --- STOCKS ---
        for products_chunk in mp_object.get_info():  # GET /campaigns/{campaignId}/offer-mapping-entries
            shop_skus_chunk = [product['offer_id'] for product in products_chunk]  # выделяем shopSkus
            products_chunk = append_cols_products(products_chunk, account_id, api_key)
            insert_into_db('product_list', products_chunk)
            products_chunk = mp_object.get_stocks(shop_skus_chunk)  # POST /stats/skus
            products_chunk = append_cols(products_chunk, account_id, api_key)
            insert_into_db('stock_by_wh', products_chunk)

            # --- WAREHOUSES (FBY или FBS?) ---
            warehouses_chunk = [
                {
                    'warehouse_id': warehouse['warehouse_id'],
                    'name': warehouse['warehouse_name'],
                    'wh_type': 'FBY',  # !!! какой тип склада FBY или FBS?
                    'account_id': account_id
                }
                for warehouse in products_chunk]
            warehouses += remove_duplicates(warehouses_chunk)
        insert_into_db('wh_table', remove_duplicates(warehouses))

        # --- PRICES ---
        for prices_chunk in mp_object.get_prices():  # GET /offer-prices
            prices_chunk = append_offer_ids(prices_chunk)
            prices_chunk = append_cols(prices_chunk, account_id, api_key)
            insert_into_db('price_table', prices_chunk)

    elif mp_id == 3:  # ---------------------------------- ВБ --------------------------------------------------

        # --- WAREHOUSES FBO(?) ---
        warehouses = mp_object.get_warehouses()  # /api/v2/warehouses, список словарей {'warehouse_id':..., 'name': ...}
        for warehouse in warehouses:             # метод получает только склады FBO?
            warehouse['wh_type'] = 'FBO'
            warehouse['account_id'] = account_id
        insert_into_db('wh_table', warehouses)

        # --- STOCKS FBO ---
        warehouses_fbo = []
        for products_fbo_chunk in mp_object.get_stocks_fbo():  # GET /api/v2/stocks
            products_fbo_chunk = append_cols(products_fbo_chunk, account_id, api_key)
            insert_into_db('stock_by_wh', products_fbo_chunk)

            # --- PRODUCTS FBO ---
            products = [
                {
                    'product_id': product['product_id'],
                    'offer_id': product['offer_id'],
                    'barcode': product['barcode'],
                    'category_id': product['category'],
                    'name': product['product_name']  # !!! возможно загрузить другие поля
                }
                for product in products_fbo_chunk]
            products = append_cols_products(products, account_id, api_key)
            insert_into_db('product_list', products)

            # --- WAREHOUSES FBO ---
            warehouses_fbo_chunk = [
                {
                    'warehouse_id': product['warehouse_id'],
                    'name': product['warehouse_name'],
                    'wh_type': 'FBO',
                    'account_id': account_id
                }
                for product in products_fbo_chunk]
            warehouses_fbo += remove_duplicates(warehouses_fbo_chunk)
        insert_into_db('wh_table', remove_duplicates(warehouses_fbo))

        # --- STOCKS & PRICES FBS --- (используется один и тот же метод)
        warehouses_fbs = []
        for products_fbs_chunk in mp_object.get_stocks_fbs():   # GET /api/v1/supplier/stocks

            # --- STOCKS ---
            stocks_fbs = [
                {
                    'warehouse_id': product['warehouse_id'],
                    'offer_id': product['offer_id'],
                    'product_id': product['product_id'],
                    'stock_fbo': product['stock_fbo'],
                    'stock_fbs': product['stock_fbs']
                }
                for product in products_fbs_chunk]
            stocks_fbs = append_cols(stocks_fbs, account_id, api_key)
            insert_into_db('stock_by_wh', stocks_fbs)

            # --- PRODUCTS FBS ---
            products = [
                {
                    'product_id': product['product_id'],
                    'offer_id': product['offer_id'],
                    'barcode': product['barcode'],
                    'category_id': product['product_category'],
                    'name': product['product_name']  # !!! возможно загрузить другие поля
                 }
                for product in products_fbs_chunk]
            products = append_cols_products(products, account_id, api_key)
            insert_into_db('product_list', products)

            # --- PRICES FBS ---  !!! дублирует product_id полученные через метод # GET /public/api/v1/info
            prices_fbs = [
                {
                    'offer_id': product['offer_id'],
                    'product_id': product['product_id'],
                    'price': product['price']
                }
                for product in products_fbs_chunk]
            prices_fbs = append_cols(prices_fbs, account_id, api_key)
            insert_into_db('price_table', prices_fbs)

            # --- WAREHOUSES FBS ---
            warehouses_fbs_chunk = [
                {
                    'warehouse_id': product['warehouse_id'],
                    'name': product['warehouse_name'],
                    'wh_type': 'FBS',
                    'account_id': account_id
                }
                for product in products_fbs_chunk]
            warehouses_fbs += remove_duplicates(warehouses_fbs_chunk)
        insert_into_db('wh_table', remove_duplicates(warehouses_fbs))

        # --- PRICES FBO + FBS --- (!!! включает также товары FBS)
        for prices_fbo in mp_object.get_prices():  # GET /public/api/v1/info
            # prices_fbo = append_offer_ids(prices_fbo)  # !!! надо придумать как подгружать offer_id по product_id
            prices_fbo = append_cols(prices_fbo, account_id, api_key)
            insert_into_db('price_table', prices_fbo)

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
