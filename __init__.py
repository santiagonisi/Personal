import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

db = SQLAlchemy()

def ensure_personal_lugar_trabajo_column():
    columnas = db.session.execute(text("PRAGMA table_info(personal)")).fetchall()
    nombres_columnas = {columna[1] for columna in columnas}

    if 'lugar_trabajo' not in nombres_columnas:
        db.session.execute(
            text("ALTER TABLE personal ADD COLUMN lugar_trabajo VARCHAR(20) DEFAULT 'obra'")
        )
        db.session.execute(
            text("UPDATE personal SET lugar_trabajo = 'obra' WHERE lugar_trabajo IS NULL OR lugar_trabajo = ''")
        )
        db.session.commit()

def ensure_asignaciones_frente_column():
    columnas = db.session.execute(text("PRAGMA table_info(asignaciones)")).fetchall()
    nombres_columnas = {columna[1] for columna in columnas}
    cambios = False

    if 'frente' not in nombres_columnas:
        db.session.execute(text("ALTER TABLE asignaciones ADD COLUMN frente VARCHAR(100)"))
        cambios = True

    if cambios:
        db.session.commit()

def create_app():
    app = Flask(__name__, 
                template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
                static_folder=os.path.join(os.path.dirname(__file__), 'static'))
    
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nomina.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'tu-clave-secreta-aqui'
    app.config['JSON_SORT_KEYS'] = False
    
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
        ensure_personal_lugar_trabajo_column()
        ensure_asignaciones_frente_column()
    
    from routes import main_bp, personal_bp, obras_bp, asignaciones_bp, auth_bp, admin_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(personal_bp)
    app.register_blueprint(obras_bp)
    app.register_blueprint(asignaciones_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    
    return app
