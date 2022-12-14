from shared.db import run_sql, run_sql_api, run_sql_account_list, run_sql_delete, get_table_cols, connection_pool
from PARSER.config import TEST_ACCOUNTS, EXCLUDE_ACCOUNTS, DB_TABLES, PRINT_DB_INSERTS
from MARKETPLACES.ozon.ozon import OzonApi
from MARKETPLACES.wb.wb import WildberriesApi
from MARKETPLACES.yandex.yandex import YandexMarketApi
from concurrent.futures import ThreadPoolExecutor
from loguru import logger
import pandas as pd
from datetime import date


def create_mp_object(account: dict):  # на вход словарь {(account_id, mp_id): [(attribute_id, attribute_value), ...]}
    mp_id = list(account.keys())[0][1]
    attribute_values = [item[1] for item in list(account.values())[0]]
    if mp_id == 1:  # Озон
        return OzonApi(attribute_values[0], attribute_values[1])
    if mp_id == 2:  # ЯМ
        return YandexMarketApi(attribute_values[0], attribute_values[1], attribute_values[2])
    if mp_id == 3:  # ВБ (FBO)
        return WildberriesApi(attribute_values[0], '')
    if mp_id == 15:  # ВБ (FBS)
        return WildberriesApi('', attribute_values[0])


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

    if PRINT_DB_INSERTS:
        print(len(dataset), 'записей добавлено в таблицу', table_name, ' / account_id=', account_id)


def append_offer_ids(products: list, account_id: int) -> list:
    sql = 'SELECT product_id, offer_id FROM product_list WHERE account_id=%s'
    mappings = run_sql_api(sql, (str(account_id), ))
    mappings = {mapping[0]: mapping[1] for mapping in mappings}
    df = pd.DataFrame.from_dict(products)
    df['offer_id'] = df['product_id'].map(mappings)
    df = df.where(df.notnull(), None)
    return df.to_dict('records')


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


def append_sales_percent(prices: list, sales_percents: list) -> list:
    prices = pd.DataFrame.from_dict(prices)
    sales_percents = pd.DataFrame.from_dict(sales_percents)
    prices_with_sales_percents = pd.merge(prices, sales_percents, on='offer_id', how='left')
    prices_with_sales_percents = prices_with_sales_percents.where(prices_with_sales_percents.notnull(), None)
    return prices_with_sales_percents.to_dict('records')


# --- !!! НОВАЯ ФУНКЦИЯ (ДОБАВЛЯЕТ ЦЕНУ BUYBOX) добавлена 15.12.22
def append_recommended_prices(prices: list, recommended_prices: list) -> list:
    prices = pd.DataFrame.from_dict(prices)
    recommended_prices = pd.DataFrame.from_dict(recommended_prices)
    prices_with_recommended_prices = pd.merge(prices, recommended_prices, on='product_id', how='left')  # !!! on product_id ???
    prices_with_recommended_prices = prices_with_recommended_prices.where(prices_with_recommended_prices.notnull(), None)
    return prices_with_recommended_prices.to_dict('records')


def process_account_data(account: dict):
    # account - словарь {(account_id, mp_id): [(attribute_id, attribute_value, key_attr), (), ...]}
    account_id, mp_id = list(account.keys())[0]
    # print('Обрабатывается аккаунт', account)
    attrs = list(account.values())[0]
    api_key = list(filter(lambda x: x[2], attrs))[0][1]
    mp_object = create_mp_object(account)  # инициализация объекта класса МП

    if mp_id == 1:  # -------------------------------------- ОЗОН ----------------------------------------

        # --- WAREHOUSES FBS --- !!! проверить почему в данных по складу is_rfbs = false
        warehouses = mp_object.get_warehouses()  # POST /v1/warehouse/list список складов
        insert_into_db('wh_table', warehouses, account_id, api_key)
        warehouses.clear()

        # --- PRODUCTS ---
        # for products_chunk in mp_object.get_product_list([], []):  # /v2/product/list (список всех товаров)
        #     offer_ids = [product['offer_id'] for product in products_chunk]
        #     products = mp_object.get_product_info_list(offer_ids)  # /v2/product/info/list (подробная информация о товарах по списку offer_id)
        #     insert_into_db('product_list', products, account_id, api_key)  # БОЛЬШЕ НЕ ЗАПИСЫВАЕМ В ТАБЛИЦУ product_list

        # --- ALL STOCKS --- (данные для таблицы total_stock)
        for stocks_chunk in mp_object.get_stocks_info():  # POST /v3/product/info/stocks
            insert_into_db('total_stock', stocks_chunk, account_id, api_key, add_date=True)

            # --- STOCKS FBS ---
            offer_ids = [product['offer_id'] for product in stocks_chunk]
            fbs_skus = mp_object.get_product_info_list(offer_ids, fbs=True)  # /v2/product/info/list (отбираем товары по списку offer_ids на складах FBS)

            # print('fbs_skus', len(fbs_skus))

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

    if mp_id == 2:  # ------------------------ ЯМ ------------------------------------------------------------

        warehouses = []
        sales_percents = []
        # --- STOCKS ---
        for products_chunk in mp_object.get_info():  # GET /campaigns/{campaignId}/offer-mapping-entries
            shop_skus_chunk = [product['offer_id'] for product in products_chunk]  # выделяем shopSkus
            # insert_into_db('product_list', products_chunk, account_id, api_key)  # НЕ ЗАПИСЫВАЕМ В ТАБЛИЦУ product_list
            products_chunk, sales_percents_chunk = mp_object.get_stocks(shop_skus_chunk)  # POST /stats/skus
            insert_into_db('stock_by_wh', products_chunk, account_id, api_key, add_date=True)  # -----------
            sales_percents += sales_percents_chunk

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

        # --- PRICES --- (!!! ДОБАВИТЬ ЗАГРУЗКУ ЦЕН ЧЕРЕЗ МЕТОД /stats/skus)
        for prices_chunk in mp_object.get_prices():  # GET /offer-prices

            # print('prices_chunk before append_offer_ids', prices_chunk[0:20])  # ------------------
            prices_chunk = append_offer_ids(prices_chunk, account_id)
            # print('prices_chunk after append_offer_ids', prices_chunk[0:20])  # ------------------
            prices_chunk = append_sales_percent(prices_chunk, sales_percents)
            # print('prices_chunk after append_sales_percent', prices_chunk[0:20])  # ------------------

            # --- ADD RECOMMENDED PRICE / BUYBOX ------ добавлено 15.12.22 -------------------------------------
            market_skus = [{'marketSku': int(float(product['product_id']))}
                           for product in prices_chunk if product['product_id'] != 'None']
            recommended_prices = mp_object.get_recommended_prices(market_skus)

            try:
                prices_chunk = append_recommended_prices(prices_chunk, recommended_prices)
            except KeyError as error:
                logger.error(f'Ошибка {error} при добавлении recommended_price / account_id={account_id}')

            # --------------------------------------------------------------------------------------------------

            insert_into_db('price_table', prices_chunk, account_id, api_key, add_date=True)

    if mp_id == 3:  # ---------------------------------- ВБ (FBO) -----------------------------------------------

        # --- WAREHOUSES FBO(?) ---
        warehouses = mp_object.get_warehouses()  # /api/v2/warehouses, список словарей {'warehouse_id':..., 'name': ...}
        for warehouse in warehouses:  # метод получает только склады FBO?
            warehouse['wh_type'] = 'FBO'
        insert_into_db('wh_table', warehouses, account_id, api_key)

        # --- STOCKS FBO ---
        warehouses_fbo = []
        for products_fbo_chunk in mp_object.get_stocks_fbo():  # GET /api/v2/stocks
            insert_into_db('stock_by_wh', products_fbo_chunk, account_id, api_key, add_date=True)

            # --- PRODUCTS FBO ---
            # products = [
            #     {
            #         'product_id': product['product_id'],
            #         'offer_id': product['offer_id'],
            #         'barcode': product['barcode'],
            #         'category_id': product['category'],
            #         'name': product['product_name']  # !!! возможно загрузить другие поля
            #     }
            #     for product in products_fbo_chunk]
            # insert_into_db('product_list', products, account_id, api_key)  # БОЛЬШЕ НЕ ЗАПИСЫВАЕМ В ТАБЛИЦУ product_list

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

        # --- PRICES FBO + FBS --- (!!! включает также товары FBS)
        for prices_fbo in mp_object.get_prices():  # GET /public/api/v1/info
            prices_fbo = append_offer_ids(prices_fbo, account_id)  # НОВАЯ ФУНКЦИЯ
            insert_into_db('price_table', prices_fbo, account_id, api_key, add_date=True)

    if mp_id == 15:  # ---------------------------------- ВБ (FBS) -----------------------------------------------

        # --- STOCKS & PRICES FBS --- (используется один и тот же метод)
        warehouses_fbs = []
        for products_fbs_chunk in mp_object.get_stocks_fbs():  # GET /api/v1/supplier/stocks

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
            # products = [
            #     {
            #         'product_id': product['product_id'],
            #         'offer_id': product['offer_id'],
            #         'barcode': product['barcode'],
            #         'category_id': product['product_category'],
            #         'name': product['product_name']  # !!! возможно загрузить другие поля
            #     }
            #     for product in products_fbs_chunk]
            # insert_into_db('product_list', products, account_id, api_key)  # БОЛЬШЕ НЕ ЗАПИСЫВАЕМ В ТАБЛИЦУ product_list

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

    return account_id


def main():
    logger.remove()
    logger.add(sink='logs/parser_logfile.log', format="{time} {level} {message}", level="INFO")
    logger.info('Работа скрипта начата')

    futures = []
    with ThreadPoolExecutor() as executor:

        for mp_id in [1, 2, 3, 15]:  # цикл по маркетплейсам
            sql = '''
            SELECT al.id, al.mp_id, asd.attribute_id, asd.attribute_value, sa.key_attr
            FROM account_list al
            JOIN account_service_data asd ON al.id = asd.account_id
            JOIN service_attr sa ON asd.attribute_id = sa.id
            WHERE al.status_1 = 'Active' AND al.mp_id = %s
            ORDER BY al.id, asd.attribute_id
            '''
            mp_accounts = run_sql_account_list(sql, (str(mp_id), ))
            accounts_groupped = {}
            processed_attr_values = []

            if TEST_ACCOUNTS:  # список номеров аккаунтов в таблице account_list для тестирования (указать в config.py)
                mp_accounts = [account for account in mp_accounts if account[0] in TEST_ACCOUNTS]

            if not TEST_ACCOUNTS and EXCLUDE_ACCOUNTS:  # список номеров аккаунтов в таблице account_list, которые нужно исключить
                mp_accounts = [account for account in mp_accounts if account[0] not in EXCLUDE_ACCOUNTS]

            for account_id, mp_id, attr_id, attr_value, key_attr in mp_accounts:
                accounts_groupped.setdefault((account_id, mp_id), []).append((attr_id, attr_value, key_attr))

            for account, attrs in accounts_groupped.items():
                attr_value = list(filter(lambda x: x[2], attrs))[0][1]
                if attr_value not in processed_attr_values:
                    future = executor.submit(process_account_data, {account: attrs})
                    futures.append(future)
                    processed_attr_values.append(attr_value)

        # accounts - список словарей {(account_id, mp_id): [(attribute_id, attribute_value, key_attr), (), ...]}
        response = [future.result() for future in futures]

    delete_duplicate_records_from_db()  # удалить дупликаты во всех таблицах
    connection_pool.closeall()
    logger.info(f'Работа скрипта завершена.  Номера обработанных аккаунтов {response}')


if __name__ == '__main__':
    main()
