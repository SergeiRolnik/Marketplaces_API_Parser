from flask import Flask
from flask_restful import Api
import os
from loguru import logger
from shared.models import db
from shared.db import DB_DSN
from API.methods_cost_min_margin import AddPricesToDB, AddMarginsToDB, TestAPICostMargin
from API.methods_parse_mp_by_account import ParseStocksAndPrices, TestAPIParseMPByAccount
from API.methods_add_mappings import AddMappings, TestAPIAddMappings

logger.remove()
logger.add(sink='logs/api_logfile.log', format="{time} {level} {message}", level="INFO")

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = DB_DSN
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
api = Api(app)

# --- ADD COST & MARGIN URLS ---
api.add_resource(AddPricesToDB, '/prices')
api.add_resource(AddMarginsToDB, '/margins')
api.add_resource(TestAPICostMargin, '/test_cost_margin')

# --- PARSE MPS BY ACCOUNT URL ---
api.add_resource(ParseStocksAndPrices, '/parse_mp')
api.add_resource(TestAPIParseMPByAccount, '/test_parse_mp_by_account')

# --- MAPPING ROUTES ---
api.add_resource(AddMappings, '/mappings')
api.add_resource(TestAPIAddMappings, '/test_mappings')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

# if __name__ == '__main__':
#     app.run(debug=True)
