from flask import current_app
from flask_restful import Resource


class HealthResource(Resource):
    def get(self):
        return {"status": "ok", "version": current_app.config["APP_VERSION"]}, 200
