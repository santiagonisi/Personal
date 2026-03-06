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

def ensure_personal_legajo_column():
    columnas = db.session.execute(text("PRAGMA table_info(personal)")).fetchall()
    nombres_columnas = {columna[1] for columna in columnas}

    if 'legajo' not in nombres_columnas:
        db.session.execute(text("ALTER TABLE personal ADD COLUMN legajo VARCHAR(30)"))
        db.session.commit()

def cleanup_personal_legacy_columns():
    columnas = db.session.execute(text("PRAGMA table_info(personal)")).fetchall()
    nombres_columnas = {columna[1] for columna in columnas}
    columnas_legacy = {'fecha_nacimiento', 'domicilio', 'ciudad', 'provincia', 'codigo_postal'}

    if not (columnas_legacy & nombres_columnas):
        return

    db.session.execute(text("PRAGMA foreign_keys=OFF"))
    db.session.execute(text("DROP TABLE IF EXISTS personal_new"))
    db.session.execute(text("""
        CREATE TABLE personal_new (
            id INTEGER PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL,
            apellido VARCHAR(100) NOT NULL,
            email VARCHAR(100),
            telefono VARCHAR(20),
            dni VARCHAR(20) UNIQUE,
            estado VARCHAR(20) DEFAULT 'activo',
            lugar_trabajo VARCHAR(20) DEFAULT 'obra',
            fecha_ingreso VARCHAR(10),
            fecha_creacion DATETIME
        )
    """))
    db.session.execute(text("""
        INSERT INTO personal_new (
            id, nombre, apellido, email, telefono, dni, estado, lugar_trabajo, fecha_ingreso, fecha_creacion
        )
        SELECT
            id,
            nombre,
            apellido,
            email,
            telefono,
            dni,
            COALESCE(estado, 'activo'),
            CASE
                WHEN lugar_trabajo IN ('oficina', 'obra', 'planta') THEN lugar_trabajo
                ELSE 'obra'
            END,
            fecha_ingreso,
            fecha_creacion
        FROM personal
    """))
    db.session.execute(text("DROP TABLE personal"))
    db.session.execute(text("ALTER TABLE personal_new RENAME TO personal"))
    db.session.execute(text("PRAGMA foreign_keys=ON"))
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
        cleanup_personal_legacy_columns()
        ensure_personal_legajo_column()
        ensure_asignaciones_frente_column()
    
    from routes import main_bp, personal_bp, obras_bp, asignaciones_bp, auth_bp, admin_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(personal_bp)
    app.register_blueprint(obras_bp)
    app.register_blueprint(asignaciones_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    
    return app
