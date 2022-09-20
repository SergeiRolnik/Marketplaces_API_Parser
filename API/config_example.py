# максимальное кол-во товаров можно отправлть в одном запросе
MAX_NUMBER_OF_PRODUCTS = 10000

# максимальное кол-во аккаунтов, которое можно обновить в одном запросе
MAX_NUMBER_OF_ACCOUNTS = 10

# сколько товаров можно в одном запросе отправлять на площадки
NUMBER_OF_PRODUCTS_TO_PROCESS = 100

# данные для подключения к БД Ecom Seller (master_db)
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