from shared.config import DB_DSN, MAX_NUM_OF_CONNECTIONS
from psycopg2.pool import ThreadedConnectionPool
from psycopg2._json import Json
from loguru import logger


class ConnectionPool(ThreadedConnectionPool):
    def __init__(self, minconn, maxconn, *args, **kwargs):
        super().__init__(minconn, maxconn, *args, **kwargs)

    def connect_to_pool(self):
        return self.getconn()

    def disconnect_from_pool(self, connection):
        return self.putconn(connection)


db_connection_pool = ConnectionPool(1, MAX_NUM_OF_CONNECTIONS, DB_DSN)


def run_sql_delete(sql: str):
    try:
        connection = db_connection_pool.connect_to_pool()
        connection.autocommit = True
        cursor = connection.cursor()
        cursor.execute(sql)
    except Exception as error:
        logger.error(f'Ошибка {error} при обработке SQL запроса {sql}')
    finally:
        if connection:
            db_connection_pool.disconnect_from_pool(connection)


def run_sql(sql: str, values: list):
    try:
        connection = db_connection_pool.connect_to_pool()
        connection.autocommit = True
        cursor = connection.cursor()
        cursor.executemany(sql, values)
    except Exception as error:
        logger.error(f'Ошибка {error} при обработке SQL запроса {sql}')
    finally:
        if connection:
            db_connection_pool.disconnect_from_pool(connection)


def run_sql_account_list(sql: str, values: tuple):
    try:
        connection = db_connection_pool.connect_to_pool()
        cursor = connection.cursor()
        cursor.execute(sql, values)
        result = cursor.fetchall()
        return result
    except Exception as error:
        logger.error(f'Ошибка {error} при обработке SQL запроса {sql}')
    finally:
        if connection:
            db_connection_pool.disconnect_from_pool(connection)


def run_sql_get_offer_ids(sql: str):
    try:
        connection = db_connection_pool.connect_to_pool()
        cursor = connection.cursor()
        cursor.execute(sql)
        column_names = [col[0] for col in cursor.description]
        result = [dict(zip(column_names, row)) for row in cursor.fetchall()]  # преобразовать в список словарей
        return result
    except Exception as error:
        logger.error(f'Ошибка {error} при обработке SQL запроса {sql}')
    finally:
        if connection:
            db_connection_pool.disconnect_from_pool(connection)


def get_table_cols(table_name: str):
    try:
        connection = db_connection_pool.connect_to_pool()
        cursor = connection.cursor()
        sql = f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name='{table_name}'"
        cursor.execute(sql)
        result = cursor.fetchall()
        result = [item[0] for item in result]
        return result
    except Exception as error:
        logger.error(f'Ошибка {error} при обработке SQL запроса {sql}')
    finally:
        if connection:
            db_connection_pool.disconnect_from_pool(connection)


# --- ФУНКЦИИ ДЛЯ РАБОТЫ API ---------------------------------------------------------

# ОДНА ФУНКЦИЯ ДЛЯ ВСЕХ ЗАПРОСОВ
def run_sql_api(sql: str, values: tuple):

    if len(values) == 2 and sql.find('category_id') == -1:
        values = list(values)
        values[1] = Json(values[1]) # если идет запись правила, преобразовать его в json объект
        values = tuple(values)

    try:
        connection = db_connection_pool.connect_to_pool()
        connection.autocommit = True
        cursor = connection.cursor()
        cursor.execute(sql, values)
        result = cursor.fetchall()
        return result
    except Exception as error:
        logger.error(f'Ошибка {error} при обработке SQL запроса {sql}')
    finally:
        if connection:
            db_connection_pool.disconnect_from_pool(connection)


def run_sql_insert_many(sql: str, values: list):
    try:
        connection = db_connection_pool.connect_to_pool()
        connection.autocommit = True
        cursor = connection.cursor()
        cursor.executemany(sql, values)
    except Exception as error:
        logger.error(f'Ошибка {error} при обработке SQL запроса {sql}')
    finally:
        if connection:
            db_connection_pool.disconnect_from_pool(connection)


def run_sql_get_product_ids(sql: str):
    try:
        connection = db_connection_pool.connect_to_pool()
        cursor = connection.cursor()
        cursor.execute(sql)
        column_names = [col[0] for col in cursor.description]
        result = [dict(zip(column_names, row)) for row in cursor.fetchall()]  # преобразовать в список словарей
        return result
    except Exception as error:
        logger.error(f'Ошибка {error} при обработке SQL запроса {sql}')
    finally:
        if connection:
            db_connection_pool.disconnect_from_pool(connection)

