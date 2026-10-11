from flask_restful import Api

from app.resources.blacklist import BlacklistResource
from app.resources.health import HealthResource


def register_resources(app):
    api = Api(app)
    api.add_resource(HealthResource, "/health")
    api.add_resource(BlacklistResource, "/blacklists")
