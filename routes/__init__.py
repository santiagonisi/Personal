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

def actualizar_estados_obras_por_fecha():
    """Actualiza automáticamente el estado de obras según la fecha de fin estimada."""
    hoy = datetime.now().date()
    cambios = False

    for obra in Obra.query.all():
        estado_actual = obra.estado or 'activa'
        nuevo_estado = estado_actual

        if obra.fecha_fin_estimada:
            try:
                fecha_fin = datetime.strptime(obra.fecha_fin_estimada, '%Y-%m-%d').date()
                nuevo_estado = 'desactiva' if hoy > fecha_fin else 'activa'
            except ValueError:
                continue

        if nuevo_estado != estado_actual:
            obra.estado = nuevo_estado
            cambios = True

    if cambios:
        db.session.commit()

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

        lugar_trabajo = data.get('lugar_trabajo', 'obra')
        if lugar_trabajo not in ['oficina', 'obra', 'planta']:
            return jsonify({'error': 'lugar_trabajo debe ser oficina, obra o planta'}), 400
        
        nuevo = Personal(
            nombre=data['nombre'],
            apellido=data['apellido'],
            email=data.get('email'),
            telefono=data.get('telefono'),
            dni=data.get('dni'),
            lugar_trabajo=lugar_trabajo,
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
    try:
        personal = Personal.query.get(id)
        if not personal:
            return jsonify({'error': 'No encontrado'}), 404

        data = request.json or {}
        if 'lugar_trabajo' in data and data.get('lugar_trabajo') not in ['oficina', 'obra', 'planta']:
            return jsonify({'error': 'lugar_trabajo debe ser oficina, obra o planta'}), 400

        personal.nombre = data.get('nombre', personal.nombre)
        personal.apellido = data.get('apellido', personal.apellido)
        personal.email = data.get('email', personal.email)
        personal.telefono = data.get('telefono', personal.telefono)
        personal.dni = data.get('dni', personal.dni)
        personal.lugar_trabajo = data.get('lugar_trabajo', personal.lugar_trabajo)
        personal.fecha_ingreso = data.get('fecha_ingreso', personal.fecha_ingreso)
        personal.estado = data.get('estado', personal.estado)

        db.session.commit()
        return jsonify({'mensaje': 'Actualizado'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'No se pudo actualizar el empleado: {str(e)}'}), 500

@personal_bp.route('/<int:id>', methods=['DELETE'])
@admin_required
def eliminar_personal(id):
    try:
        personal = Personal.query.get(id)
        if not personal:
            return jsonify({'error': 'No encontrado'}), 404

        asignaciones_count = Asignacion.query.filter_by(personal_id=id).count()
        presentismo_count = Presentismo.query.filter_by(personal_id=id).count()
        ingresos_count = IngresoEgreso.query.filter_by(personal_id=id).count()

        if asignaciones_count or presentismo_count or ingresos_count:
            return jsonify({
                'error': (
                    'No se puede eliminar el empleado porque tiene datos asociados '
                    f'(asignaciones: {asignaciones_count}, presentismo: {presentismo_count}, ingresos/egresos: {ingresos_count}).'
                )
            }), 400

        db.session.delete(personal)
        db.session.commit()
        return jsonify({'mensaje': 'Eliminado'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'No se pudo eliminar el empleado: {str(e)}'}), 500


obras_bp = Blueprint('obras', __name__, url_prefix='/api/obras')

@obras_bp.route('', methods=['GET'])
@obra_or_admin_required
def get_obras():
    actualizar_estados_obras_por_fecha()
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
        responsable=data.get('frente', data.get('responsable'))
    )
    db.session.add(nueva)
    db.session.commit()
    return jsonify({'id': nueva.id, 'mensaje': 'Obra creada'}), 201

@obras_bp.route('/<int:id>', methods=['GET'])
@obra_or_admin_required
def get_obra_id(id):
    actualizar_estados_obras_por_fecha()
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
    obra.responsable = data.get('frente', data.get('responsable', obra.responsable))
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
    asignaciones = Asignacion.query.order_by(Asignacion.fecha_asignacion.desc(), Asignacion.id.desc()).all()
    return jsonify([a.to_dict() for a in asignaciones])

@asignaciones_bp.route('', methods=['POST'])
@obra_or_admin_required
def crear_asignacion():
    try:
        data = request.json or {}

        if not data.get('personal_id') or not data.get('obra_id') or not data.get('fecha_asignacion'):
            return jsonify({'error': 'personal_id, obra_id y fecha_asignacion son requeridos'}), 400

        nueva = Asignacion(
            personal_id=data['personal_id'],
            obra_id=data['obra_id'],
            fecha_asignacion=data['fecha_asignacion'],
            puesto=data.get('puesto'),
            frente=data.get('frente')
        )
        db.session.add(nueva)
        db.session.commit()
        return jsonify({'id': nueva.id, 'mensaje': 'Asignación creada'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'No se pudo crear la asignación: {str(e)}'}), 500

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
    try:
        asignacion = Asignacion.query.get(id)
        if not asignacion:
            return jsonify({'error': 'No encontrado'}), 404

        data = request.json or {}
        asignacion.personal_id = data.get('personal_id', asignacion.personal_id)
        asignacion.obra_id = data.get('obra_id', asignacion.obra_id)
        asignacion.puesto = data.get('puesto', asignacion.puesto)
        asignacion.frente = data.get('frente', asignacion.frente)
        asignacion.fecha_asignacion = data.get('fecha_asignacion', asignacion.fecha_asignacion)
        asignacion.fecha_fin = data.get('fecha_fin', asignacion.fecha_fin)
        asignacion.estado = data.get('estado', asignacion.estado)

        if not asignacion.personal_id or not asignacion.obra_id or not asignacion.fecha_asignacion:
            return jsonify({'error': 'personal_id, obra_id y fecha_asignacion son requeridos'}), 400

        db.session.commit()
        return jsonify({'mensaje': 'Actualizado'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'No se pudo actualizar la asignación: {str(e)}'}), 500

@asignaciones_bp.route('/<int:id>', methods=['DELETE'])
@admin_required
def eliminar_asignacion(id):
    asignacion = Asignacion.query.get(id)
    if not asignacion:
        return jsonify({'error': 'No encontrado'}), 404
    
    db.session.delete(asignacion)
    db.session.commit()
    return jsonify({'mensaje': 'Eliminado'})


@main_bp.route('/api/parte-diario', methods=['GET'])
@obra_or_admin_required
def get_parte_diario():
    obra_id = request.args.get('obra_id', type=int)
    fecha = request.args.get('fecha') or datetime.now().strftime('%Y-%m-%d')

    if not obra_id:
        return jsonify({'error': 'obra_id es requerido'}), 400

    personal_obra = Personal.query.filter_by(lugar_trabajo='obra').order_by(Personal.apellido.asc(), Personal.nombre.asc()).all()
    asignaciones = Asignacion.query.filter_by(obra_id=obra_id, estado='activa').all()
    presentismos = Presentismo.query.filter_by(obra_id=obra_id, fecha=fecha).all()
    ingresos_egresos = IngresoEgreso.query.filter_by(obra_id=obra_id, fecha=fecha).all()

    puesto_por_personal = {a.personal_id: a.puesto for a in asignaciones}
    presentismo_por_personal = {p.personal_id: p for p in presentismos}
    ingreso_por_personal = {i.personal_id: i for i in ingresos_egresos}

    filas = []
    for persona in personal_obra:
        presentismo = presentismo_por_personal.get(persona.id)
        ingreso = ingreso_por_personal.get(persona.id)
        tipo = presentismo.tipo if presentismo else 'ausente_sin_aviso'

        filas.append({
            'personal_id': persona.id,
            'nombre': persona.nombre,
            'apellido': persona.apellido,
            'dni': persona.dni,
            'puesto': puesto_por_personal.get(persona.id),
            'presentismo_id': presentismo.id if presentismo else None,
            'tipo': tipo,
            'en_obra': tipo == 'presente',
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
