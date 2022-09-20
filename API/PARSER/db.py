from psycopg2.pool import ThreadedConnectionPool
from config import DB_DSN
from loguru import logger


# класс для работы с connection pooling
class ConnectionPool(ThreadedConnectionPool):
    def __init__(self, minconn, maxconn, *args, **kwargs):
        super().__init__(minconn, maxconn, *args, **kwargs)

    def connect_to_pool(self):
        return self.getconn()

    def disconnect_from_pool(self, connection):
        return self.putconn(connection)


db_connection_pool = ConnectionPool(1, 100, DB_DSN)


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