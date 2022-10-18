import psycopg2
from config import DB_DSN

try:
    connection = psycopg2.connect(DB_DSN)
    cursor = connection.cursor()
    print('Информация о сервере PostgreSQL')
    for key, value in connection.get_dsn_parameters().items():
        print(key, value)
    sql = "SELECT table_name FROM information_schema.tables WHERE (table_schema = 'public')"
    cursor.execute(sql)
    print('Список доступных таблиц')
    for table in cursor.fetchall():
        print(table)
except Exception as error:
    print('Ошибка подключения', error)
