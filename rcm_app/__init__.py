import os
from datetime import timedelta
from flask import Flask, jsonify
from .extensions import db, jwt
from .settings import AppConfig
from .api import register_blueprints
from sqlalchemy import text


def create_app(config: AppConfig | None = None) -> Flask:
    app = Flask(__name__)

    cfg = config or AppConfig.from_env()
    app.config.update(
        SQLALCHEMY_DATABASE_URI=cfg.database_url,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"implicit_returning": False},
        JWT_SECRET_KEY=cfg.jwt_secret_key,
        JWT_ACCESS_TOKEN_EXPIRES=timedelta(minutes=cfg.jwt_access_minutes),
        JWT_DECODE_LEEWAY=10,
        MAX_CONTENT_LENGTH=cfg.max_upload_bytes,
    )

    db.init_app(app)
    jwt.init_app(app)

    register_blueprints(app)

    # Ensure SQLite directory exists and auto-create tables for local dev
    with app.app_context():
        try:
            uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
            if uri.startswith("sqlite:///"):
                # Extract filesystem path from sqlite URI
                db_path = uri.replace("sqlite:///", "", 1)
                dir_path = os.path.dirname(db_path)
                if dir_path and not os.path.exists(dir_path):
                    os.makedirs(dir_path, exist_ok=True)
            db.create_all()
            _ensure_sqlite_pk_compat()
        except Exception:  # noqa: BLE001
            app.logger.exception("failed to auto-create tables")

    # Log available routes for debugging
    with app.app_context():
        try:
            routes = sorted({
                f"{rule.methods} {rule.rule}" for rule in app.url_map.iter_rules()
            })
            for r in routes:
                app.logger.info("route: %s", r)
        except Exception:  # noqa: BLE001
            pass

    @app.get("/health")
    def health() -> tuple[dict, int]:
        return jsonify({
            "status": "ok",
            "version": os.getenv("APP_VERSION", "0.1.0"),
        }), 200

    return app


def _ensure_sqlite_pk_compat() -> None:
    """Ensure SQLite has INTEGER PRIMARY KEY for autoincrement IDs.

    If legacy schema exists (e.g., BIGINT), drop and recreate tables.
    """
    uri = db.engine.url.render_as_string(hide_password=False)
    if not uri.startswith("sqlite"):
        return
    try:
        res = db.session.execute(text("PRAGMA table_info('claims_master')")).fetchall()
        if not res:
            return
        cols = {row[1]: row for row in res}  # name -> row
        id_row = cols.get("id")
        if not id_row:
            return
        col_type = (id_row[2] or "").upper()
        is_pk = bool(id_row[5])
        if col_type != "INTEGER" or not is_pk:
            # Drop and recreate all tables to fix schema
            from flask import current_app
            current_app.logger.warning("Recreating SQLite tables to ensure INTEGER PRIMARY KEY ids")
            db.drop_all()
            db.create_all()
    except Exception:
        # Best-effort; continue
        pass

