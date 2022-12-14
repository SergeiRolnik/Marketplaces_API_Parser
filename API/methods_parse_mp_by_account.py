from flask import abort
from flask_restful import Resource, reqparse
import time
from shared.db import run_sql_account_list
from PARSER.main import process_account_data, delete_duplicate_records_from_db

parser = reqparse.RequestParser()
parser.add_argument('account_id', type=int, required=True, help='Номер аккаунта должен быть целым числом')


# --- PARSE STOCKS & PRICES ---
class ParseStocksAndPrices(Resource):
    # @token_required
    def post(self):
        start_time = time.time()
        args = parser.parse_args()
        account_id = args['account_id']
        sql = '''
        SELECT al.id as account_id, al.mp_id, asd.attribute_id, asd.attribute_value, sa.key_attr
        FROM account_list al
        JOIN account_service_data asd ON al.id = asd.account_id
        JOIN service_attr sa ON asd.attribute_id = sa.id
        WHERE al.id = %s AND al.status_1 = 'Active'
        ORDER BY al.id, asd.attribute_id
        '''
        mp_accounts = run_sql_account_list(sql, (str(account_id), ))
        if len(mp_accounts) == 0:
            abort(400, 'Номер аккаунта не существует')
        accounts_groupped = {}
        for account_id, mp_id, attr_id, attr_value, key_attr in mp_accounts:
            accounts_groupped.setdefault((account_id, mp_id), []).append((attr_id, attr_value, key_attr))
        process_account_data(accounts_groupped)
        delete_duplicate_records_from_db()
        # logger.info(f'Работа метода API parse_mp закончена. '
        #             f'Аккаунт {account_id}. '
        #             f'Время выполнения {time.time() - start_time} сек.')
        return {'message': f'Остатки и цены по аккаунту {account_id} собраны и записаны в БД'}


class TestAPIParseMPByAccount(Resource):
    def get(self):
        return {'message': 'Parse marketplaces by account method OK'}
