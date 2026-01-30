from app import db
from datetime import datetime

class Personal(db.Model):
    __tablename__ = 'personal'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100))
    telefono = db.Column(db.String(20))
    dni = db.Column(db.String(20), unique=True)
    fecha_nacimiento = db.Column(db.String(10))
    domicilio = db.Column(db.String(200))
    ciudad = db.Column(db.String(100))
    provincia = db.Column(db.String(100))
    codigo_postal = db.Column(db.String(10))
    estado = db.Column(db.String(20), default='activo')
    fecha_ingreso = db.Column(db.String(10), nullable=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.now)
    
    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'apellido': self.apellido,
            'email': self.email,
            'telefono': self.telefono,
            'dni': self.dni,
            'fecha_nacimiento': self.fecha_nacimiento,
            'domicilio': self.domicilio,
            'ciudad': self.ciudad,
            'provincia': self.provincia,
            'codigo_postal': self.codigo_postal,
            'estado': self.estado,
            'fecha_ingreso': self.fecha_ingreso
        }


class Obra(db.Model):
    __tablename__ = 'obras'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text)
    ubicacion = db.Column(db.String(200))
    fecha_inicio = db.Column(db.String(10))
    fecha_fin_estimada = db.Column(db.String(10))
    estado = db.Column(db.String(20), default='activa')
    responsable = db.Column(db.String(100))
    fecha_creacion = db.Column(db.DateTime, default=datetime.now)
    
    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'descripcion': self.descripcion,
            'ubicacion': self.ubicacion,
            'fecha_inicio': self.fecha_inicio,
            'fecha_fin_estimada': self.fecha_fin_estimada,
            'estado': self.estado,
            'responsable': self.responsable
        }


class Asignacion(db.Model):
    __tablename__ = 'asignaciones'
    
    id = db.Column(db.Integer, primary_key=True)
    personal_id = db.Column(db.Integer, db.ForeignKey('personal.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obras.id'), nullable=False)
    fecha_asignacion = db.Column(db.String(10), nullable=False)
    fecha_fin = db.Column(db.String(10))
    puesto = db.Column(db.String(100))
    salario_diario = db.Column(db.Float)
    estado = db.Column(db.String(20), default='activa')
    fecha_creacion = db.Column(db.DateTime, default=datetime.now)
    
    personal = db.relationship('Personal', backref='asignaciones')
    obra = db.relationship('Obra', backref='asignaciones')
    
    def to_dict(self):
        return {
            'id': self.id,
            'personal_id': self.personal_id,
            'obra_id': self.obra_id,
            'personal_nombre': self.personal.nombre,
            'personal_apellido': self.personal.apellido,
            'obra_nombre': self.obra.nombre,
            'fecha_asignacion': self.fecha_asignacion,
            'fecha_fin': self.fecha_fin,
            'puesto': self.puesto,
            'salario_diario': self.salario_diario,
            'estado': self.estado
        }


class Presentismo(db.Model):
    __tablename__ = 'presentismo'
    
    id = db.Column(db.Integer, primary_key=True)
    personal_id = db.Column(db.Integer, db.ForeignKey('personal.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obras.id'), nullable=False)
    fecha = db.Column(db.String(10), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    descripcion = db.Column(db.Text)
    notas = db.Column(db.Text)
    fecha_creacion = db.Column(db.DateTime, default=datetime.now)
    
    personal = db.relationship('Personal', backref='presentismo')
    obra = db.relationship('Obra', backref='presentismo')
    
    __table_args__ = (db.UniqueConstraint('personal_id', 'obra_id', 'fecha', name='uq_presentismo'),)
    
    def to_dict(self):
        return {
            'id': self.id,
            'personal_id': self.personal_id,
            'obra_id': self.obra_id,
            'personal_nombre': self.personal.nombre,
            'personal_apellido': self.personal.apellido,
            'obra_nombre': self.obra.nombre,
            'fecha': self.fecha,
            'tipo': self.tipo,
            'descripcion': self.descripcion,
            'notas': self.notas
        }


class IngresoEgreso(db.Model):
    __tablename__ = 'ingresos_egresos'
    
    id = db.Column(db.Integer, primary_key=True)
    personal_id = db.Column(db.Integer, db.ForeignKey('personal.id'), nullable=False)
    obra_id = db.Column(db.Integer, db.ForeignKey('obras.id'), nullable=False)
    fecha = db.Column(db.String(10), nullable=False)
    hora_ingreso = db.Column(db.String(5))
    hora_egreso = db.Column(db.String(5))
    horas_trabajadas = db.Column(db.Float)
    notas = db.Column(db.Text)
    fecha_creacion = db.Column(db.DateTime, default=datetime.now)
    
    personal = db.relationship('Personal', backref='ingresos_egresos')
    obra = db.relationship('Obra', backref='ingresos_egresos')
    
    def to_dict(self):
        return {
            'id': self.id,
            'personal_id': self.personal_id,
            'obra_id': self.obra_id,
            'personal_nombre': self.personal.nombre,
            'personal_apellido': self.personal.apellido,
            'obra_nombre': self.obra.nombre,
            'fecha': self.fecha,
            'hora_ingreso': self.hora_ingreso,
            'hora_egreso': self.hora_egreso,
            'horas_trabajadas': self.horas_trabajadas,
            'notas': self.notas
        }
