from flask import Flask
from app.extensions import db, login_manager, mail, migrate
from app.config import Config
import os
from datetime import datetime

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Ensure export directory exists
    os.makedirs(app.config['EXPORT_FOLDER'], exist_ok=True)
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)
    
    login_manager.login_view = 'auth.login'
    
    # Register blueprints
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp)
    
    from app.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    from app.lecturer import bp as lecturer_bp
    app.register_blueprint(lecturer_bp, url_prefix='/lecturer')
    
    from app.class_rep import bp as class_rep_bp
    app.register_blueprint(class_rep_bp, url_prefix='/class_rep')
    
    from app.profile import bp as profile_bp
    app.register_blueprint(profile_bp, url_prefix='/profile')
    
    from app.calendar import bp as calendar_bp
    app.register_blueprint(calendar_bp, url_prefix='/calendar')
    
    # Inject current datetime into template context
    @app.context_processor
    def inject_now():
        return {'now': datetime.now}
    
    # Create database tables and ensure directories exist
    with app.app_context():
        # Ensure export directory exists
        os.makedirs(app.config['EXPORT_FOLDER'], exist_ok=True)
        
        db.create_all()
        
        # Create admin user if not exists
        from app.models import User
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(username='admin', email='admin@mace.edu.zm', role='admin')
            admin.set_password('adminpass')
            db.session.add(admin)
            db.session.commit()
    
    return app

