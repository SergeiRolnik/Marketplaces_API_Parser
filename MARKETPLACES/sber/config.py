BASE_URL = 'https://partner.sbermegamarket.ru/api/merchantIntegration/v1/offerService'
BASE_URL_TEST = 'https://partner.goodsteam.tech/api/merchantIntegration/v1/offerService'

# 2.3. Обновление остатков по API
STOCK_UPDATE_URL = BASE_URL + '/stock/update'
STOCK_UPDATE_URL_TEST = BASE_URL_TEST + '/stock/update'

# Рекомендованное количество передаваемых позиций в одном запросе - 300

# Пример запроса
# curl --location --request POST 'https://partner.goodsteam.tech/api/merchantIntegration/v1/offerService/stock/update' \
# --header 'Content-Type: application/json' \
# --data-raw '{
#     "meta": {},
#     "data": {
#         "token": "6D104D16-97E9-44D4-8F9B-01A31D014FBF",
#         "stocks": [
#             {
#                 "offerId": "7",
#                 "quantity": 798
#             }
#         ]
#     }
# }'

# Пример ответа {'success': 1,  'meta': {}, 'data': {}}

# 2.4. Обновление цен по API
PRICE_UPDATE_URL = BASE_URL + '/manualPrice/save'
PRICE_UPDATE_URL_TEST = BASE_URL_TEST + '/manualPrice/save'

# Логика работы обновления цен по api:
# Если в isdeleted установлено значение false, то старое значение не удаляется, а дополнительно записывается новое значение.
# В такой ситуации будет показано две цены.
# Если в параметре установлено значение true, то старое удаляется и показывается только новое значение
# Первое обновление цен по апи должно быть с параметром Isdeleted false всегда. Зачеркнутая цена берётся из тега oldprice в фиде,
# если он есть
# Если передать isDeleted = true, то установленная цена будет сброшена до той, которая передавалась в товарном фиде.

# Пример запроса
# curl --location --request POST 'https://partner.sbermegamarket.ru/api/merchantIntegration/v1/offerService/manualPrice/save' \
# --header 'Content-Type: application/json' \
# --data-raw '{
#     "meta": {},
#     "data": {
#         "token": "4C59E63F-62AF-4A11-B953-EEC7683863DA",
#         "prices": [
#             {
#                 "offerId": "10002179",
#                 "price":2000,
#                 "isDeleted": false
#             }
#         ]
#     }
# }'

# Пример ответа {'success': 1,  'meta': {}, 'data': {}}