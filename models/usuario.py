from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    nombre = db.Column(db.String(120), nullable=False)
    apellido = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(50), nullable=False, default='en_obra')  # 'admin' o 'en_obra'
    activo = db.Column(db.Boolean, default=True)
    fecha_creacion = db.Column(db.DateTime, default=db.func.now())
    
    def set_password(self, password):
        """Hashea y guarda la contraseña"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verifica que la contraseña sea correcta"""
        return check_password_hash(self.password_hash, password)
    
    def es_admin(self):
        """Retorna True si el usuario es administrador"""
        return self.rol == 'admin'
    
    def es_en_obra(self):
        """Retorna True si el usuario es de obra"""
        return self.rol == 'en_obra'
    
    def __repr__(self):
        return f'<Usuario {self.email}>'
