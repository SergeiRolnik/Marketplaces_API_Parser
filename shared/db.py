from shared.config import DB_DSN, MAX_NUM_OF_CONNECTIONS
from psycopg2.pool import ThreadedConnectionPool
from psycopg2._json import Json
from loguru import logger
from threading import Semaphore


class ReallyThreadedConnectionPool(ThreadedConnectionPool):
    def __init__(self, minconn, maxconn, *args, **kwargs):
        self._semaphore = Semaphore(maxconn)
        super().__init__(minconn, maxconn, *args, **kwargs)

    def getconn(self, *args, **kwargs):
        self._semaphore.acquire()
        return super().getconn(*args, **kwargs)

    def putconn(self, *args, **kwargs):
        super().putconn(*args, **kwargs)
        self._semaphore.release()


connection_pool = ReallyThreadedConnectionPool(1, MAX_NUM_OF_CONNECTIONS, DB_DSN)


def run_sql_delete(sql: str):
    try:
        connection = connection_pool.getconn()
        connection.autocommit = True
        cursor = connection.cursor()
        cursor.execute(sql)
    except Exception as error:
        logger.error(f'Ошибка {error} при обработке SQL запроса {sql}')
    finally:
        if connection:
            connection_pool.putconn(connection, close=False)


def run_sql(sql: str, values: list):
    try:
        connection = connection_pool.getconn()
        connection.autocommit = True
        cursor = connection.cursor()
        cursor.executemany(sql, values)
    except Exception as error:
        logger.error(f'Ошибка {error} при обработке SQL запроса {sql}')
    finally:
        if connection:
            connection_pool.putconn(connection, close=False)


def run_sql_account_list(sql: str, values: tuple):
    try:
        connection = connection_pool.getconn()
        cursor = connection.cursor()
        cursor.execute(sql, values)
        result = cursor.fetchall()
        return result
    except Exception as error:
        logger.error(f'Ошибка {error} при обработке SQL запроса {sql}')
    finally:
        if connection:
            connection_pool.putconn(connection, close=False)


def run_sql_get_offer_ids(sql: str):
    try:
        connection = connection_pool.getconn()
        cursor = connection.cursor()
        cursor.execute(sql)
        column_names = [col[0] for col in cursor.description]
        result = [dict(zip(column_names, row)) for row in cursor.fetchall()]  # преобразовать в список словарей
        return result
    except Exception as error:
        logger.error(f'Ошибка {error} при обработке SQL запроса {sql}')
    finally:
        if connection:
            connection_pool.putconn(connection, close=False)


def get_table_cols(table_name: str):
    try:
        connection = connection_pool.getconn()
        cursor = connection.cursor()
        sql = f"SELECT column_name FROM information_schema.columns WHERE table_name='{table_name}'"
        cursor.execute(sql)
        result = cursor.fetchall()
        result = [item[0] for item in result]
        return result
    except Exception as error:
        logger.error(f'Ошибка {error} при обработке SQL запроса {sql}')
    finally:
        if connection:
            connection_pool.putconn(connection, close=False)


# --- ФУНКЦИИ ДЛЯ РАБОТЫ API ---------------------------------------------------------

# ОДНА ФУНКЦИЯ ДЛЯ ВСЕХ ЗАПРОСОВ
def run_sql_api(sql: str, values: tuple):

    if len(values) == 2 and sql.find('category_id') == -1:
        values = list(values)
        values[1] = Json(values[1]) # если идет запись правила, преобразовать его в json объект
        values = tuple(values)

    try:
        connection = connection_pool.getconn()
        connection.autocommit = True
        cursor = connection.cursor()
        cursor.execute(sql, values)
        result = cursor.fetchall()
        return result
    except Exception as error:
        logger.error(f'Ошибка {error} при обработке SQL запроса {sql}')
    finally:
        if connection:
            connection_pool.putconn(connection, close=False)


def run_sql_insert_many(sql: str, values: list):
    try:
        connection = connection_pool.getconn()
        connection.autocommit = True
        cursor = connection.cursor()
        cursor.executemany(sql, values)
    except Exception as error:
        logger.error(f'Ошибка {error} при обработке SQL запроса {sql}')
    finally:
        if connection:
            connection_pool.putconn(connection, close=False)


def run_sql_get_product_ids(sql: str):
    try:
        connection = connection_pool.getconn()
        cursor = connection.cursor()
        cursor.execute(sql)
        column_names = [col[0] for col in cursor.description]
        result = [dict(zip(column_names, row)) for row in cursor.fetchall()]  # преобразовать в список словарей
        return result
    except Exception as error:
        logger.error(f'Ошибка {error} при обработке SQL запроса {sql}')
    finally:
        if connection:
            connection_pool.putconn(connection, close=False)

