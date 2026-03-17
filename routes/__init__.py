from flask import Blueprint, render_template, request, jsonify, redirect, url_for, make_response
from flask_login import login_required, current_user
from models import Personal, Obra, Presentismo, IngresoEgreso
from app import db
from functools import wraps
from datetime import datetime, timedelta
from sqlalchemy import text

VIATICO_VALOR_CLAVE = 'viatico_valor_base'

def obtener_valor_viatico_base():
    fila = db.session.execute(
        text("SELECT valor FROM configuraciones WHERE clave = :clave"),
        {'clave': VIATICO_VALOR_CLAVE}
    ).fetchone()

    if not fila or fila[0] is None:
        return 0.0

    try:
        return max(0.0, float(fila[0]))
    except (TypeError, ValueError):
        return 0.0

def guardar_valor_viatico_base(valor_base):
    existe = db.session.execute(
        text("SELECT 1 FROM configuraciones WHERE clave = :clave"),
        {'clave': VIATICO_VALOR_CLAVE}
    ).fetchone()

    if existe:
        db.session.execute(
            text("""
                UPDATE configuraciones
                SET valor = :valor, fecha_actualizacion = CURRENT_TIMESTAMP
                WHERE clave = :clave
            """),
            {'clave': VIATICO_VALOR_CLAVE, 'valor': str(valor_base)}
        )
    else:
        db.session.execute(
            text("""
                INSERT INTO configuraciones (clave, valor, fecha_actualizacion)
                VALUES (:clave, :valor, CURRENT_TIMESTAMP)
            """),
            {'clave': VIATICO_VALOR_CLAVE, 'valor': str(valor_base)}
        )

    db.session.commit()

def calcular_monto_viatico_por_registro(presentismo, valor_base, valor_medio):
    nivel_vivienda = (presentismo.viatico_vivienda_nivel or '').strip().lower()
    nivel_traslado = (presentismo.viatico_traslado_nivel or '').strip().lower()
    if nivel_vivienda in {'sin_viatico', 'medio', 'entero'} and nivel_traslado in {'sin_viatico', 'medio', 'entero'}:
        return calcular_monto_viatico_por_niveles(nivel_vivienda, nivel_traslado, valor_base, valor_medio)

    checks_viatico = int(bool(presentismo.viatico_vivienda)) + int(bool(presentismo.viatico_traslado))
    if checks_viatico >= 2:
        return 'entero', valor_base
    if checks_viatico == 1:
        return 'medio', valor_medio
    return 'sin_viatico', 0.0

def normalizar_nivel_viatico(nivel):
    valor = (nivel or '').strip().lower()
    if valor in {'sin_viatico', 'medio', 'entero'}:
        return valor
    return 'sin_viatico'

def calcular_monto_viatico_por_niveles(nivel_vivienda, nivel_traslado, valor_base, valor_medio):
    ranking = {'sin_viatico': 0, 'medio': 1, 'entero': 2}
    nivel_vivienda = normalizar_nivel_viatico(nivel_vivienda)
    nivel_traslado = normalizar_nivel_viatico(nivel_traslado)

    nivel_final = nivel_vivienda
    if ranking[nivel_traslado] > ranking[nivel_final]:
        nivel_final = nivel_traslado

    if nivel_final == 'entero':
        return 'entero', valor_base
    if nivel_final == 'medio':
        return 'medio', valor_medio
    return 'sin_viatico', 0.0

def calcular_monto_viatico_por_checks(viatico_vivienda, viatico_traslado, valor_base, valor_medio):
    checks_viatico = int(bool(viatico_vivienda)) + int(bool(viatico_traslado))
    if checks_viatico >= 2:
        return 'entero', valor_base
    if checks_viatico == 1:
        return 'medio', valor_medio
    return 'sin_viatico', 0.0

def obtener_viatico_congelado_o_calculado(presentismo, valor_base_actual, valor_medio_actual):
    clasificacion = (presentismo.viatico_clasificacion or '').strip().lower()
    if clasificacion in {'entero', 'medio', 'sin_viatico'} and presentismo.viatico_monto is not None:
        return clasificacion, round(float(presentismo.viatico_monto), 2)

    valor_base_referencia = presentismo.viatico_valor_base_aplicado
    if valor_base_referencia is None:
        valor_base_referencia = valor_base_actual
    valor_base_referencia = round(float(valor_base_referencia or 0), 2)
    valor_medio_referencia = round(valor_base_referencia * 0.5, 2)

    return calcular_monto_viatico_por_registro(
        presentismo,
        valor_base_referencia,
        valor_medio_referencia
    )

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

def combinar_niveles_viatico(nivel_actual, nuevo_nivel):
    ranking = {'sin_viatico': 0, 'medio': 1, 'entero': 2}
    nivel_actual = normalizar_nivel_viatico(nivel_actual)
    nuevo_nivel = normalizar_nivel_viatico(nuevo_nivel)
    if ranking[nuevo_nivel] > ranking[nivel_actual]:
        return nuevo_nivel
    return nivel_actual

def obtener_nivel_registro(presentismo, campo_nivel, campo_flag):
    nivel = normalizar_nivel_viatico(getattr(presentismo, campo_nivel, None))
    if nivel != 'sin_viatico':
        return nivel
    return 'medio' if bool(getattr(presentismo, campo_flag, False)) else 'sin_viatico'

def construir_resumen_viaticos(fecha_desde, fecha_hasta, nombre=''):
    valor_viatico_base = obtener_valor_viatico_base()
    valor_medio_viatico = round(valor_viatico_base * 0.5, 2)

    presentismos = Presentismo.query.filter(
        Presentismo.fecha >= fecha_desde,
        Presentismo.fecha <= fecha_hasta
    ).order_by(Presentismo.fecha.asc(), Presentismo.personal_id.asc()).all()

    ingresos = IngresoEgreso.query.filter(
        IngresoEgreso.fecha >= fecha_desde,
        IngresoEgreso.fecha <= fecha_hasta
    ).all()

    horas_por_dia = {}
    for ingreso in ingresos:
        key = (ingreso.personal_id, ingreso.fecha)
        horas_actuales = horas_por_dia.get(key, 0)
        horas_por_dia[key] = round(horas_actuales + float(ingreso.horas_trabajadas or 0), 2)

    registros_por_dia = {}
    for presentismo in presentismos:
        key = (presentismo.personal_id, presentismo.fecha)
        registro = registros_por_dia.get(key)
        if registro is None:
            registro = {
                'personal_id': presentismo.personal_id,
                'nombre': presentismo.personal.nombre if presentismo.personal else '',
                'apellido': presentismo.personal.apellido if presentismo.personal else '',
                'fecha': presentismo.fecha,
                'obras': set(),
                'tipos': set(),
                'presente': False,
                'viatico_vivienda': False,
                'viatico_traslado': False,
                'viatico_vivienda_nivel': 'sin_viatico',
                'viatico_traslado_nivel': 'sin_viatico',
                'valor_viatico_referencia': 0,
            }
            registros_por_dia[key] = registro

        if presentismo.obra and presentismo.obra.nombre:
            registro['obras'].add(presentismo.obra.nombre)
        registro['tipos'].add(presentismo.tipo or '')
        registro['presente'] = registro['presente'] or presentismo.tipo == 'presente'
        registro['viatico_vivienda'] = registro['viatico_vivienda'] or bool(presentismo.viatico_vivienda)
        registro['viatico_traslado'] = registro['viatico_traslado'] or bool(presentismo.viatico_traslado)
        registro['viatico_vivienda_nivel'] = combinar_niveles_viatico(
            registro['viatico_vivienda_nivel'],
            obtener_nivel_registro(presentismo, 'viatico_vivienda_nivel', 'viatico_vivienda')
        )
        registro['viatico_traslado_nivel'] = combinar_niveles_viatico(
            registro['viatico_traslado_nivel'],
            obtener_nivel_registro(presentismo, 'viatico_traslado_nivel', 'viatico_traslado')
        )

        valor_base_registro = presentismo.viatico_valor_base_aplicado
        if valor_base_registro is None:
            valor_base_registro = valor_viatico_base
        registro['valor_viatico_referencia'] = round(
            max(float(registro['valor_viatico_referencia'] or 0), float(valor_base_registro or 0)),
            2
        )

    resumen = {}
    dias_ordenados = sorted(
        registros_por_dia.values(),
        key=lambda item: ((item.get('apellido') or ''), (item.get('nombre') or ''), (item.get('fecha') or ''))
    )

    for registro in dias_ordenados:
        key = registro['personal_id']
        if key not in resumen:
            resumen[key] = {
                'personal_id': registro['personal_id'],
                'nombre': registro['nombre'],
                'apellido': registro['apellido'],
                'dias_con_registro': 0,
                'dias_presente': 0,
                'dias_viatico_vivienda': 0,
                'dias_viatico_traslado': 0,
                'dias_viatico_entero': 0,
                'dias_viatico_medio': 0,
                'dias_sin_viatico': 0,
                'horas_totales': 0,
                'total_viatico': 0,
                'fecha_ultimo_registro': '',
                'valor_viatico_referencia': 0,
                'detalles': []
            }

        item = resumen[key]
        item['dias_con_registro'] += 1
        if registro['presente']:
            item['dias_presente'] += 1
        if registro['viatico_vivienda']:
            item['dias_viatico_vivienda'] += 1
        if registro['viatico_traslado']:
            item['dias_viatico_traslado'] += 1

        valor_base_referencia = round(float(registro['valor_viatico_referencia'] or valor_viatico_base), 2)
        valor_medio_referencia = round(valor_base_referencia * 0.5, 2)
        clasificacion, monto_viatico = calcular_monto_viatico_por_niveles(
            registro['viatico_vivienda_nivel'],
            registro['viatico_traslado_nivel'],
            valor_base_referencia,
            valor_medio_referencia
        )

        if clasificacion == 'entero':
            item['dias_viatico_entero'] += 1
        elif clasificacion == 'medio':
            item['dias_viatico_medio'] += 1
        else:
            item['dias_sin_viatico'] += 1

        horas = horas_por_dia.get((registro['personal_id'], registro['fecha']), 0)
        item['horas_totales'] = round(item['horas_totales'] + horas, 2)
        item['total_viatico'] = round(item['total_viatico'] + monto_viatico, 2)

        if registro['fecha'] and registro['fecha'] >= (item['fecha_ultimo_registro'] or ''):
            item['fecha_ultimo_registro'] = registro['fecha']
            item['valor_viatico_referencia'] = valor_base_referencia

        obras = sorted(obra for obra in registro['obras'] if obra)
        tipos = sorted(tipo for tipo in registro['tipos'] if tipo)
        item['detalles'].append({
            'fecha': registro['fecha'],
            'obra_nombre': ' / '.join(obras) if obras else 'Sin obra',
            'obras': obras,
            'tipo': ' / '.join(tipos),
            'tipos': tipos,
            'viatico_vivienda': registro['viatico_vivienda'],
            'viatico_traslado': registro['viatico_traslado'],
            'viatico_vivienda_nivel': registro['viatico_vivienda_nivel'],
            'viatico_traslado_nivel': registro['viatico_traslado_nivel'],
            'horas_trabajadas': horas,
            'clasificacion_formula': clasificacion,
            'monto_viatico': monto_viatico,
            'valor_viatico_referencia': valor_base_referencia
        })

    data = list(resumen.values())
    if nombre:
        data = [
            item for item in data
            if nombre in f"{(item.get('nombre') or '').lower()} {(item.get('apellido') or '').lower()}"
        ]

    data.sort(key=lambda item: ((item.get('apellido') or ''), (item.get('nombre') or '')))

    return {
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'nombre': nombre,
        'valor_viatico_base': valor_viatico_base,
        'valor_medio_viatico': valor_medio_viatico,
        'total_empleados': len(data),
        'items': data
    }

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
    return render_template('dashboard.html', 
                         total_personal=total_personal,
                         total_obras=total_obras)

@main_bp.route('/personal')
@login_required
def personal_page():
    if not current_user.es_admin():
        return redirect(url_for('main.dashboard'))
    return render_template('personal.html')

@main_bp.route('/obras')
@login_required
def obras_page():
    if not (current_user.es_admin() or current_user.es_en_obra()):
        return redirect(url_for('main.dashboard'))
    return render_template('obras.html')

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

@main_bp.route('/viaticos')
@login_required
def viaticos_page():
    if not current_user.es_admin():
        return redirect(url_for('main.dashboard'))
    return render_template('viaticos.html')


@main_bp.route('/api/viaticos/configuracion', methods=['GET', 'PUT'])
@admin_required
def viaticos_configuracion():
    if request.method == 'GET':
        valor_base = obtener_valor_viatico_base()
        valor_medio = round(valor_base * 0.5, 2)
        return jsonify({
            'valor_viatico_base': valor_base,
            'valor_medio_viatico': valor_medio
        })

    data = request.json or {}
    valor_base = data.get('valor_viatico_base')

    try:
        valor_base = round(float(valor_base), 2)
    except (TypeError, ValueError):
        return jsonify({'error': 'valor_viatico_base debe ser numérico'}), 400

    if valor_base < 0:
        return jsonify({'error': 'valor_viatico_base no puede ser negativo'}), 400

    guardar_valor_viatico_base(valor_base)
    return jsonify({
        'ok': True,
        'valor_viatico_base': valor_base,
        'valor_medio_viatico': round(valor_base * 0.5, 2)
    })


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

        legajo = (data.get('legajo') or '').strip() or None
        
        nuevo = Personal(
            legajo=legajo,
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
        if 'legajo' in data:
            personal.legajo = (data.get('legajo') or '').strip() or None
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

        presentismo_count = Presentismo.query.filter_by(personal_id=id).count()
        ingresos_count = IngresoEgreso.query.filter_by(personal_id=id).count()

        if presentismo_count or ingresos_count:
            return jsonify({
                'error': (
                    'No se puede eliminar el empleado porque tiene datos asociados '
                    f'(presentismo: {presentismo_count}, ingresos/egresos: {ingresos_count}).'
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


@main_bp.route('/api/parte-diario', methods=['GET'])
@obra_or_admin_required
def get_parte_diario():
    obra_id = request.args.get('obra_id', type=int)
    fecha = request.args.get('fecha') or datetime.now().strftime('%Y-%m-%d')

    if not obra_id:
        return jsonify({'error': 'obra_id es requerido'}), 400

    personal_obra = Personal.query.filter_by(lugar_trabajo='obra').order_by(Personal.apellido.asc(), Personal.nombre.asc()).all()
    presentismos = Presentismo.query.filter_by(obra_id=obra_id, fecha=fecha).all()
    ingresos_egresos = IngresoEgreso.query.filter_by(obra_id=obra_id, fecha=fecha).all()

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
            'puesto': None,
            'presentismo_id': presentismo.id if presentismo else None,
            'tipo': tipo,
            'en_obra': tipo == 'presente',
            'viatico_vivienda': bool(presentismo.viatico_vivienda) if presentismo else False,
            'viatico_traslado': bool(presentismo.viatico_traslado) if presentismo else False,
            'viatico_vivienda_nivel': (presentismo.viatico_vivienda_nivel if presentismo else 'sin_viatico') or 'sin_viatico',
            'viatico_traslado_nivel': (presentismo.viatico_traslado_nivel if presentismo else 'sin_viatico') or 'sin_viatico',
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
    viatico_vivienda_nivel = normalizar_nivel_viatico(data.get('viatico_vivienda_nivel'))
    viatico_traslado_nivel = normalizar_nivel_viatico(data.get('viatico_traslado_nivel'))
    viatico_vivienda = viatico_vivienda_nivel != 'sin_viatico'
    viatico_traslado = viatico_traslado_nivel != 'sin_viatico'
    valor_viatico_base = obtener_valor_viatico_base()
    valor_medio_viatico = round(valor_viatico_base * 0.5, 2)
    clasificacion_viatico, monto_viatico = calcular_monto_viatico_por_niveles(
        viatico_vivienda_nivel,
        viatico_traslado_nivel,
        valor_viatico_base,
        valor_medio_viatico
    )

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
        presentismo.viatico_vivienda = viatico_vivienda
        presentismo.viatico_traslado = viatico_traslado
        presentismo.viatico_vivienda_nivel = viatico_vivienda_nivel
        presentismo.viatico_traslado_nivel = viatico_traslado_nivel
        presentismo.viatico_clasificacion = clasificacion_viatico
        presentismo.viatico_valor_base_aplicado = valor_viatico_base
        presentismo.viatico_monto = monto_viatico
    else:
        presentismo = Presentismo(
            personal_id=personal_id,
            obra_id=obra_id,
            fecha=fecha,
            tipo=tipo,
            viatico_vivienda=viatico_vivienda,
            viatico_traslado=viatico_traslado,
            viatico_vivienda_nivel=viatico_vivienda_nivel,
            viatico_traslado_nivel=viatico_traslado_nivel,
            viatico_clasificacion=clasificacion_viatico,
            viatico_valor_base_aplicado=valor_viatico_base,
            viatico_monto=monto_viatico,
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
        presentismos = Presentismo.query.filter_by(personal_id=obrero.id).all()
        ingresos = IngresoEgreso.query.filter_by(personal_id=obrero.id).all()

        obras_por_id = {}

        for p in presentismos:
            if not p.obra_id:
                continue
            entry = obras_por_id.setdefault(p.obra_id, {'fechas': set()})
            if p.fecha:
                entry['fechas'].add(p.fecha)

        for ing in ingresos:
            if not ing.obra_id:
                continue
            entry = obras_por_id.setdefault(ing.obra_id, {'fechas': set()})
            if ing.fecha:
                entry['fechas'].add(ing.fecha)

        obras = []
        for obra_id, data_obra in obras_por_id.items():
            obra = Obra.query.get(obra_id)
            fechas = sorted([f for f in data_obra.get('fechas', set()) if f])
            fecha_desde = fechas[0] if fechas else ''
            fecha_hasta = fechas[-1] if len(fechas) > 1 else ''

            obras.append({
                'obra_id': obra_id,
                'obra_nombre': obra.nombre if obra else 'Sin obra',
                'fecha_asignacion': fecha_desde,
                'fecha_fin': fecha_hasta,
                'puesto': None,
                'frente': obra.responsable if obra else None
            })

        obras.sort(key=lambda x: x.get('fecha_asignacion') or '', reverse=True)

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

        justificaciones.sort(key=lambda x: x.get('fecha') or '', reverse=True)

        historico.append({
            'personal_id': obrero.id,
            'nombre': obrero.nombre,
            'apellido': obrero.apellido,
            'dni': obrero.dni,
            'lugar_trabajo': obrero.lugar_trabajo,
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


@main_bp.route('/api/viaticos/resumen', methods=['GET'])
@admin_required
def get_viaticos_resumen():
    fecha_desde = request.args.get('fecha_desde')
    fecha_hasta = request.args.get('fecha_hasta')
    nombre = (request.args.get('nombre') or '').strip().lower()

    if not fecha_desde or not fecha_hasta:
        return jsonify({'error': 'fecha_desde y fecha_hasta son requeridos'}), 400

    if fecha_desde > fecha_hasta:
        return jsonify({'error': 'fecha_desde no puede ser mayor a fecha_hasta'}), 400

    return jsonify(construir_resumen_viaticos(fecha_desde, fecha_hasta, nombre))


@main_bp.route('/api/viaticos/resumen.pdf', methods=['GET'])
@admin_required
def get_viaticos_resumen_pdf():
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError:
        return jsonify({'error': 'Falta dependencia reportlab para exportar PDF'}), 500

    fecha_desde = request.args.get('fecha_desde')
    fecha_hasta = request.args.get('fecha_hasta')
    nombre = (request.args.get('nombre') or '').strip().lower()

    if not fecha_desde or not fecha_hasta:
        return jsonify({'error': 'fecha_desde y fecha_hasta son requeridos'}), 400

    if fecha_desde > fecha_hasta:
        return jsonify({'error': 'fecha_desde no puede ser mayor a fecha_hasta'}), 400

    resumen = construir_resumen_viaticos(fecha_desde, fecha_hasta, nombre)
    valor_viatico_base = resumen['valor_viatico_base']
    data = resumen['items']

    if len(data) == 0:
        return jsonify({'error': 'No hay datos para exportar en ese rango'}), 404

    import io
    import zipfile
    import re

    fecha_descarga = datetime.now().strftime('%d/%m/%Y')

    def slugify_filename(texto):
        limpio = re.sub(r'[^A-Za-z0-9_-]+', '_', (texto or '').strip())
        return limpio.strip('_') or 'empleado'

    def generar_pdf_empleado(item):
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        y = height - 40

        nombre_completo = f"{item.get('nombre', '')} {item.get('apellido', '')}".strip()

        c.setTitle(f'Viatico_{nombre_completo}')
        c.setFont('Helvetica-Bold', 12)
        c.drawString(40, y, nombre_completo)
        c.setFont('Helvetica', 10)
        c.drawRightString(width - 40, y, f'Fecha: {fecha_descarga}')
        y -= 18

        c.setFont('Helvetica', 10)
        c.drawString(40, y, f'Periodo: {fecha_desde} a {fecha_hasta}')
        y -= 22

        c.setFont('Helvetica-Bold', 11)
        c.drawString(40, y, 'Desglose')
        y -= 16

        c.setFont('Helvetica', 10)
        c.drawString(40, y, f'Dias trabajados: {item.get("dias_presente", 0)}')
        y -= 16
        c.drawString(40, y, f'Hs trabajadas: {item.get("horas_totales", 0)}')
        y -= 16

        valor_viatico_referencia = item.get('valor_viatico_referencia', valor_viatico_base)
        c.drawString(40, y, f'Valor viatico a la fecha: ${valor_viatico_referencia:.2f}')
        y -= 16

        c.drawString(40, y, f'Dias viatico entero: {item.get("dias_viatico_entero", 0)}')
        y -= 16
        c.drawString(40, y, f'Dias viatico medio: {item.get("dias_viatico_medio", 0)}')
        y -= 16
        c.drawString(40, y, f'Dias sin viatico: {item.get("dias_sin_viatico", 0)}')
        y -= 24

        c.setFont('Helvetica-Bold', 11)
        c.drawString(40, y, f'Total viatico (sumatoria): ${item.get("total_viatico", 0):.2f}')

        c.save()
        buffer.seek(0)
        return buffer.getvalue()

    archivos = []
    fecha_archivo = fecha_hasta
    for item in data:
        apellido = slugify_filename(item.get('apellido', '')).upper()
        nombre_archivo = slugify_filename(item.get('nombre', '')).lower()
        archivo_pdf = f'{fecha_archivo}-{apellido}-{nombre_archivo}.pdf'
        archivos.append((archivo_pdf, generar_pdf_empleado(item)))

    if len(archivos) == 1:
        nombre_archivo, contenido = archivos[0]
        response = make_response(contenido)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={nombre_archivo}'
        return response

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode='w', compression=zipfile.ZIP_DEFLATED) as zip_file:
        for nombre_archivo, contenido in archivos:
            zip_file.writestr(nombre_archivo, contenido)

    zip_buffer.seek(0)
    response = make_response(zip_buffer.getvalue())
    response.headers['Content-Type'] = 'application/zip'
    response.headers['Content-Disposition'] = f'attachment; filename=viaticos_{fecha_desde}_a_{fecha_hasta}.zip'
    return response

from routes.auth import auth_bp
from routes.admin import admin_bp
