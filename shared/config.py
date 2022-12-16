import os
from os.path import join, dirname, exists
from dotenv import load_dotenv

dotenv_path = join(dirname(__file__), '.env')

# если файл .env существует подгрузить переменные окружения из него
if exists(dotenv_path):
    load_dotenv(dotenv_path)

APP_ENV = os.environ.get('APP_ENV')
MAX_NUM_OF_CONNECTIONS = 16  # максимально число соединений в пуле
ATTR_VIRT = 8

# --------------------------------------------------------------------------------
#                        DEVELOPMENT SETTINGS
# --------------------------------------------------------------------------------

if APP_ENV == 'development':

    # параметры подключения к локальной БД
    DB_SERVER = os.environ.get('PG_HOST')
    DB_USER = os.environ.get('PG_USER')
    DB_PASSWORD = os.environ.get('PG_PASSWORD')
    DB_NAME = os.environ.get('PG_DB')
    DB_DSN = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_SERVER}/{DB_NAME}'

# --------------------------------------------------------------------------------
#                            TESTING SETTINGS (заполнение таблиц на сервере с локального компьютера)
# --------------------------------------------------------------------------------

if APP_ENV == 'testing':

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

# --------------------------------------------------------------------------------
#                            PRODUCTION SETTINGS
# --------------------------------------------------------------------------------

if APP_ENV == 'production':

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
