from flask_restful import Resource, reqparse, abort
import psycopg2
from shared.config import DB_DSN
from random import randrange


def run_sql(sql: str):
    conn = psycopg2.connect(DB_DSN)
    conn.autocommit = True
    cursor = conn.cursor()
    cursor.execute(sql)
    if sql.find('select') != -1:
        result = cursor.fetchall()
        return result


parser = reqparse.RequestParser()
parser.add_argument('client_id', type=int, required=True)
parser.add_argument('mappings', type=dict, action='append', required=True)


class AddMappings(Resource):
    def post(self):
        data = parser.parse_args()
        client_id = data['client_id']
        mappings = data['mappings']
        if len(mappings) > 1000:  # additional data validation, if necessary
            abort(400, message='List of products is too long')
        master_products = list(mappings[0].values())[0]  # list of master products
        master_product_api_id = list(mappings[0].keys())[0]

        for offer in master_products:
            # check if master product exists in product_list
            sql = f"select product_id, offer_id from product_list " \
                  f"where offer_id ='{offer}' and api_id = '{master_product_api_id}'"
            result = run_sql(sql)

            if result:  # if master product exists in product_list ...
                master_product_id = result[0][0]
                master_offer_id = result[0][1]
                sql = f"select product_id, offer_id from offers_mapping_table " \
                      f"where product_id = '{master_product_id}' and offer_id ='{master_offer_id}'"
                result = run_sql(sql)

                if not result:  # ... but not in mappings, add master product to mappings
                    sql = f"insert into offers_mapping_table(product_id, offer_id, client_id) " \
                          f"values('{master_product_id}', '{master_offer_id}', {client_id})"
                    run_sql(sql)

            else:  # if master product does not exist in product_list, add it to product_list and offers_mapping_table
                # product_id is a random number to ensure uniqueness of product_id/offer_id pair in virtual account
                product_id = randrange(100000)  # maybe, replace it with a serial number
                sql = f"insert into offers_mapping_table(product_id, offer_id, client_id) " \
                      f"values('{product_id}', '{offer}', {client_id})"
                run_sql(sql)
                sql = f"insert into product_list(product_id, offer_id, api_id) " \
                      f"values('{product_id}', '{offer}', '{master_product_api_id}')"
                run_sql(sql)

        # iterate for all slave products and add them to mappings
        for mapping in mappings[1:]:
            slave_products = list(mapping.values())[0]
            slave_product_api_id = list(mapping.keys())[0]

            for i, offer in enumerate(slave_products):
                # check if slave product exists in product_list, if not, skip mapping
                sql = f"select product_id, offer_id from product_list " \
                      f"where offer_id ='{offer}' and api_id = '{slave_product_api_id}'"
                result = run_sql(sql)

                if result:
                    slave_product_id = result[0][0]
                    sql = f"insert into offers_mapping_table(product_id, offer_id, master_id, client_id) " \
                          f"values('{slave_product_id}', '{offer}', '{master_products[i]}', {client_id})"
                    run_sql(sql)

        # remove duplicates
        table_name = 'offers_mapping_table'
        partition = 'product_id, offer_id, master_id, date'
        sql = f'''
        DELETE FROM {table_name} WHERE id IN (SELECT id FROM
        (SELECT id, row_number() OVER(PARTITION BY {partition} ORDER BY id DESC) FROM {table_name}) AS sel_unique
        WHERE row_number >= 2)
        '''
        run_sql(sql)

        return {'message': f'{len(master_products)} mappings have been added to offers_mapping_table'}, 201


class TestAPIAddMappings(Resource):
    def get(self):
        return {'message': 'Add mappings method OK'}
