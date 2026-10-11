from datetime import datetime, timezone

from app.extensions import db


def utc_now():
    return datetime.now(timezone.utc)


class BlacklistEntry(db.Model):
    __tablename__ = "blacklists"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    app_uuid = db.Column(db.Uuid, nullable=False)
    blocked_reason = db.Column(db.String(255), nullable=True)
    request_ip = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
