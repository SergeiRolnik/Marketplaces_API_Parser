import psycopg2
from config import DB_DSN

try:
    connection = psycopg2.connect(DB_DSN)
    cursor = connection.cursor()
    print("Информация о сервере PostgreSQL")
    for key, value in connection.get_dsn_parameters().items():
        print(key, value)
except Exception as error:
    print('Connection error', error)
