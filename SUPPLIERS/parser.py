from ftplib import FTP
import pandas as pd
from loguru import logger
from datetime import date
from concurrent.futures import ThreadPoolExecutor
from SUPPLIERS.connectors import *
from SUPPLIERS.config import *
from shared.db import *

logger.remove()
logger.add(sink='logs/suppliers_logfile.log', format="{time} {level} {message}", level="INFO")


def insert_into_db(table_name: str, dataset: list, supplier_id: int):
    if dataset:
        for row in dataset:
            if 'price' not in row.keys():
                row['price'] = 0
            row['supplier_id'] = supplier_id
            row['date'] = str(date.today())
        table_fields = ['offer_id', 'stock', 'price', 'supplier_id', 'date']
        fields = ','.join(table_fields)
        dataset_fields = list(dataset[0].keys())
        values = ','.join([f'%({value})s' for value in dataset_fields])
        sql = f'INSERT INTO {table_name} ({fields}) VALUES ({values})'
        run_sql_insert_many(sql, dataset)


def delete_duplicate_records_from_suppliers_data():
    table_name = SUPPLIERS_DATA_TABLE_NAME
    partition = SUPPLIERS_DATA_TABLE_NAME_PARTITION
    sql = f'''
        DELETE FROM {table_name} WHERE id IN (SELECT id FROM
        (SELECT id, row_number() OVER(PARTITION BY {partition} ORDER BY id DESC) FROM {table_name}) AS sel_unique
        WHERE row_number >= 2)
        '''
    run_sql_delete(sql)


class Connector:
    def __init__(self, resource_url, supplier_id):
        self.resource_url = resource_url  # URL поставщика откуда загружается информация о товарах
        self.supplier_id = supplier_id    # идентификатор поставщика в таблице suppliers


class FTPConnector(Connector):  # --- ДОРАБОТАТЬ ---
    def __init__(self, user, password, port, timeout, resource_url, supplier_id):
        super().__init__(resource_url, supplier_id)
        self.user = user
        self.password = password
        self.port = port
        self.timeout = timeout

    def connect_to_ftp(self):
        ftp_obj = FTP(self.resource_url)
        ftp_obj.connect(host=self.resource_url, port=self.port, timeout=self.timeout)
        ftp_obj.login(user=self.user, passwd=self.password)
        return ftp_obj

    def get_products_from_supplier(self):  # доработать функцию
        ftp_obj = self.connect_to_ftp()
        file = open('data.xls', 'wb')
        ftp_obj.retrbinary('data.xls', file.write, 1024)
        df = pd.read_excel('data.xls', sheet_name='Sheet1')
        data = [tuple(x) for x in df.to_numpy()]
        file.close()
        ftp_obj.quit()
        return data

    def write_to_db(self):
        pass


class ExcelFileConnector(Connector):
    def __init__(self, sheet_name, fields_mapping, resource_url, supplier_id):
        super().__init__(resource_url, supplier_id)
        self.sheet_name = sheet_name  # название листа в Excel файле
        self.fields_mapping = fields_mapping  # маппинг полей

    def map_data(self, df):  # маппинг полей: API stocks ---> Эксель файл поставщика
        df = df[[self.fields_mapping['offer_id'], self.fields_mapping['stock']]]
        mapped_data = [{'offer_id': row[0], 'stock': row[1]} for i, row in df.iterrows()]
        return mapped_data

    def get_products_from_supplier(self):
        df = pd.read_excel(self.resource_url, sheet_name=self.sheet_name)  # создание объекта DataFrame
        return self.map_data(df)

    def write_to_db(self):
        products = self.get_products_from_supplier()
        insert_into_db('suppliers_data', products, self.supplier_id)


class APIConnector(Connector):
    def __init__(self, url_stocks, url_prices, api_key, supplier_func, resource_url, supplier_id):
        super().__init__(resource_url, supplier_id)
        self.url_stocks = url_stocks
        self.url_prices = url_prices
        self.api_key = api_key  # API-ключ
        self.supplier_func = supplier_func  # имя функции, которая вызывается для обращения в API поставщика

    def get_products_from_supplier(self):
        supplier_func = self.supplier_func
        func_name = globals()[supplier_func]
        products = func_name(self.resource_url, self.url_stocks, self.url_prices, self.api_key)
        return products  # список словарей {'offer_id':..., 'stock':..., 'price':...}

    def write_to_db(self):
        products = self.get_products_from_supplier()
        insert_into_db('suppliers_data', products, self.supplier_id)


def process_supplier_data(supplier: dict):
    supplier_id = supplier['id']
    resource_url = supplier['resource_url']
    connection_method = supplier['connection_method']
    connector = None
    if connection_method == 'api':
        api_key = supplier['api_key']
        supplier_func = supplier['supplier_func']
        url_stocks = supplier['url_stocks']
        url_prices = supplier['url_prices']
        connector = APIConnector(url_stocks, url_prices, api_key, supplier_func, resource_url, supplier_id)
    if connection_method == 'excel':
        fields_mapping = supplier['fields_mapping']
        connector = ExcelFileConnector('Sheet1', fields_mapping, resource_url, supplier_id)
    if connection_method == 'ftp':
        user = supplier['username']
        password = supplier['pwd']
        connector = FTPConnector(user, password, 80, 10, resource_url, supplier_id)  # port=80, timeout=10
    connector.write_to_db()
    return supplier_id


def main():
    suppliers = read_from_suppliers_db()  # получить список поставщиков из таблицы suppliers
    futures = []
    with ThreadPoolExecutor() as executor:
        for supplier in suppliers:  # цикл по поставщикам в разных потоках
            future = executor.submit(process_supplier_data, dict(supplier))  # обработка поставщика в потоке
            futures.append(future)
        response = [future.result() for future in futures]
    print(f'Загрузка остатков и цен поставщиков завершена. Список идентификаторов поставщиков', response)
    delete_duplicate_records_from_suppliers_data()  # удалить дупликаты из таблицы suppliers_data


if __name__ == '__main__':
    main()
