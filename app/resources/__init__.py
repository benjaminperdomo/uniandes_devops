from flask_restful import Api

from app.resources.health import HealthResource


def register_resources(app):
    api = Api(app)
    api.add_resource(HealthResource, "/health")
