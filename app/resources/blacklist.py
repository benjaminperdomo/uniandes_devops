from flask import request
from flask_jwt_extended import jwt_required
from flask_restful import Resource
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import BlacklistEntry
from app.schemas import BlacklistCreateSchema

blacklist_create_schema = BlacklistCreateSchema()


class BlacklistResource(Resource):
    method_decorators = [jwt_required()]

    def post(self):
        payload = request.get_json(silent=True)
        try:
            data = blacklist_create_schema.load(payload if payload is not None else {})
        except ValidationError as error:
            return {"message": "Validation error", "errors": error.messages}, 400

        if db.session.execute(db.select(BlacklistEntry.id).filter_by(email=data["email"])).first():
            return {"message": "Email is already in the blacklist"}, 409

        entry = BlacklistEntry(
            email=data["email"],
            app_uuid=data["app_uuid"],
            blocked_reason=data["blocked_reason"],
            request_ip=request.remote_addr,
        )
        db.session.add(entry)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return {"message": "Email is already in the blacklist"}, 409

        return {"message": "Email added to the blacklist", "email": entry.email}, 201


class BlacklistEmailResource(Resource):
    method_decorators = [jwt_required()]

    def get(self, email):
        entry = db.session.execute(
            db.select(BlacklistEntry).filter_by(email=email.strip().lower())
        ).scalar_one_or_none()

        if entry is None:
            return {"is_blacklisted": False, "blocked_reason": None}, 200
        return {"is_blacklisted": True, "blocked_reason": entry.blocked_reason}, 200
