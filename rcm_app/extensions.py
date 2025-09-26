from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager

db = SQLAlchemy(session_options={"expire_on_commit": False})
jwt = JWTManager()

