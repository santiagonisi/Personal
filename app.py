import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__, 
                template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
                static_folder=os.path.join(os.path.dirname(__file__), 'static'))
    
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nomina.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'tu-clave-secreta-aqui'
    app.config['JSON_SORT_KEYS'] = False
    
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Debes iniciar sesión para acceder a esta página'
    
    with app.app_context():
        db.create_all()
        
        # Cargar usuario por ID para Flask-Login
        from models.usuario import Usuario
        
        @login_manager.user_loader
        def load_user(user_id):
            return Usuario.query.get(int(user_id))
    
    from routes import main_bp, personal_bp, obras_bp, asignaciones_bp, presentismo_bp, ingresos_egresos_bp, auth_bp, admin_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(personal_bp)
    app.register_blueprint(obras_bp)
    app.register_blueprint(asignaciones_bp)
    app.register_blueprint(presentismo_bp)
    app.register_blueprint(ingresos_egresos_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    
    return app
