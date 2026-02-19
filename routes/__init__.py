from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from models import Personal, Obra, Asignacion, Presentismo, IngresoEgreso
from app import db
from functools import wraps
from datetime import datetime, timedelta

def admin_required(f):
    """Decorador para requerir rol de admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.es_admin():
            return jsonify({'error': 'Acceso denegado. Se requieren permisos de administrador.'}), 403
        return f(*args, **kwargs)
    return decorated_function

def obra_or_admin_required(f):
    """Decorador para requerir rol admin o en_obra"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not (current_user.es_admin() or current_user.es_en_obra()):
            return jsonify({'error': 'Acceso denegado. Se requieren permisos de administrador o en_obra.'}), 403
        return f(*args, **kwargs)
    return decorated_function

def calcular_horas_trabajadas(hora_ingreso, hora_egreso):
    """Calcula horas trabajadas a partir de hora de ingreso y egreso."""
    if not hora_ingreso or not hora_egreso:
        return None

    formatos = ['%H:%M', '%H:%M:%S']
    inicio = None
    fin = None

    for formato in formatos:
        try:
            inicio = datetime.strptime(hora_ingreso, formato)
            break
        except ValueError:
            continue

    for formato in formatos:
        try:
            fin = datetime.strptime(hora_egreso, formato)
            break
        except ValueError:
            continue

    if not inicio or not fin:
        return None

    if fin < inicio:
        fin += timedelta(days=1)

    return round((fin - inicio).total_seconds() / 3600, 2)

def asignacion_activa_en_fecha(asignacion, fecha):
    """Retorna True si la asignación está activa en la fecha indicada (YYYY-MM-DD)."""
    if not asignacion or not fecha:
        return False
    if asignacion.estado != 'activa':
        return False
    if asignacion.fecha_asignacion and asignacion.fecha_asignacion > fecha:
        return False
    if asignacion.fecha_fin and asignacion.fecha_fin < fecha:
        return False
    return True

def obtener_asignacion_activa(personal_id, obra_id, fecha):
    """Obtiene una asignación activa de un obrero en una obra para una fecha."""
    asignaciones = Asignacion.query.filter_by(
        personal_id=personal_id,
        obra_id=obra_id,
        estado='activa'
    ).all()

    for asignacion in asignaciones:
        if asignacion_activa_en_fecha(asignacion, fecha):
            return asignacion
    return None

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
    if not current_user.es_admin():
        return redirect(url_for('main.dashboard'))
    return render_template('personal.html')

@main_bp.route('/obras')
@login_required
def obras_page():
    if not current_user.es_admin():
        return redirect(url_for('main.dashboard'))
    return render_template('obras.html')

@main_bp.route('/asignaciones')
@login_required
def asignaciones_page():
    return render_template('asignaciones.html')

@main_bp.route('/presentismo')
@login_required
def presentismo_page():
    return redirect(url_for('main.parte_diario_page'))

@main_bp.route('/ingresos-egresos')
@login_required
def ingresos_egresos_page():
    return redirect(url_for('main.parte_diario_page'))

@main_bp.route('/parte-diario')
@login_required
def parte_diario_page():
    if not (current_user.es_admin() or current_user.es_en_obra()):
        return redirect(url_for('main.dashboard'))
    return render_template('parte_diario.html')

@main_bp.route('/historico-obreros')
@login_required
def historico_obreros_page():
    if not current_user.es_admin():
        return redirect(url_for('main.dashboard'))
    return render_template('historico_obreros.html')


personal_bp = Blueprint('personal', __name__, url_prefix='/api/personal')

@personal_bp.route('', methods=['GET'])
@obra_or_admin_required
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
@obra_or_admin_required
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
@obra_or_admin_required
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
@obra_or_admin_required
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
@obra_or_admin_required
def get_asignaciones():
    asignaciones = Asignacion.query.all()
    return jsonify([a.to_dict() for a in asignaciones])

@asignaciones_bp.route('', methods=['POST'])
@obra_or_admin_required
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
@obra_or_admin_required
def get_asignacion_id(id):
    asignacion = Asignacion.query.get(id)
    if not asignacion:
        return jsonify({'error': 'No encontrado'}), 404
    return jsonify(asignacion.to_dict())

@asignaciones_bp.route('/<int:id>', methods=['PUT'])
@obra_or_admin_required
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
@obra_or_admin_required
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
@obra_or_admin_required
def crear_presentismo():
    data = request.json
    personal_id = data.get('personal_id')
    obra_id = data.get('obra_id')
    fecha = data.get('fecha')
    tipo = data.get('tipo')

    if not personal_id or not obra_id or not fecha or not tipo:
        return jsonify({'error': 'personal_id, obra_id, fecha y tipo son requeridos'}), 400

    if not obtener_asignacion_activa(personal_id, obra_id, fecha):
        return jsonify({'error': 'El obrero no tiene asignación activa en esa obra y fecha'}), 400

    existente = Presentismo.query.filter_by(
        personal_id=personal_id,
        obra_id=obra_id,
        fecha=fecha
    ).first()

    if existente:
        existente.tipo = tipo
        existente.descripcion = data.get('descripcion')
        existente.notas = data.get('notas')
        mensaje = 'Presentismo actualizado'
        presentismo_id = existente.id
    else:
        nuevo = Presentismo(
            personal_id=personal_id,
            obra_id=obra_id,
            fecha=fecha,
            tipo=tipo,
            descripcion=data.get('descripcion'),
            notas=data.get('notas')
        )
        db.session.add(nuevo)
        mensaje = 'Presentismo registrado'

    db.session.commit()
    if existente:
        return jsonify({'id': presentismo_id, 'mensaje': mensaje}), 200
    return jsonify({'id': nuevo.id, 'mensaje': mensaje}), 201

@presentismo_bp.route('/<int:id>', methods=['GET'])
@obra_or_admin_required
def get_presentismo_id(id):
    presentismo = Presentismo.query.get(id)
    if not presentismo:
        return jsonify({'error': 'No encontrado'}), 404
    return jsonify(presentismo.to_dict())

@presentismo_bp.route('/<int:id>', methods=['PUT'])
@obra_or_admin_required
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
@admin_required
def eliminar_presentismo(id):
    presentismo = Presentismo.query.get(id)
    if not presentismo:
        return jsonify({'error': 'No encontrado'}), 404
    
    db.session.delete(presentismo)
    db.session.commit()
    return jsonify({'mensaje': 'Eliminado'})


ingresos_egresos_bp = Blueprint('ingresos_egresos', __name__, url_prefix='/api/ingresos-egresos')

@ingresos_egresos_bp.route('', methods=['GET'])
@obra_or_admin_required
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
@obra_or_admin_required
def crear_ingreso_egreso():
    data = request.json
    personal_id = data.get('personal_id')
    obra_id = data.get('obra_id')
    fecha = data.get('fecha')

    if not personal_id or not obra_id or not fecha:
        return jsonify({'error': 'personal_id, obra_id y fecha son requeridos'}), 400

    if not obtener_asignacion_activa(personal_id, obra_id, fecha):
        return jsonify({'error': 'El obrero no tiene asignación activa en esa obra y fecha'}), 400

    horas_trabajadas = calcular_horas_trabajadas(data.get('hora_ingreso'), data.get('hora_egreso'))
    existente = IngresoEgreso.query.filter_by(
        personal_id=personal_id,
        obra_id=obra_id,
        fecha=fecha
    ).first()

    if existente:
        existente.hora_ingreso = data.get('hora_ingreso')
        existente.hora_egreso = data.get('hora_egreso')
        existente.horas_trabajadas = horas_trabajadas
        existente.notas = data.get('notas')
        mensaje = 'Registro actualizado'
        registro_id = existente.id
    else:
        nuevo = IngresoEgreso(
            personal_id=personal_id,
            obra_id=obra_id,
            fecha=fecha,
            hora_ingreso=data.get('hora_ingreso'),
            hora_egreso=data.get('hora_egreso'),
            horas_trabajadas=horas_trabajadas,
            notas=data.get('notas')
        )
        db.session.add(nuevo)
        mensaje = 'Registro creado'

    db.session.commit()
    if existente:
        return jsonify({'id': registro_id, 'mensaje': mensaje}), 200
    return jsonify({'id': nuevo.id, 'mensaje': mensaje}), 201

@ingresos_egresos_bp.route('/<int:id>', methods=['GET'])
@obra_or_admin_required
def get_ingreso_egreso_id(id):
    registro = IngresoEgreso.query.get(id)
    if not registro:
        return jsonify({'error': 'No encontrado'}), 404
    return jsonify(registro.to_dict())

@ingresos_egresos_bp.route('/<int:id>', methods=['PUT'])
@obra_or_admin_required
def actualizar_ingreso_egreso(id):
    registro = IngresoEgreso.query.get(id)
    if not registro:
        return jsonify({'error': 'No encontrado'}), 404
    
    data = request.json
    hora_ingreso = data.get('hora_ingreso', registro.hora_ingreso)
    hora_egreso = data.get('hora_egreso', registro.hora_egreso)
    registro.hora_ingreso = hora_ingreso
    registro.hora_egreso = hora_egreso
    registro.horas_trabajadas = calcular_horas_trabajadas(hora_ingreso, hora_egreso)
    registro.notas = data.get('notas', registro.notas)
    
    db.session.commit()
    return jsonify({'mensaje': 'Actualizado'})

@ingresos_egresos_bp.route('/<int:id>', methods=['DELETE'])
@admin_required
def eliminar_ingreso_egreso(id):
    registro = IngresoEgreso.query.get(id)
    if not registro:
        return jsonify({'error': 'No encontrado'}), 404
    
    db.session.delete(registro)
    db.session.commit()
    return jsonify({'mensaje': 'Eliminado'})


@main_bp.route('/api/parte-diario', methods=['GET'])
@obra_or_admin_required
def get_parte_diario():
    obra_id = request.args.get('obra_id', type=int)
    fecha = request.args.get('fecha') or datetime.now().strftime('%Y-%m-%d')

    if not obra_id:
        return jsonify({'error': 'obra_id es requerido'}), 400

    asignaciones = Asignacion.query.filter_by(obra_id=obra_id, estado='activa').all()
    presentismos = Presentismo.query.filter_by(obra_id=obra_id, fecha=fecha).all()
    ingresos_egresos = IngresoEgreso.query.filter_by(obra_id=obra_id, fecha=fecha).all()

    presentismo_por_personal = {p.personal_id: p for p in presentismos}
    ingreso_por_personal = {i.personal_id: i for i in ingresos_egresos}

    filas = []
    for asignacion in asignaciones:
        if not asignacion_activa_en_fecha(asignacion, fecha):
            continue

        presentismo = presentismo_por_personal.get(asignacion.personal_id)
        ingreso = ingreso_por_personal.get(asignacion.personal_id)

        filas.append({
            'personal_id': asignacion.personal_id,
            'nombre': asignacion.personal.nombre,
            'apellido': asignacion.personal.apellido,
            'dni': asignacion.personal.dni,
            'puesto': asignacion.puesto,
            'presentismo_id': presentismo.id if presentismo else None,
            'tipo': presentismo.tipo if presentismo else 'presente',
            'descripcion': presentismo.descripcion if presentismo else '',
            'ingreso_egreso_id': ingreso.id if ingreso else None,
            'hora_ingreso': ingreso.hora_ingreso if ingreso else '',
            'hora_egreso': ingreso.hora_egreso if ingreso else '',
            'horas_trabajadas': ingreso.horas_trabajadas if ingreso else None,
            'notas': ingreso.notas if ingreso else ''
        })

    return jsonify({
        'obra_id': obra_id,
        'fecha': fecha,
        'total_obreros': len(filas),
        'filas': filas
    })


@main_bp.route('/api/parte-diario', methods=['POST'])
@obra_or_admin_required
def guardar_parte_diario():
    data = request.json or {}

    obra_id = data.get('obra_id')
    personal_id = data.get('personal_id')
    fecha = data.get('fecha') or datetime.now().strftime('%Y-%m-%d')
    tipo = data.get('tipo')
    descripcion = data.get('descripcion')
    hora_ingreso = data.get('hora_ingreso')
    hora_egreso = data.get('hora_egreso')
    notas = data.get('notas')

    if not obra_id or not personal_id or not tipo:
        return jsonify({'error': 'obra_id, personal_id y tipo son requeridos'}), 400

    if not obtener_asignacion_activa(personal_id, obra_id, fecha):
        return jsonify({'error': 'El obrero no tiene asignación activa en esa obra y fecha'}), 400

    presentismo = Presentismo.query.filter_by(
        obra_id=obra_id,
        personal_id=personal_id,
        fecha=fecha
    ).first()

    if presentismo:
        presentismo.tipo = tipo
        presentismo.descripcion = descripcion
    else:
        presentismo = Presentismo(
            personal_id=personal_id,
            obra_id=obra_id,
            fecha=fecha,
            tipo=tipo,
            descripcion=descripcion,
            notas=''
        )
        db.session.add(presentismo)

    ingreso_egreso = IngresoEgreso.query.filter_by(
        obra_id=obra_id,
        personal_id=personal_id,
        fecha=fecha
    ).first()

    horas_trabajadas = calcular_horas_trabajadas(hora_ingreso, hora_egreso)

    if ingreso_egreso:
        ingreso_egreso.hora_ingreso = hora_ingreso
        ingreso_egreso.hora_egreso = hora_egreso
        ingreso_egreso.horas_trabajadas = horas_trabajadas
        ingreso_egreso.notas = notas
    else:
        ingreso_egreso = IngresoEgreso(
            personal_id=personal_id,
            obra_id=obra_id,
            fecha=fecha,
            hora_ingreso=hora_ingreso,
            hora_egreso=hora_egreso,
            horas_trabajadas=horas_trabajadas,
            notas=notas
        )
        db.session.add(ingreso_egreso)

    db.session.commit()
    return jsonify({'mensaje': 'Parte diario guardado correctamente'})


@main_bp.route('/api/historico-obreros', methods=['GET'])
@admin_required
def get_historico_obreros():
    personal_list = Personal.query.order_by(Personal.apellido.asc(), Personal.nombre.asc()).all()
    historico = []

    for obrero in personal_list:
        asignaciones = Asignacion.query.filter_by(personal_id=obrero.id).all()
        presentismos = Presentismo.query.filter_by(personal_id=obrero.id).all()
        ingresos = IngresoEgreso.query.filter_by(personal_id=obrero.id).all()

        obras = []
        obras_set = set()
        for asignacion in asignaciones:
            if asignacion.obra_id in obras_set:
                continue
            obras_set.add(asignacion.obra_id)
            obras.append({
                'obra_id': asignacion.obra_id,
                'obra_nombre': asignacion.obra.nombre if asignacion.obra else 'Sin obra',
                'fecha_asignacion': asignacion.fecha_asignacion,
                'fecha_fin': asignacion.fecha_fin,
                'puesto': asignacion.puesto
            })

        total_horas = round(sum((ing.horas_trabajadas or 0) for ing in ingresos), 2)
        dias_trabajados = len({ing.fecha for ing in ingresos if ing.fecha})

        presentes = sum(1 for p in presentismos if p.tipo == 'presente')
        no_presentes = sum(1 for p in presentismos if p.tipo != 'presente')
        no_presentes_justificados = sum(1 for p in presentismos if p.tipo in ['ausente_justificado', 'art', 'vacacion', 'franco'])
        no_presentes_sin_justificar = sum(1 for p in presentismos if p.tipo == 'ausente_sin_aviso')

        justificaciones = []
        for p in presentismos:
            if p.tipo == 'presente':
                continue
            justificaciones.append({
                'fecha': p.fecha,
                'obra_nombre': p.obra.nombre if p.obra else 'Sin obra',
                'tipo': p.tipo,
                'detalle': p.descripcion or p.notas or '-'
            })

        historico.append({
            'personal_id': obrero.id,
            'nombre': obrero.nombre,
            'apellido': obrero.apellido,
            'dni': obrero.dni,
            'obras': obras,
            'total_horas': total_horas,
            'dias_trabajados': dias_trabajados,
            'presentes': presentes,
            'no_presentes': no_presentes,
            'no_presentes_justificados': no_presentes_justificados,
            'no_presentes_sin_justificar': no_presentes_sin_justificar,
            'justificaciones': justificaciones
        })

    return jsonify(historico)

from routes.auth import auth_bp
from routes.admin import admin_bp
