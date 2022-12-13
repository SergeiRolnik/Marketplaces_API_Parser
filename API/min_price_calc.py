from loguru import logger
from shared.db import run_sql, run_sql_api, run_sql_account_list, run_sql_delete, get_table_cols, connection_pool
from PARSER.config import TEST_ACCOUNTS, EXCLUDE_ACCOUNTS, DB_TABLES, PRINT_DB_INSERTS


def get_min_price(price: float, min_margin: float, commission: float):  # commission - sales_percent (Yandex)
    delivery = min(max(60.0, price * 1.05), 350.0)
    processing = min(max(20.0, price * 1.03), 60.0)
    min_margin = (100 + min_margin) / 100
    min_price = (price + delivery + processing + price * min_margin) / (1 - commission / 100)  # FBY и FBS
    min_price_express = (price + price * min_margin) / (1 - commission / 100)  # Express
    return min_price, min_price_express


def main():
    logger.remove()
    logger.add(sink='logs/price_calc_logfile.log', format="{time} {level} {message}", level="INFO")
    logger.info('Работа скрипта начата')

    # получить список api_id по аккаунтам ЯМ
    sql = '''
    select api_id from price_table pt
    where account_id in (select id from account_list where mp_id = 2)
    group by api_id
    '''
    api_id_list = run_sql_account_list(sql, ())

    for api_id in api_id_list:

        # выборка из таблицы price_table для конкретного api_id
        sql = '''
        select * from (
        select account_id, offer_id, price, sales_percent, api_id, date, row_number() 
        over(partition by offer_id order by date desc) as row_num
        from price_table pt
        ) t
        where t.row_num = 1
        '''
        prices = run_sql_account_list(sql, ())


        # выборка из таблицы margin (все записи)
        sql = '''
        select * from (
        select offer_id, min_margin, account_id as api_id, date, row_number() 
        over(partition by offer_id order by date desc) as row_num
        from margin
        ) t
        where
        t.row_num = 1
        '''
        margins = run_sql_account_list(sql, ())

    # получить из prices и margins - price / min_margin / commission
    data = get_min_price(price, min_margin, commission)

    # записать данные в таблицу price_table

    connection_pool.closeall()
    logger.info(f'Работа скрипта завершена')


if __name__ == '__main__':
    main()
