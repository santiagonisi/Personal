from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from models.usuario import Usuario

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    """Decorador para requerir rol de admin"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.es_admin():
            flash('Acceso denegado. Se requieren permisos de administrador.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/usuarios', methods=['GET', 'POST'])
@login_required
@admin_required
def usuarios():
    """Página para gestionar usuarios"""
    if request.method == 'POST':
        action = request.form.get('action')
        user_id = request.form.get('user_id')
        
        if action == 'cambiar_rol':
            usuario = Usuario.query.get(user_id)
            if usuario and usuario.id != current_user.id:  # No permitir cambiar el propio rol
                nuevo_rol = request.form.get('rol')
                if nuevo_rol in ['admin', 'en_obra']:
                    usuario.rol = nuevo_rol
                    db.session.commit()
                    flash(f'Rol de {usuario.email} actualizado a {nuevo_rol}', 'success')
        
        elif action == 'activar_desactivar':
            usuario = Usuario.query.get(user_id)
            if usuario and usuario.id != current_user.id:  # No permitir desactivarse a sí mismo
                usuario.activo = not usuario.activo
                db.session.commit()
                estado = 'activado' if usuario.activo else 'desactivado'
                flash(f'{usuario.email} ha sido {estado}', 'success')
        
        return redirect(url_for('admin.usuarios'))
    
    usuarios = Usuario.query.all()
    return render_template('admin/usuarios.html', usuarios=usuarios)

@admin_bp.route('/usuarios/<int:id>/cambiar-password', methods=['POST'])
@login_required
@admin_required
def cambiar_password_usuario(id):
    """API para cambiar contraseña de un usuario"""
    usuario = Usuario.query.get(id)
    if not usuario:
        return jsonify({'error': 'Usuario no encontrado'}), 404
    
    if usuario.id == current_user.id:
        return jsonify({'error': 'No puedes cambiar tu propia contraseña desde aquí'}), 400
    
    try:
        nueva_password = request.json.get('password')
        if not nueva_password or len(nueva_password) < 6:
            return jsonify({'error': 'La contraseña debe tener al menos 6 caracteres'}), 400
        
        usuario.set_password(nueva_password)
        db.session.commit()
        return jsonify({'mensaje': f'Contraseña de {usuario.email} actualizada'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/crear-usuario', methods=['GET', 'POST'])
@login_required
@admin_required
def crear_usuario():
    """Crear un nuevo usuario"""
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        apellido = request.form.get('apellido')
        email = request.form.get('email')
        rol = request.form.get('rol', 'en_obra')
        password = request.form.get('password')
        
        # Validaciones
        if not all([nombre, apellido, email, password]):
            flash('Todos los campos son requeridos', 'danger')
            return redirect(url_for('admin.crear_usuario'))
        
        if len(password) < 6:
            flash('La contraseña debe tener al menos 6 caracteres', 'danger')
            return redirect(url_for('admin.crear_usuario'))
        
        if Usuario.query.filter_by(email=email).first():
            flash(f'El email {email} ya está registrado', 'danger')
            return redirect(url_for('admin.crear_usuario'))
        
        # Crear usuario
        nuevo_usuario = Usuario(
            nombre=nombre,
            apellido=apellido,
            email=email,
            rol=rol,
            activo=True
        )
        nuevo_usuario.set_password(password)
        
        try:
            db.session.add(nuevo_usuario)
            db.session.commit()
            flash(f'Usuario {email} creado exitosamente', 'success')
            return redirect(url_for('admin.usuarios'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear usuario: {str(e)}', 'danger')
            return redirect(url_for('admin.crear_usuario'))
    
    return render_template('admin/crear_usuario.html')
