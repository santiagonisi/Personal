import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def create_app():
    app = Flask(__name__, 
                template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
                static_folder=os.path.join(os.path.dirname(__file__), 'static'))
    
    # Configuración
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nomina.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'tu-clave-secreta-aqui'
    app.config['JSON_SORT_KEYS'] = False
    
    # Inicializar BD
    db.init_app(app)
    
    # Crear tablas
    with app.app_context():
        db.create_all()
    
    # Registrar blueprints
    from routes import main_bp, personal_bp, obras_bp, asignaciones_bp, presentismo_bp, ingresos_egresos_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(personal_bp)
    app.register_blueprint(obras_bp)
    app.register_blueprint(asignaciones_bp)
    app.register_blueprint(presentismo_bp)
    app.register_blueprint(ingresos_egresos_bp)
    
    return app
