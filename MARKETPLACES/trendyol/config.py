BASE_URL = 'https://api.trendyol.com/sapigw'
BASE_URL_STAGE = 'https://stageapi.trendyol.com/stagesapigw'
SUPPLIER_ID = ''

API_KEY = ''

PRODUCT_INFO_URL = BASE_URL + '/suppliers/' + SUPPLIER_ID + '/products'
# approved = true

# GET Parameters
# approved	The product is used for approved or unapproved control,Must be true for approved products	boolean
# barcode	Unique barcode must be sent for inquiry	string
# startDate	It fetches the next products from a specific date-Timestamp.	long
# endDate	Bring a previous date from a specific date - Timestamp.	long
# page	Only return information on the specified page	int
# dateQueryType	Date date filter can work on CREATED DATE or LAST_MODIFIED_DATE	string
# size	Specifies the maximum number to list on a page.	int
# supplierId	ID information of the relevant supplier should be sent	long
# onSale	onSale=true must be submitted to list products for sale	boolean
# rejected	rejected=true or false must be submitted to list products that rejected	boolean
# blacklisted	blacklisted=true or false must be submitted to list products that blacklisted	boolean
# brandIds	It should be used to list products with the specified brandId	array

# Sample Service Response
# {
#     "totalElements": 30,
#     "totalPages": 2,
#     "page": 0,
#     "size": 10,
#     "content": [
#         {
#             "id": "000741dbafd0790b3d41cd5cbf575eb5",
#             "approved": true,
#             "productCode": 13622639,
#             "batchRequestId": "a8529b65-27c1-494a-a01c-a791d6a9b135-1529674360",
#             "supplierId": 1234567,
#             "createDateTime": 1525583690416,
#             "lastUpdateDate": 1529587960412,
#             "gender": "M",
#             "brand": "EVEREST",
#             "barcode": "999999999",
#             "title": "Everest Pseb240 240-200 Motorlu Projeksiyon Perdes",
#             "categoryName": "Görüntü Sistemleri Aksesuarları",
#             "productMainId": "PRO M.PRD 240-200 E",
#             "description": "Everest PSEB240 240-200 Motorlu Projeksiyon Perdes",
#             "stockUnitType": "Adet",
#             "quantity": 6,
#             "listPrice": 1335.65,
#             "salePrice": 1293.21,
#             "vatRate": 18,
#             "dimensionalWeight": 0,
#             "stockCode": "0099000",
#             "deliveryDuration": 10, // It will be removed from the body as of October 17
#             "deliveryOption": {
#                  "deliveryDuration": 1,
#                  "fastDeliveryType": "SAME_DAY_SHIPPING|FAST_DELIVERY"
#             }
#             "images": [
#                 {
#                     "url": "https://img-trendyol.mncdn.com/mnresize/1200/1800//Assets/ProductImages/oa/54/1078914/3/8808993855858_1_org_zoom.jpg"
#                 }
#             ],
#             "attributes": [],
#             "variantAttributes": [
#                 {
#                     "attributeName": "Renk",
#                     "attributeValue": "Karışık, Çok Renkli"
#                 }
#             ],
#             "platformListingId": "9876563563cc11231241",
#             "stockId": "523e210e0e3072e307a287c429881f5c",
#             "color": "Karışık, Çok Renkli"
#         }
#             ]
# }

# Product Stock And Price Update
PRICE_AND_STOCK_UPDATE_URL = BASE_URL + '/suppliers/' + SUPPLIER_ID + '/products/price-and-inventory'

# Sample Request Stock & Price Update
# curl --location --request POST 'https://api.trendyol.com/sapigw/suppliers/200300444/products/price-and-inventory' \
# --header 'Authorization: Basic NmF1M3R4NDZMS3ZFYW1ObFJjdkE6blNMblBtdERxZ2R5SGlsVUVPZVc==' \
# --header 'User-Agent: 200300444 - Trendyolsoft' \
# --header 'Content-Type: application/json' \
# --data-raw '{
#   "items": [
#     {
#       "barcode": "8680000000",
#       "quantity": 100,
#       "salePrice": 112.85,
#       "listPrice": 113.85
#     }
#   ]
# }'

# Sample Response
# {
#     "batchRequestId": "fa75dfd5-6ce6-4730-a09e-97563500000-1529854840"
# }

# You can update a maximum of 100 items (sku) in stock-price update transactions

# Check Batchrequest Result
# curl --location --request GET 'https://api.trendyol.com/sapigw/suppliers/200300444/products/batch-requests/56fb618b-bff6-47e5-a249-62e2ab42bc20-1620063393' \
# --header 'Authorization: Basic NmF1M3R4NDZMS3ZFYW1ObFJjdkE6blNMblBtdERxZ2R5SGlsVUVPZVc==' \
# --header 'User-Agent: 200300444 - Trendyolsoft' \