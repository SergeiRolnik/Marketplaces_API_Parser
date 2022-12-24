from loguru import logger
from concurrent.futures import ThreadPoolExecutor
from MARKETPLACES.ozon.ozon import OzonApi
from MARKETPLACES.wb.wb import WildberriesApi
from MARKETPLACES.yandex.yandex import YandexMarketApi
from shared.db import run_sql_api, run_sql_account_list, run_sql_api_dict

logger.remove()
logger.add(sink='logs/api_logfile.log', format="{time} {level} {message}", level="INFO")


def create_mp_object(mp_service_attrs: list) -> object:  # service_attrs - [(mp_id, attr_id, attr_value, key_attr), ..]}
    mp_id = mp_service_attrs[0][0]
    attr_values = [item[2] for item in mp_service_attrs]
    if mp_id == 1:  # Ozon
        return OzonApi(attr_values[0], attr_values[1])
    if mp_id == 2:  # YandexMarket
        return YandexMarketApi(attr_values[0], attr_values[1], attr_values[2])
    if mp_id == 3:  # Wildberries (FBO)
        return WildberriesApi(attr_values[0], '')
    if mp_id == 15:  # Wildberries (FBS)
        return WildberriesApi('', attr_values[0])


def apply_filters(products: list, filters: dict) -> list:
    filtered_products = products
    if filters['categories']:
        s_string = str(len(filters['categories']) * '%s,')[0:-1]
        sql = 'SELECT product_id FROM product_list WHERE category_id IN (' + s_string + ')'
        result = run_sql_api(sql, tuple(filters['categories']))
        products_in_categories = list(sum(result, ()))  # преобразеум список кортежей в список
        filtered_products = [product for product in products if product['product_id'] in products_in_categories]
    if filters['brands']:
        pass
    return filtered_products


def apply_actions(products: list, actions: str) -> list:
    if actions == 'set_min_price':
        for product in products:
            if not product['price'] == product['recommended_price']:
                if product['min_price_fbm'] < product['recommended_price']:
                    product['price'] = product['recommended_price'] - 1
                else:
                    product['price'] = product['min_price_fbm']
    products = [{k: v for k, v in product.items() if k == 'product_id' or k == 'price'} for product in products]
    return products


def process_account_data(account: dict) -> dict:
    # account - {'api_id': '1001', 'prices': [{'product_id': 'ABC', 'price': 100}, ...]}
    api_id = account['api_id']
    prices = account['prices']

    # --- find the other service attributes for this api_id ---
    sql = ''' 
    SELECT sa.service_id as mp_id, asd1.attribute_id, asd1.attribute_value, sa.key_attr
    FROM account_service_data asd1
    JOIN service_attr sa ON sa.id = asd1.attribute_id 
    WHERE asd1.account_id = (SELECT asd2.account_id FROM account_service_data asd2 WHERE asd2.attribute_value = %s)
    ORDER BY asd1.attribute_id
    '''
    mp_service_attrs = run_sql_account_list(sql, (api_id, ))
    print('mp_service_attrs', mp_service_attrs)

    mp_id = mp_service_attrs[0][0]

    # --- initialize marketplace class object ---
    mp_object = create_mp_object(mp_service_attrs)
    print(mp_object)
    prices = [{'product_id': int(item['product_id']), 'price': item['price']} for item in prices]
    print('--- > final prices to send to marketplace', prices)

    # --- send data to marketplace to update prices ---
    mp_response = mp_object.update_prices(prices)  # --- TESTING WITHOUT SENDING DATA TO MP ---

    return {'mp_id': mp_id, 'marketplace response': mp_response}


def main():

    futures = []
    with ThreadPoolExecutor() as executor:

        sql = "SELECT id, client_id, rule, target_api_id FROM price_rules WHERE status = 'Active'"
        # sql = "SELECT id, rule, client_id, api_id FROM price_rules WHERE status = 'Active'"
        price_rules = run_sql_api_dict(sql, ())
        for price_rule in price_rules:
            rule_id = price_rule['id']
            rule = price_rule['rule']
            client_id = price_rule['client_id']
            api_id = price_rule['target_api_id']  # yandex market api_id
            print('--- > YandexMarket api_id', api_id, '--- > client_id', client_id)  # --- TESTING ---

            # --- get all products from price_table for given yandex market api_id ---
            sql = "SELECT product_id, price, recommended_price, min_price_fbm " \
                  "FROM price_table_test WHERE api_id=%s and product_id='101869907809'"
            products = run_sql_api_dict(sql, (api_id, ))
            print('products from price_table', products)  # --- TESTING ---
            products = apply_filters(products, rule['filters'])
            products = apply_actions(products, rule['actions'])
            print('products after actions', products)  # --- TESTING ---
            account = {'api_id': api_id, 'prices': products}

            # test = input('OK')

            future = executor.submit(process_account_data, account)
            futures.append(future)

            # --- apply timestamp to the rule ---
            sql = 'UPDATE price_rules SET date=current_date WHERE id=%s'
            run_sql_api(sql, (rule_id, ))

        response = [future.result() for future in futures]
        print('final response', response)  # --- TESTING ---
        rule_ids = [item['id'] for item in price_rules]
        logger.info(f'Rules {rule_ids} have been processed. Response from marketplaces: {response}')


if __name__ == '__main__':
    main()