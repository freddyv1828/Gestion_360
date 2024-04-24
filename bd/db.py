import firebase_admin
from firebase_admin import credentials, firestore
from pytz import timezone
from datetime import datetime


cred = credentials.Certificate('config_lacteos.json')

firebase_admin.initialize_app(cred)


db = firestore.client()


# Crear colecciones
def create_admin(name, lastname, dni, email, phone, username, password):
    # referencia de la coleccion a crear
    admin = db.collection('administrador')
    
    
    try:
        # Intenta obtener la coleccion desde la base de datos
        admin.get()
    except  (firebase_admin.exceptions.NotFound, ValueError):
        admin.create()
        admin.create_idex(['usuario'], unique = True)
        admin.create_index(['cedula'], unique = True)
    
    # Crea documento con id automatico
    admin_document = admin.document()
    
    # Toma los datos para el documento
    data = {
        'nombre': name,
        'apellido': lastname,
        'cedula': dni,
        'correo': email,
        'telefono': phone,
        'usuario': username,
        'contraseña': password,
    }
    
    # Crear documento en la colecion administrador
    admin_document.create(data)
    

# Buscar clave de activacion 
def search_clave():
    doc = db.collection('clave_activacion').stream()
    for i in doc:
        data = i.to_dict()
    return data['clave']

# Validacion de entrada o login
def login(username, password):
    doc = db.collection('administrador').stream()
    for i in doc:
        data = i.to_dict()
        if username == data['usuario'] and password == data['contraseña']:
            return data
    
    return False

# Obtener datos de la coleccion para evitar datos duplicados
def datos_register(username, email, dni):
    doc = db.collection('administrador').stream()
    for i in doc:
        data = i.to_dict()
        if username == data['usuario']:
            return 'user'
        
        if email == data['correo']:
            return 'email'
        
        if dni == data['cedula']:
            return 'dni'
    
    return True


# Crear Variables
def create_variables(iva, igtf, dolar_p, dolar_o, user):
    # Crear refetencia de la coleccion
    var = db.collection('variables')
    
    # Crear documento con id automatico
    var_document = var.document()
    
    # Tomar datos para crear documento y hora de venezuela
    
    # Zona horaria
    venezuela_tz = timezone('America/Caracas')
    
    # Fecha y hora
    now_venezuela = datetime.now(venezuela_tz)
    
    # Obtener la fecha
    fecha_venezuela = now_venezuela.date()

    # Obtener la hora
    hora_venezuela = now_venezuela.time()
    
    fecha_str = fecha_venezuela.strftime('%Y-%m-%d')
    hora_str = hora_venezuela.strftime('%H:%M:%S')
    
    data = {
        'iva': iva,
        'igtf': igtf,
        'dolar_p': dolar_p,
        'dolar_o': dolar_o,
        'fecha': fecha_str,
        'hora': hora_str,
        'usurario': user,
    }
    
    # Crear documento
    var_document.create(data)
    

# Obtener variables

def obtener_iva():
    iva = db.collection('variables').stream()
    for i in iva:
        data = i.to_dict()
    return data['iva']

def obtener_igtf():
    igtf = db.collection('variables').stream()
    for i in igtf:
        data = i.to_dict()
    if data:   
        return data['igtf_2']
    else:
        return 0.0

def obtener_igtf_especial():
    igtf = db.collection('variables').stream()
    for i in igtf:
        data = i.to_dict()
    if data:
        return data['igtf']
    else:
        return 0.0
    


