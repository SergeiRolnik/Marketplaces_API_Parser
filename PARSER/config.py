import os
from os.path import join, dirname, exists
from dotenv import load_dotenv

dotenv_path = join(dirname(__file__), '.env')

# если файл .env существует подгрузить переменные окружения из него
if exists(dotenv_path):
    load_dotenv(dotenv_path)

# --------------------------------------------------------------------------------
#                        GENERAL SETTINGS
# --------------------------------------------------------------------------------

DB_TABLES = [  # названия таблиц в БД и уникальные поля для удаления дупликатов
    {'table_name': 'total_stock', 'partition': 'product_id, date'},
    {'table_name': 'price_table', 'partition': 'product_id, date'},
    {'table_name': 'stock_by_wh', 'partition': 'product_id, warehouse_id, date'},
    {'table_name': 'product_list', 'partition': 'product_id, api_id'},
    {'table_name': 'wh_table', 'partition': 'warehouse_id, api_id'}
]

CHUNK_SIZE = 5000  # маскимальный размер списка для оптимизации оперативной памяти

# --------------------------------------------------------------------------------
#                        DEVELOPMENT SETTINGS
# --------------------------------------------------------------------------------
if os.environ.get('APP_ENV') == 'development':

    # параметры подключения к локальной БД
    DB_SERVER = os.environ.get('PG_HOST')
    DB_USER = os.environ.get('PG_USER')
    DB_PASSWORD = os.environ.get('PG_PASSWORD')
    DB_NAME = os.environ.get('PG_DB')
    DB_DSN = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_SERVER}/{DB_NAME}'

    SLEEP_TIME = 5  # время между запросами в API маркетплейсов (сек)
    TEST_ACCOUNTS = [1, 3, 13]  # номера аккаунтов для тестирования в локальной таблице account_list

# --------------------------------------------------------------------------------
#                            PRODUCTION SETTINGS
# --------------------------------------------------------------------------------
if os.environ.get('APP_ENV') == 'production':

    # параметры подключения к market_db
    DB_DSN = f'''
    host={os.environ.get('PG_HOST')}
    port={os.environ.get('PG_PORT')}
    dbname={os.environ.get('PG_DB')}
    user={os.environ.get('PG_USER')}
    password={os.environ.get('PG_PASSWORD')}
    target_session_attrs={os.environ.get('TARGET_SESSION_ATTRS')}
    sslmode={os.environ.get('SSLMODE')}
    sslrootcert={os.environ.get('ROOT_CERT')}
    '''

    SLEEP_TIME = 0  # время между запросами в API маркетплейсов (сек)
    TEST_ACCOUNTS = []  # номера аккаунтов для тестирования в таблице account_list в БД market_db, например, [1, 2, 3]
