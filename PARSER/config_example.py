# данные для подключения к БД Ecom Seller (market_db)
DB_DSN = """
host = rc1b-itt1uqz8cxhs0c3d.mdb.yandexcloud.net
port = 6432
dbname = market_db
user = your_username_here
password = your_password_here
target_session_attrs = read-write
sslmode = verify-full
sslrootcert=root.crt
"""

CHUNK_SIZE = 2000

SLEEP_TIME = 5  # время между запросами в API Озона (сек)

TEST_ACCOUNTS = []  # номера аккаунтов в таблице account_list для тестирования (для продакшн TEST_ACCOUNTS = [])
