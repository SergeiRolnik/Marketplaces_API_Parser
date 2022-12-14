BASE_URL = 'https://developer-docs.amazon.com/sp-api/docs'

PRODUCT_PRICING_URL = BASE_URL + '/product-pricing-api-v0-use-case-guide'

# You can call the getPricing operation to get pricing information based on either a list of SKUs or ASINs.
# This operation accepts a list of up to 20 SKUs or ASINs as a query parameter.

# Query parameters
# Name	Description	Schema
# MarketplaceId	A marketplace identifier. Specifies the marketplace for which prices are returned.	Type: string
# Asins	A list of up to 20 Amazon Standard Identification Number (ASIN) values used to identify items in the given marketplace.
# Max count: 20	Type: array
# Skus	A list of up to 20 seller SKU values used to identify items in the given marketplace.
# Max count: 20	Type: array
# ItemType	Indicates whether ASIN values or seller SKU values are used to identify items. If you specify Asin, the information in the response will be dependent on the list of ASINs you provide in the Asins parameter. If you specify Sku, the information in the response will be dependent on the list of SKUs you provide in the Skus parameter.
# Possible values: Asin, Sku.	Type: enum (ItemType)
# CustomerType	Indicates whether to request pricing information from the point of view of consumer or business buyers. Default is Consumer.	Type: enum (CustomerType)
# OfferType	Indicates whether to request pricing information for the seller's B2C (business-to-consumer) or B2B (business-to-business) offers. Default is B2C.	Type: enum (OfferType)

# Request example using an ASIN
# GET https://sellingpartnerapi-na.amazon.com/products/pricing/v0/price
#   ?MarketplaceId=ATVPDKIKX0DER
#   &Asins=B00V5DG6IQ,B00551Q3CS
#   &ItemType=Asin

# Response Example
# {
#   "payload": [
#     {
#       "status": "Success",
#       "ASIN": "B00V5DG6IQ",
#       "Product": {
#         "Identifiers": {
#           "MarketplaceASIN": {
#             "MarketplaceId": "ATVPDKIKX0DER",
#             "ASIN": "B00V5DG6IQ"
#           },
#           "SKUIdentifier": {
#             "MarketplaceId": "",
#             "SellerId": "",
#             "SellerSKU": ""
#           }
#         },
#         "Offers": [
#           {
#             "BuyingPrice": {
#               "ListingPrice": {
#                 "CurrencyCode": "USD",
#                 "Amount": 10.00
#               },
#               "LandedPrice": {
#                 "CurrencyCode": "USD",
#                 "Amount": 10.00
#               },
#               "Shipping": {
#                 "CurrencyCode": "USD",
#                 "Amount": 0.00
#               }
#             },
#             "RegularPrice": {
#               "CurrencyCode": "USD",
#               "Amount": 10.00
#             },
#             "FulfillmentChannel": "MERCHANT",
#             "ItemCondition": "New",
#             "ItemSubCondition": "New",
#             "SellerSKU": "NABetaASINB00V5DG6IQ"
#           }
#         ]
#       }
#     },
#     {
#       "status": "Success",
#       "ASIN": "B00551Q3CS",
#       "Product": {
#         "Identifiers": {
#           "MarketplaceASIN": {
#             "MarketplaceId": "ATVPDKIKX0DER",
#             "ASIN": "B00551Q3CS"
#           },
#           "SKUIdentifier": {
#             "MarketplaceId": "",
#             "SellerId": "",
#             "SellerSKU": ""
#           }
#         },
#         "Offers": [
#           {
#             "BuyingPrice": {
#               "ListingPrice": {
#                 "CurrencyCode": "USD",
#                 "Amount": 10.00
#               },
#               "LandedPrice": {
#                 "CurrencyCode": "USD",
#                 "Amount": 10.00
#               },
#               "Shipping": {
#                 "CurrencyCode": "USD",
#                 "Amount": 0.00
#               }
#             },
#             "RegularPrice": {
#               "CurrencyCode": "USD",
#               "Amount": 10.00
#             },
#             "FulfillmentChannel": "MERCHANT",
#             "ItemCondition": "New",
#             "ItemSubCondition": "New",
#             "SellerSKU": "NABetaASINB00551Q3CS"
#           }
#         ]
#       }
#     }
#   ]
# }

FBA_INVENTORY_URL = BASE_URL + '/fba/inventory/v1/summaries'

MERCHANT_FULFILLMENT_URL = BASE_URL + '/merchant-fulfillment-api-v0-model'  # !!! ИСПРАВИТЬ