# Personal

Sistema de gestión de personal y empleados para la administración interna de la empresa.

## Stack

- **Backend:** Python + Flask
- **ORM:** Flask-SQLAlchemy
- **Autenticación:** Flask-Login
- **Base de datos:** SQLite
- **Reportes:** ReportLab
- **Planillas:** OpenPyXL
- **Servidor:** Gunicorn

## Estructura del proyecto

```
Personal/
├── models/               # Modelos de datos
├── routes/               # Rutas de autenticación y administración
├── templates/            # Plantillas de la interfaz
├── static/               # CSS, JavaScript y recursos estáticos
├── app.py                # Configuración de la aplicación
├── run.py                # Punto de entrada
├── create_admin.py       # Gestión del usuario administrador
├── __init__.py           # Inicialización del paquete
└── requirements.txt      # Dependencias de Python
```

## Módulos

- **Personal:** administración de empleados y sus datos.
- **Usuarios:** autenticación y control de acceso.
- **Administración:** funciones de gestión para perfiles autorizados.
- **Reportes:** generación de informes de personal.
- **Exportación:** trabajo con planillas de cálculo.
