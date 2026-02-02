from flask import Flask
from config import Config
from models import Base
from sql_db import engine
from routes_web import web
from routes_api import api


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # create tables for demo
    Base.metadata.create_all(bind=engine)

    app.register_blueprint(web)
    app.register_blueprint(api)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
