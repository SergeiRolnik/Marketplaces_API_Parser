from loguru import logger
import concurrent.futures
from MARKETPLACES.ozon.ozon import OzonApi
from MARKETPLACES.wb.wb import WildberriesApi
from MARKETPLACES.yandex.yandex import YandexMarketApi
from MARKETPLACES.sber.sber import SberApi
from shared.db import run_sql_api

logger.remove()
logger.add(sink='API/logfile.log', format="{time} {level} {message}", level="INFO")


# функция применяет выборку к списку товаров products в соотв. с фильтром
def apply_filter(products: list, filters: dict):

    categories = filters['categories']
    brands = filters['brands']

    if categories:
        s_string = str(len(categories) * '%s,')[0:-1]
        sql = 'SELECT offer_id FROM product_list WHERE category_id IN (' + s_string + ')'
        result = run_sql_api(sql, tuple(categories))
        products_in_categories = list(sum(result, ()))  # преобразеум список кортежей в список
        filtered_products = [product for product in products if product['offer_id'] in products_in_categories]

    elif brands:
        pass

    else:
        pass # код для другого фильтра

    return filtered_products


# функция применяет действие к списку товаров products в соотв. с правилом
def apply_action(products: list, actions: dict):

    account_list = []

    if actions['send_stocks_to_accounts']:  # правило распеределения по % соотношению
        for account in actions['send_stocks_to_accounts']:
            # account - словарь {'account_id': 105, 'warehouse_id': 777, 'percentage': 30}
            products_for_account = [{'offer_id': product['offer_id'], 'stock': int(product['stock'] * account['percentage'] / 100)}
            for product in products]
            account_list.append({
                'account_id': account['account_id'],
                'warehouse_id': account['warehouse_id'],
                'products': products_for_account
            })

    elif actions['if_stock_less_or_equal_than_one_set_stock_at_zero']:  # правило обнуления всех остатков при остатке <= max_stock
        for account in actions['if_stock_less_or_equal_than_one_set_stock_at_zero']:
            # account - словарь {'account_id': 105, 'warehouse_id': 777}
            products_for_account = [{'offer_id': product['offer_id'], 'stock': 0} for product in products]
            account_list.append({
                'account_id': account['account_id'],
                'warehouse_id': account['warehouse_id'],
                'products': products_for_account
            })

    else:  # логика для других правил
        pass

    return account_list
    # на выходе - список словарей:
    # {'account_id': 1001, 'warehouse_id': 777, 'products': [{'offer_id': 'ABC', 'stock': 100}, ...]}


# функция создает соотв. объект класса для отправки запроса на площадку
def create_mp_object(mp_id: int, client_id: str, api_key: str, campaign_id: str):
    if mp_id == 1:
        return OzonApi(client_id, api_key)
    elif mp_id == 2:
        return YandexMarketApi(client_id, api_key, campaign_id)
    elif mp_id == 3:
        return WildberriesApi(client_id, api_key)  # api_key - API-ключ для методов API /suppliers
    elif mp_id == 4:
        return SberApi(api_key)


# отправляем данные по одной партии товаров на разные аккаунты/площадки в разных потоках
def process_account_data(account: dict):

    # account - словарь {'account_id': 1001, 'warehouse_id': 777, 'products': [{'offer_id': 'ABC', 'stock': 100}, ...]}
    account_id = account['account_id']
    warehouse_id = account['warehouse_id']

    # из БД master_db по account_id получаем mp_id, client_id, api_key, campaign_id
    sql = 'SELECT mp_id, client_id_api, api_key, campaigns_id FROM account_list WHERE id=%s'
    result = run_sql_api(sql, (str(account_id), ))
    mp_id, client_id, api_key, campaign_id = result[0]

    # инициализируем объект соотв. класса для обращения в API площадки
    mp_object = create_mp_object(mp_id, client_id, api_key, campaign_id)

    # формируем список товар-количество для отправки в API площадки
    products = [{'offer_id': product['offer_id'], 'stock': product['stock']} for product in account['products']]
    update_stocks_list = mp_object.make_update_stocks_list(products, warehouse_id)

    if mp_id == 2: # для ЯМ
        response = 'Данные по остаткам сохранены в файл ym_data.json'
    else:
        # обращаемся к соотв. методу обновления остатков API МП и возвращаем результат (кроме ЯМ)
        mp_response = mp_object.update_stocks(update_stocks_list)
        # обрабытываем ответ площадки и формируем ответ клиенту (для теста ответ МП оставляем без изменений)
        response = mp_object.process_mp_response(mp_response, account_id, products)

    sql = 'SELECT mp_name FROM marketplaces_list WHERE id=%s'
    result = run_sql_api(sql, (str(mp_id), ))
    mp_name = result[0][0]

    return {'marketplace': mp_name, 'response': response}


def main():

    # достать все необработанные правила из БД (таблица stock_rules)
    sql = 'SELECT rule FROM stock_rules WHERE processed=False'
    result = run_sql_api(sql, tuple())
    rules = result[0]

    if rules: # если в таблице stock_rules есть необработанные правила

        # проходим по всем необработанным правилам в таблице stock_rules
        for rule in rules:

            warehouse_id = rule['warehouse_id'] # номер склада-источника (дополнительный столбец в stock_rules)
            rule_id = rule['rule_id'] # порядковый номер заполненного правила
            rule = rules['rule']

            # достать из БД (таблица stock_by_wh) все товары по указанному warehouse_id (склад-источник)
            sql = 'SELECT offer_id, fbo_present FROM stock_by_wh WHERE warehouse_id=%s'
            products = run_sql_api(sql, (warehouse_id, ))  # products - список кортежей [(offer_id, stock), ..... ]
            # преобразовать список кортежей в список словарей (для удобства обработки)
            products = [{'offer_id': product[0], 'stock': int(product[1])} for product in products]

            # если в правиле указаны фильтры, сделать выборку
            filters = rule['filters']
            for filter in filters.values():
                if len(filter) != 0:
                    products = apply_filter(products, filters)

            response_to_client = [] # здесь будем хранить респонсы МП
            # применить правило/действие(action)
            actions = rule['actions']
            accounts = apply_action(products, actions)
            # accounts - список словарей: {'account_id': 1001, 'warehouse_id': 777, 'products': [{'offer_id': 'ABC', 'stock': 100}, ...]}

            # запускаем многопоточность (отдельный поток для каждого аккаунта)
            with concurrent.futures.ThreadPoolExecutor() as executor:
                results = [executor.submit(process_account_data, account) for account in accounts]
                # получаем результат выполнения функции process_account_data и записываем в ответ клиенту
                for result in results:
                    response_to_client.append(result.result()) # соединяем результаты выполнения всех потоков

            # пометить правило как обработанное
            sql = 'UPDATE stock_rules SET processed=True WHERE id=%s'
            result = run_sql_api(sql, (rule_id, ))

            logger.info(f'Правило {rule_id} успешно обработано') # возможно стоит записать в лог также респонсы МП


if __name__ == '__main__':
    main()
