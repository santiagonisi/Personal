from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from models import Personal, Obra, Asignacion, Presentismo, IngresoEgreso
from app import db
from functools import wraps

def admin_required(f):
    """Decorador para requerir rol de admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.es_admin():
            return jsonify({'error': 'Acceso denegado. Se requieren permisos de administrador.'}), 403
        return f(*args, **kwargs)
    return decorated_function

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return redirect(url_for('auth.login'))

@main_bp.route('/dashboard')
@login_required
def dashboard():
    total_personal = Personal.query.count()
    total_obras = Obra.query.count()
    total_asignaciones = Asignacion.query.count()
    return render_template('dashboard.html', 
                         total_personal=total_personal,
                         total_obras=total_obras,
                         total_asignaciones=total_asignaciones)

@main_bp.route('/personal')
@login_required
def personal_page():
    return render_template('personal.html')

@main_bp.route('/obras')
@login_required
def obras_page():
    return render_template('obras.html')

@main_bp.route('/asignaciones')
@login_required
def asignaciones_page():
    return render_template('asignaciones.html')

@main_bp.route('/presentismo')
@login_required
def presentismo_page():
    return render_template('presentismo.html')

@main_bp.route('/ingresos-egresos')
@login_required
def ingresos_egresos_page():
    return render_template('ingresos_egresos.html')


personal_bp = Blueprint('personal', __name__, url_prefix='/api/personal')

@personal_bp.route('', methods=['GET'])
def get_personal():
    try:
        personal = Personal.query.all()
        return jsonify([p.to_dict() for p in personal])
    except Exception as e:
        return jsonify({'error': f'Error al obtener personal: {str(e)}'}), 500

@personal_bp.route('', methods=['POST'])
@admin_required
def crear_personal():
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No se recibieron datos'}), 400
        
        if not data.get('nombre') or not data.get('apellido'):
            return jsonify({'error': 'Nombre y Apellido son requeridos'}), 400
        
        nuevo = Personal(
            nombre=data['nombre'],
            apellido=data['apellido'],
            email=data.get('email'),
            telefono=data.get('telefono'),
            dni=data.get('dni'),
            fecha_nacimiento=data.get('fecha_nacimiento'),
            domicilio=data.get('domicilio'),
            ciudad=data.get('ciudad'),
            provincia=data.get('provincia'),
            codigo_postal=data.get('codigo_postal'),
            fecha_ingreso=data.get('fecha_ingreso', '')
        )
        db.session.add(nuevo)
        db.session.commit()
        return jsonify({'id': nuevo.id, 'mensaje': 'Empleado creado'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@personal_bp.route('/<int:id>', methods=['GET'])
def get_personal_id(id):
    personal = Personal.query.get(id)
    if not personal:
        return jsonify({'error': 'No encontrado'}), 404
    return jsonify(personal.to_dict())

@personal_bp.route('/<int:id>', methods=['PUT'])
@admin_required
def actualizar_personal(id):
    personal = Personal.query.get(id)
    if not personal:
        return jsonify({'error': 'No encontrado'}), 404
    
    data = request.json
    personal.nombre = data.get('nombre', personal.nombre)
    personal.apellido = data.get('apellido', personal.apellido)
    personal.email = data.get('email', personal.email)
    personal.telefono = data.get('telefono', personal.telefono)
    personal.dni = data.get('dni', personal.dni)
    personal.fecha_nacimiento = data.get('fecha_nacimiento', personal.fecha_nacimiento)
    personal.domicilio = data.get('domicilio', personal.domicilio)
    personal.ciudad = data.get('ciudad', personal.ciudad)
    personal.provincia = data.get('provincia', personal.provincia)
    personal.codigo_postal = data.get('codigo_postal', personal.codigo_postal)
    personal.fecha_ingreso = data.get('fecha_ingreso', personal.fecha_ingreso)
    personal.estado = data.get('estado', personal.estado)
    
    db.session.commit()
    return jsonify({'mensaje': 'Actualizado'})

@personal_bp.route('/<int:id>', methods=['DELETE'])
@admin_required
def eliminar_personal(id):
    personal = Personal.query.get(id)
    if not personal:
        return jsonify({'error': 'No encontrado'}), 404
    
    db.session.delete(personal)
    db.session.commit()
    return jsonify({'mensaje': 'Eliminado'})


obras_bp = Blueprint('obras', __name__, url_prefix='/api/obras')

@obras_bp.route('', methods=['GET'])
def get_obras():
    obras = Obra.query.all()
    return jsonify([o.to_dict() for o in obras])

@obras_bp.route('', methods=['POST'])
@admin_required
def crear_obra():
    data = request.json
    nueva = Obra(
        nombre=data['nombre'],
        descripcion=data.get('descripcion'),
        ubicacion=data.get('ubicacion'),
        fecha_inicio=data.get('fecha_inicio'),
        fecha_fin_estimada=data.get('fecha_fin_estimada'),
        responsable=data.get('responsable')
    )
    db.session.add(nueva)
    db.session.commit()
    return jsonify({'id': nueva.id, 'mensaje': 'Obra creada'}), 201

@obras_bp.route('/<int:id>', methods=['GET'])
def get_obra_id(id):
    obra = Obra.query.get(id)
    if not obra:
        return jsonify({'error': 'No encontrado'}), 404
    return jsonify(obra.to_dict())

@obras_bp.route('/<int:id>', methods=['PUT'])
@admin_required
def actualizar_obra(id):
    obra = Obra.query.get(id)
    if not obra:
        return jsonify({'error': 'No encontrado'}), 404
    
    data = request.json
    obra.nombre = data.get('nombre', obra.nombre)
    obra.descripcion = data.get('descripcion', obra.descripcion)
    obra.ubicacion = data.get('ubicacion', obra.ubicacion)
    obra.responsable = data.get('responsable', obra.responsable)
    obra.fecha_inicio = data.get('fecha_inicio', obra.fecha_inicio)
    obra.fecha_fin_estimada = data.get('fecha_fin_estimada', obra.fecha_fin_estimada)
    obra.estado = data.get('estado', obra.estado)
    
    db.session.commit()
    return jsonify({'mensaje': 'Actualizado'})

@obras_bp.route('/<int:id>', methods=['DELETE'])
@admin_required
def eliminar_obra(id):
    obra = Obra.query.get(id)
    if not obra:
        return jsonify({'error': 'No encontrado'}), 404
    
    db.session.delete(obra)
    db.session.commit()
    return jsonify({'mensaje': 'Eliminado'})


asignaciones_bp = Blueprint('asignaciones', __name__, url_prefix='/api/asignaciones')

@asignaciones_bp.route('', methods=['GET'])
def get_asignaciones():
    asignaciones = Asignacion.query.all()
    return jsonify([a.to_dict() for a in asignaciones])

@asignaciones_bp.route('', methods=['POST'])
@admin_required
def crear_asignacion():
    data = request.json
    nueva = Asignacion(
        personal_id=data['personal_id'],
        obra_id=data['obra_id'],
        fecha_asignacion=data['fecha_asignacion'],
        puesto=data.get('puesto'),
        salario_diario=data.get('salario_diario')
    )
    db.session.add(nueva)
    db.session.commit()
    return jsonify({'id': nueva.id, 'mensaje': 'Asignación creada'}), 201

@asignaciones_bp.route('/<int:id>', methods=['GET'])
def get_asignacion_id(id):
    asignacion = Asignacion.query.get(id)
    if not asignacion:
        return jsonify({'error': 'No encontrado'}), 404
    return jsonify(asignacion.to_dict())

@asignaciones_bp.route('/<int:id>', methods=['PUT'])
@admin_required
def actualizar_asignacion(id):
    asignacion = Asignacion.query.get(id)
    if not asignacion:
        return jsonify({'error': 'No encontrado'}), 404
    
    data = request.json
    asignacion.personal_id = data.get('personal_id', asignacion.personal_id)
    asignacion.obra_id = data.get('obra_id', asignacion.obra_id)
    asignacion.puesto = data.get('puesto', asignacion.puesto)
    asignacion.salario_diario = data.get('salario_diario', asignacion.salario_diario)
    asignacion.fecha_asignacion = data.get('fecha_asignacion', asignacion.fecha_asignacion)
    asignacion.fecha_fin = data.get('fecha_fin', asignacion.fecha_fin)
    asignacion.estado = data.get('estado', asignacion.estado)
    
    db.session.commit()
    return jsonify({'mensaje': 'Actualizado'})

@asignaciones_bp.route('/<int:id>', methods=['DELETE'])
@admin_required
def eliminar_asignacion(id):
    asignacion = Asignacion.query.get(id)
    if not asignacion:
        return jsonify({'error': 'No encontrado'}), 404
    
    db.session.delete(asignacion)
    db.session.commit()
    return jsonify({'mensaje': 'Eliminado'})


presentismo_bp = Blueprint('presentismo', __name__, url_prefix='/api/presentismo')

@presentismo_bp.route('', methods=['GET'])
def get_presentismo():
    obra_id = request.args.get('obra_id')
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')
    
    query = Presentismo.query
    if obra_id:
        query = query.filter_by(obra_id=obra_id)
    if fecha_inicio and fecha_fin:
        query = query.filter(Presentismo.fecha.between(fecha_inicio, fecha_fin))
    
    presentismo = query.all()
    return jsonify([p.to_dict() for p in presentismo])

@presentismo_bp.route('', methods=['POST'])
def crear_presentismo():
    data = request.json
    nuevo = Presentismo(
        personal_id=data['personal_id'],
        obra_id=data['obra_id'],
        fecha=data['fecha'],
        tipo=data['tipo'],
        descripcion=data.get('descripcion'),
        notas=data.get('notas')
    )
    db.session.add(nuevo)
    db.session.commit()
    return jsonify({'id': nuevo.id, 'mensaje': 'Presentismo registrado'}), 201

@presentismo_bp.route('/<int:id>', methods=['PUT'])
def actualizar_presentismo(id):
    presentismo = Presentismo.query.get(id)
    if not presentismo:
        return jsonify({'error': 'No encontrado'}), 404
    
    data = request.json
    presentismo.tipo = data.get('tipo', presentismo.tipo)
    presentismo.descripcion = data.get('descripcion', presentismo.descripcion)
    presentismo.notas = data.get('notas', presentismo.notas)
    
    db.session.commit()
    return jsonify({'mensaje': 'Actualizado'})

@presentismo_bp.route('/<int:id>', methods=['DELETE'])
def eliminar_presentismo(id):
    presentismo = Presentismo.query.get(id)
    if not presentismo:
        return jsonify({'error': 'No encontrado'}), 404
    
    db.session.delete(presentismo)
    db.session.commit()
    return jsonify({'mensaje': 'Eliminado'})


ingresos_egresos_bp = Blueprint('ingresos_egresos', __name__, url_prefix='/api/ingresos-egresos')

@ingresos_egresos_bp.route('', methods=['GET'])
def get_ingresos_egresos():
    obra_id = request.args.get('obra_id')
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')
    
    query = IngresoEgreso.query
    if obra_id:
        query = query.filter_by(obra_id=obra_id)
    if fecha_inicio and fecha_fin:
        query = query.filter(IngresoEgreso.fecha.between(fecha_inicio, fecha_fin))
    
    registros = query.all()
    return jsonify([r.to_dict() for r in registros])

@ingresos_egresos_bp.route('', methods=['POST'])
def crear_ingreso_egreso():
    data = request.json
    nuevo = IngresoEgreso(
        personal_id=data['personal_id'],
        obra_id=data['obra_id'],
        fecha=data['fecha'],
        hora_ingreso=data.get('hora_ingreso'),
        hora_egreso=data.get('hora_egreso'),
        horas_trabajadas=data.get('horas_trabajadas'),
        notas=data.get('notas')
    )
    db.session.add(nuevo)
    db.session.commit()
    return jsonify({'id': nuevo.id, 'mensaje': 'Registro creado'}), 201

@ingresos_egresos_bp.route('/<int:id>', methods=['PUT'])
def actualizar_ingreso_egreso(id):
    registro = IngresoEgreso.query.get(id)
    if not registro:
        return jsonify({'error': 'No encontrado'}), 404
    
    data = request.json
    registro.hora_ingreso = data.get('hora_ingreso', registro.hora_ingreso)
    registro.hora_egreso = data.get('hora_egreso', registro.hora_egreso)
    registro.horas_trabajadas = data.get('horas_trabajadas', registro.horas_trabajadas)
    registro.notas = data.get('notas', registro.notas)
    
    db.session.commit()
    return jsonify({'mensaje': 'Actualizado'})

@ingresos_egresos_bp.route('/<int:id>', methods=['DELETE'])
def eliminar_ingreso_egreso(id):
    registro = IngresoEgreso.query.get(id)
    if not registro:
        return jsonify({'error': 'No encontrado'}), 404
    
    db.session.delete(registro)
    db.session.commit()
    return jsonify({'mensaje': 'Eliminado'})

from routes.auth import auth_bp
from routes.admin import admin_bp
