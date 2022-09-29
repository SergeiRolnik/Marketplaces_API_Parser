BASE_URL = 'https://suppliers-api.wildberries.ru'

# получение информации по номенклатурам, их ценам, скидкам и промокодам. Если не указывать фильтры, вернётся весь товар.
URL_WILDBERRIES_INFO = BASE_URL + '/public/api/v1/info'  # GET

# загрузка цен. За раз можно загрузить не более 1000 номенклатур.
URL_WILDBERRIES_PRICES = BASE_URL + '/public/api/v1/prices'  # POST

# получение информации по остаткам (склады ВБ/FBO)
URL_WILDBERRIES_STOCKS_FBO = BASE_URL + '/api/v2/stocks'  # GET, POST, DELETE

# получение информации по остаткам (склады поставщика/FBS)
URL_WILDBERRIES_STOCKS_FBS = 'https://suppliers-stats.wildberries.ru/api/v1/supplier/stocks'

SLEEP_TIME = 5  # время между запросами в API ВБ (сек)

CHUNK_SIZE = 10_000
