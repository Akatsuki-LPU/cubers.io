""" Main initialization point of the web app. """

from os import environ

from flask import Flask
from flask_assets import Bundle, Environment
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from config import Config

# -------------------------------------------------------------------------------------------------

CUBERS_APP = Flask(__name__)
CUBERS_APP.config.from_object(Config)

CUBERS_APP.secret_key = CUBERS_APP.config['FLASK_SECRET_KEY']

DB = SQLAlchemy(CUBERS_APP)
MIGRATE = Migrate(CUBERS_APP, DB)

ASSETS = Environment(CUBERS_APP)
ASSETS.register({
    'main_js': Bundle(
        'lib/jquery-3.3.1.min.js',
        'lib/popper.min.js',
        'lib/bootstrap.min.js',
        'lib/fitty.min.js',
        'lib/keydrown.min.js',
        output='gen/main.js'),

    'app_js': Bundle(
        'js/app.js',
        output='gen/app.js'
    ),

    'main_css': Bundle(
        'less/cubers_common.less',
        filters="less,cssmin",
        output='gen/main.css'),

    'bootstrap_css': Bundle(
        'lib/bootstrap.min.css',
        output='gen/lib.css'
    )
})

#pylint: disable=W0401
#I don't want to specifically name every route I want to import here
from app.persistence import models
from .routes import *
from .commands import create_new_test_comp
