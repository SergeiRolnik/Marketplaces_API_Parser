from flask import Flask, request
from flask_restful import Api, Resource, reqparse, abort
import json
from loguru import logger

logger.remove()
logger.add(sink='API/ym_logfile.log', format="{time} {level} {message}", level="INFO")

app = Flask(__name__)
api = Api(app)

parser = reqparse.RequestParser(bundle_errors=True)
# добавление агрументов и валидация данных
parser.add_argument(name="warehouseId", type=int, required=True, help='Параметр не задан или неверный тип данных')
parser.add_argument(name="partnerWarehouseId", type=str) # устаревший параметр, в коде не используется
parser.add_argument(name="skus", type=str, action='append', required=True, help='Список товаров пустой')

class Stocks(Resource):
    def post(self):
        args = parser.parse_args()
        warehouseId = args['warehouseId']
        skus = args['skus']  # список идентификаторов товара sku (то же самое, что offer_id)
        skus_list = []
        response = {'skus': skus_list}  # сюда записываем ответ ЯМ

        # дополнительная валидация данных (если возможно, вынести наверх в parser.add_argument)
        if not 6 < len(str(warehouseId)) < 20:
            abort(400, message='Неверное значение параметра warehouseId')

        # открыть файл с информацией об остатках
        file = open('API/ym_data.json', 'r')
        products = json.load(file)
        # products - список словарей [{'offer_id': 1001, 'stock': 100, 'warehouse_id': 999, 'updated_at': 01/01/01} ... ]
        file.close()

        # выделить только те товары из списка products (загруженный json файл),
        # которые присутствуют в списке товаров ЯМ (skus) и где совпадает указанный в запросе warehouse_id
        valid_products = list(filter(
            lambda product: product['offer_id'] in skus and product['warehouse_id'] == warehouseId, products
        ))

        for product in valid_products:
            items = []
            # для тестирования предполагаем, что есть только один тип доступности единиц товара - FIT
            # если этих типов > 1, на всякий случай делаем цикл
            for type in ['FIT']:

                items.append(
                    {
                        'type': type,  # тип доступности единиц товара: FIT — доступные и зарезервированные под заказы единицы
                        'count': product['stock'], # количество доступных и зарезервированных под заказы единиц
                        "updatedAt": product['updated_at'] # дата и время последнего обновления информации об остатках указанного типа
                    }
                )

            skus_list.append(
                {
                    'sku': product['offer_id'],
                    'warehouseId': product['warehouse_id'],
                    'items': items
                }
            )

        logger.info(f'Запрос выполнен успешно. URL:{request.base_url}')
        return response

api.add_resource(Stocks, "/stocks")

if __name__ == '__main__':
    app.run(debug=True)