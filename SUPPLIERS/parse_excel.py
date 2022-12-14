from flask import Flask, request, jsonify
import pandas as pd
from shared.db import DB_DSN, run_sql_delete
from shared.models import Account
from shared.auth import token_required, app

ALLOWED_FILE_EXTENSIONS = ['xls', 'xlsx']
DB_FIELDS = ['supplier_offer_id', 'mp_offer_id', 'account_id']


def delete_duplicate_records_from_db():
	table_name = 'mapping_offers'
	partition = 'supplier_offer_id, account_id'
	sql = f'''
		DELETE FROM {table_name} WHERE id IN (SELECT id FROM
		(SELECT id, row_number() OVER(PARTITION BY {partition} ORDER BY id DESC) FROM {table_name}) AS sel_unique
		WHERE row_number >= 2)
		'''
	run_sql_delete(sql)


def allowed_file_name(filename):
	return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_FILE_EXTENSIONS


@app.route('/mappings-upload', methods=['POST'])
@token_required
def upload_file(client_id):
	account = Account.query.filter_by(client_id=client_id).filter_by(mp_id=5).first()
	if not account:
		return jsonify({'message': 'У клиента нет виртуального аккаунта'}), 400
	account_id = account.id
	file = request.files['file']
	if not file.filename:
		return jsonify({'message': 'Не выбран файл для загрузки'}), 400
	if not allowed_file_name(file.filename):
		return jsonify({'message': 'Загружаемый файл должен иметь расширение xls или xlsx'}), 400
	df = pd.read_excel(file)
	df['account_id'] = account_id
	if set(DB_FIELDS) != set(list(df)):
		return jsonify({'message': 'Названия столбцов в файле и таблице mapping-offers не совпадают'}), 400
	try:
		df.to_sql('mapping_offers', DB_DSN, if_exists='append', index=False)
		delete_duplicate_records_from_db()
		return jsonify({'message': 'Файл успешно загружен.  Данные записаны в таблицу mapping-offers.'}), 201
	except Exception as error:
		return jsonify({'message': f'Ошибка при записи в базу данных. Описание ошибки: {error}'}), 400


app.run()
