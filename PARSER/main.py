from MARKETPLACES.ozon.ozon import OzonApi
from MARKETPLACES.wb.wb import WildberriesApi
from MARKETPLACES.yandex.yandex import YandexMarketApi
from MARKETPLACES.sber.sber import SberApi
import concurrent.futures
from loguru import logger
from itertools import zip_longest
from db import run_sql, run_sql_account_list, run_sql_get_offer_ids, run_sql_delete, get_table_cols
from datetime import date
from config import TEST_ACCOUNTS, DB_TABLES


def create_mp_object(mp_id: int, client_id: str, api_key: str, campaign_id: str):
    if mp_id == 1:
        return OzonApi(client_id, api_key)
    elif mp_id == 2:
        return YandexMarketApi(client_id, api_key, campaign_id)
    elif mp_id == 3:
        return WildberriesApi(client_id, api_key)
    elif mp_id == 4:
        return SberApi(api_key)


def insert_into_db(table_name: str, dataset: list, account_id: int, api_id: str, add_date=False):
    if dataset:
        for row in dataset:
            row['account_id'] = account_id
            row['api_id'] = api_id
            if add_date:
                row['date'] = str(date.today())
        dataset_fields = list(dataset[0].keys())
        table_fields = get_table_cols(table_name)
        actual_fields = list(set(dataset_fields) & set(table_fields))
        fields_difference = list(set(dataset_fields) - set(table_fields))
        dataset = [{key: val for key, val in row.items() if key not in fields_difference} for row in dataset]
        fields = ','.join(actual_fields)
        values = ','.join([f'%({value})s' for value in actual_fields])
        sql = f'INSERT INTO {table_name} ({fields}) VALUES ({values})'
        run_sql(sql, dataset)

        print(len(dataset), 'records inserted in', table_name, ' / account_id=', account_id)  # --- TESTING ---


# добавить к списку offer_id (для ЯМ и ВБ), на вход список словарей {'product_id':.., 'price': ...}
def append_offer_ids(products: list) -> list:
    product_ids = [product['product_id'] for product in products]
    sql = "SELECT offer_id, product_id FROM product_list WHERE product_id IN (%s)" % str(product_ids).strip('[]')
    offer_product_ids = run_sql_get_offer_ids(sql)
    products = sorted(products, key=lambda item: item['product_id'])
    offer_product_ids = sorted(offer_product_ids, key=lambda item: item['product_id'])
    products = [{**k, **v} for k, v in zip_longest(products, offer_product_ids, fillvalue={'offer_id': None})]
    return products


def remove_duplicate_warehouses(warehouses: list) -> list:
    unique_warehouses = []
    for warehouse in warehouses:
        if warehouse not in unique_warehouses:
            unique_warehouses.append(warehouse)
    return unique_warehouses


def delete_duplicate_records_from_db():
    for table in DB_TABLES:
        table_name = table['table_name']
        partition = table['partition']
        sql = f'''
            DELETE FROM {table_name} WHERE id IN (SELECT id FROM
            (SELECT id, row_number() OVER(PARTITION BY {partition} ORDER BY id DESC) FROM {table_name}) AS sel_unique
            WHERE row_number >= 2)
            '''
        run_sql_delete(sql)


def process_account_data(account_id: int):
    sql = 'SELECT mp_id, client_id_api, api_key, campaigns_id FROM account_list WHERE id=%s'
    result = run_sql_account_list(sql, (str(account_id),))
    mp_id, client_id, api_key, campaign_id = result[0]
    mp_object = create_mp_object(mp_id, client_id, api_key, campaign_id)

    if mp_id == 1:  # -------------------------------------- ОЗОН ----------------------------------------

        # --- WAREHOUSES FBS --- !!! проверить почему в данных по складу is_rfbs = false
        warehouses = mp_object.get_warehouses()  # POST /v1/warehouse/list список складов
        insert_into_db('wh_table', warehouses, account_id, api_key)
        warehouses.clear()

        # --- PRODUCTS ---
        for products_chunk in mp_object.get_product_list([], []):  # /v2/product/list (список всех товаров)
            offer_ids = [product['offer_id'] for product in products_chunk]
            products = mp_object.get_product_info_list(offer_ids)  # /v2/product/info/list (подробная информация о товарах по списку offer_id)
            insert_into_db('product_list', products, account_id, api_key)

        # --- ALL STOCKS --- (данные для таблицы total_stock)
        for stocks_chunk in mp_object.get_stocks_info():  # POST /v3/product/info/stocks
            insert_into_db('total_stock', stocks_chunk, account_id, api_key, add_date=True)

            # --- STOCKS FBS ---
            offer_ids = [product['offer_id'] for product in stocks_chunk]
            fbs_skus = mp_object.get_product_info_list(offer_ids, fbs=True)  # /v2/product/info/list (отбираем товары по списку offer_ids на складах FBS)
            products_fbs = mp_object.get_stocks_fbs(fbs_skus)  # /v1/product/info/stocks-by-warehouse/fbs
            insert_into_db('stock_by_wh', products_fbs, account_id, api_key, add_date=True)

        # --- STOCKS FBO ---
        for products_fbo_chunk in mp_object.get_stocks_fbo():  # /v1/analytics/stock_on_warehouses
            insert_into_db('stock_by_wh', products_fbo_chunk, account_id, api_key, add_date=True)

            # --- WAREHOUSES FBO ---
            warehouses_chunk = [
                {
                    'warehouse_id': warehouse['warehouse_id'],
                    'name': warehouse['warehouse_name'],
                    'wh_type': 'FBO',
                    'account_id': account_id
                }
                for warehouse in products_fbo_chunk]
            warehouses += remove_duplicate_warehouses(warehouses_chunk)
        insert_into_db('wh_table', remove_duplicate_warehouses(warehouses), account_id, api_key)

        # --- PRICES ---
        for prices_chunk in mp_object.get_prices():  # POST /v4/product/info/prices
            insert_into_db('price_table', prices_chunk, account_id, api_key, add_date=True)

    elif mp_id == 2:  # ------------------------ ЯМ ------------------------------------------------------------

        warehouses = []
        # --- STOCKS ---
        for products_chunk in mp_object.get_info():  # GET /campaigns/{campaignId}/offer-mapping-entries
            shop_skus_chunk = [product['offer_id'] for product in products_chunk]  # выделяем shopSkus
            insert_into_db('product_list', products_chunk, account_id, api_key)
            products_chunk = mp_object.get_stocks(shop_skus_chunk)  # POST /stats/skus
            insert_into_db('stock_by_wh', products_chunk, account_id, api_key, add_date=True)

            # --- WAREHOUSES (FBY или FBS?) ---
            warehouses_chunk = [
                {
                    'warehouse_id': warehouse['warehouse_id'],
                    'name': warehouse['warehouse_name'],
                    'wh_type': 'FBY',  # !!! какой тип склада FBY или FBS?
                }
                for warehouse in products_chunk]
            warehouses += remove_duplicate_warehouses(warehouses_chunk)
        insert_into_db('wh_table', remove_duplicate_warehouses(warehouses), account_id, api_key)

        # --- PRICES ---
        for prices_chunk in mp_object.get_prices():  # GET /offer-prices
            prices_chunk = append_offer_ids(prices_chunk)
            insert_into_db('price_table', prices_chunk, account_id, api_key, add_date=True)

    elif mp_id == 3:  # ---------------------------------- ВБ --------------------------------------------------

        # --- WAREHOUSES FBO(?) ---
        warehouses = mp_object.get_warehouses()  # /api/v2/warehouses, список словарей {'warehouse_id':..., 'name': ...}
        for warehouse in warehouses:             # метод получает только склады FBO?
            warehouse['wh_type'] = 'FBO'
        insert_into_db('wh_table', warehouses, account_id, api_key)

        # --- STOCKS FBO ---
        warehouses_fbo = []
        for products_fbo_chunk in mp_object.get_stocks_fbo():  # GET /api/v2/stocks
            insert_into_db('stock_by_wh', products_fbo_chunk, account_id, api_key, add_date=True)

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
            insert_into_db('product_list', products, account_id, api_key)

            # --- WAREHOUSES FBO ---
            warehouses_fbo_chunk = [
                {
                    'warehouse_id': product['warehouse_id'],
                    'name': product['warehouse_name'],
                    'wh_type': 'FBO',
                }
                for product in products_fbo_chunk]
            warehouses_fbo += remove_duplicate_warehouses(warehouses_fbo_chunk)
        insert_into_db('wh_table', remove_duplicate_warehouses(warehouses_fbo), account_id, api_key)

        # --- STOCKS & PRICES FBS --- (используется один и тот же метод)
        warehouses_fbs = []
        for products_fbs_chunk in mp_object.get_stocks_fbs():   # GET /api/v1/supplier/stocks

            # --- STOCKS ---
            stocks_fbs = [
                {
                    'warehouse_id': product['warehouse_id'],
                    'offer_id': product['offer_id'],
                    'product_id': product['product_id'],
                    'fbo_present': product['fbo_present'],
                    'fbs_present': product['fbs_present']
                }
                for product in products_fbs_chunk]
            insert_into_db('stock_by_wh', stocks_fbs, account_id, api_key, add_date=True)

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
            insert_into_db('product_list', products, account_id, api_key)

            # --- PRICES FBS ---  !!! дублирует product_id полученные через метод # GET /public/api/v1/info
            prices_fbs = [
                {
                    'offer_id': product['offer_id'],
                    'product_id': product['product_id'],
                    'price': product['price']
                }
                for product in products_fbs_chunk]
            insert_into_db('price_table', prices_fbs, account_id, api_key, add_date=True)

            # --- WAREHOUSES FBS ---
            warehouses_fbs_chunk = [
                {
                    'warehouse_id': product['warehouse_id'],
                    'name': product['warehouse_name'],
                    'wh_type': 'FBS',
                    'account_id': account_id
                }
                for product in products_fbs_chunk]
            warehouses_fbs += remove_duplicate_warehouses(warehouses_fbs_chunk)
        insert_into_db('wh_table', remove_duplicate_warehouses(warehouses_fbs), account_id, api_key)

        # --- PRICES FBO + FBS --- (!!! включает также товары FBS)
        for prices_fbo in mp_object.get_prices():  # GET /public/api/v1/info
            prices_fbo = append_offer_ids(prices_fbo)
            insert_into_db('price_table', prices_fbo, account_id, api_key, add_date=True)

    return account_id


def main():
    logger.remove()
    logger.add(sink='logfile.log', format="{time} {level} {message}", level="INFO")
    logger.info('Работа скрипта начата')

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

    delete_duplicate_records_from_db()  # удалить дупликаты во всех таблицах
    logger.info(f'Работа скрипта завершена.  Номера обработанных аккаунтов {response}')


if __name__ == '__main__':
    main()
