from flask import Blueprint

bp = Blueprint('biometric', __name__)

from app.biometric import routes

