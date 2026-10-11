from flask_jwt_extended import JWTManager
from flask_marshmallow import Marshmallow
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
ma = Marshmallow()
jwt = JWTManager()


@jwt.unauthorized_loader
def missing_token_callback(reason):
    return {"message": "Missing authorization token", "detail": reason}, 401


@jwt.invalid_token_loader
def invalid_token_callback(reason):
    return {"message": "Invalid authorization token", "detail": reason}, 401
