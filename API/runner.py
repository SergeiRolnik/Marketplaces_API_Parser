from flask import Flask
from flask_restful import Api
import os
from loguru import logger
from shared.models import db
from shared.db import DB_DSN
from API.methods_cost_min_margin import AddPricesToDB, AddMarginsToDB, TestAPI

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

# --- TEST URL ---
api.add_resource(TestAPI, '/test')

# --- PRICES URLS ---
# api.add_resource(CreatePriceRule, '/rules/prices')
# api.add_resource(SendPricesToMarketplaces, '/prices/send/<int:rule_id>')

# --- MAPPING ROUTES ---
# app.add_url_rule('/mappings/<int:account_id>', view_func=MappingOffersView.as_view('view_mappings'), methods=['GET'])
# app.add_url_rule('/mappings', view_func=MappingOffersView.as_view('add_mapping'), methods=['POST'])
# app.add_url_rule('/mappings/<int:mapping_id>', view_func=MappingOffersView.as_view('delete_mapping'), methods=['DELETE'])
# app.add_url_rule('/mappings/<int:mapping_id>', view_func=MappingOffersView.as_view('update_mapping'), methods=['POST', 'PATCH'])

app.run(debug=True)
