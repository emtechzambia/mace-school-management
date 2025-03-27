from flask import Blueprint

bp = Blueprint('class_rep', __name__)

from app.class_rep import routes

