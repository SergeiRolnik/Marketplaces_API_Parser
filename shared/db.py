from shared.config import DB_DSN, MAX_NUM_OF_CONNECTIONS
from psycopg2.pool import ThreadedConnectionPool
from psycopg2._json import Json
from loguru import logger
from threading import Semaphore
import psycopg2
import psycopg2.extras


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


def read_from_suppliers_db():  # из таблицы suppliers получить список поставщиков
    try:
        connection = psycopg2.connect(DB_DSN)
        cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # sql = '''
        # SELECT * FROM suppliers
        # JOIN supplier_client ON suppliers.id=supplier_client.supplier_id
        # WHERE supplier_client.client_id=%s AND supplier_client.last_request_date<CURRENT_DATE
        # '''\
        #       % str(client_id)

        # sql = '''
        # SELECT * FROM suppliers
        # JOIN supplier_client ON suppliers.id=supplier_client.supplier_id
        # WHERE supplier_client.last_request_date<CURRENT_DATE
        # '''

        sql = 'SELECT * FROM suppliers'

        cursor.execute(sql)
        suppliers = cursor.fetchall()
        return suppliers
    except ConnectionError as error:
        logger.error(f'Ошибка при подключении или чтении из таблицы suppliers: {error}')


def update_last_request_date(client_id: int, supplier_id: int):  # обновить дату last_request_date
    try:
        connection = psycopg2.connect(DB_DSN)
        connection.autocommit = True
        cursor = connection.cursor()

        sql = '''
        UPDATE supplier_client
        SET last_request_date=CURRENT_DATE
        WHERE client_id=%s AND supplier_id=%s 
        '''\
              % (str(client_id), str(supplier_id))

        cursor.execute(sql)
    except ConnectionError as error:
        logger.error(f'Ошибка при обновлении даты в таблице suppliers: {error}')


def show_client_list():  # подсоединиться к БД и получить список поставщиков
    try:
        connection = psycopg2.connect(DB_DSN)
        cursor = connection.cursor()
        sql = 'SELECT * FROM client ORDER BY id'
        cursor.execute(sql)
        clients = cursor.fetchall()
        return clients
    except ConnectionError as error:
        logger.error(f'Ошибка при подключении или чтении из таблицы client: {error}')
