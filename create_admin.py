#!/usr/bin/env python3
"""
Script para crear el primer usuario administrador
Uso: python create_admin.py
"""

import sys
import os
from app import create_app, db
from models.usuario import Usuario

def crear_admin():
    app = create_app()
    
    with app.app_context():
        # Verificar si ya existe un admin
        admin_existente = Usuario.query.filter_by(rol='admin').first()
        if admin_existente:
            print(f"⚠️  Ya existe un administrador: {admin_existente.email}")
            return
        
        print("\n=== Crear Administrador ===\n")
        
        # Solicitar datos
        nombre = input("Nombre: ").strip()
        apellido = input("Apellido: ").strip()
        email = input("Email: ").strip()
        
        # Validar email
        usuario_existente = Usuario.query.filter_by(email=email).first()
        if usuario_existente:
            print(f"❌ Error: El email {email} ya está registrado")
            return
        
        # Solicitar contraseña
        while True:
            password = input("Contraseña (mín 6 caracteres): ").strip()
            if len(password) < 6:
                print("❌ La contraseña debe tener al menos 6 caracteres")
                continue
            
            password_confirm = input("Confirmar contraseña: ").strip()
            if password != password_confirm:
                print("❌ Las contraseñas no coinciden")
                continue
            break
        
        # Crear usuario
        admin = Usuario(
            nombre=nombre,
            apellido=apellido,
            email=email,
            rol='admin',
            activo=True
        )
        admin.set_password(password)
        
        try:
            db.session.add(admin)
            db.session.commit()
            print(f"\n✅ Administrador creado exitosamente!")
            print(f"   Email: {email}")
            print(f"   Nombre: {nombre} {apellido}")
            print(f"   Rol: Administrador\n")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error al crear administrador: {str(e)}")

if __name__ == '__main__':
    crear_admin()
