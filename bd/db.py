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
    

# # # Vendedores

#Obtener Vendedor
def traer_vendedor():
    vend = db.collection('personal').stream()
    vendedores = []
    for i in vend:
        data = i.to_dict()
        vendedores.append(data)
    return vendedores

# Crear vendedor
def alta_vend(name, lastname, dni, email, phone, username, password):
    
    vend = db.collection('personal')
    
    try:
        # Intenta obtener la coleccion desde la base de datos
        vend.get()
    except  (firebase_admin.exceptions.NotFound, ValueError):
        vend.create()
        vend.create_idex(['usuario'], unique = True)
        vend.create_index(['cedula'], unique = True)
    
    # Crear documento xon id automatico
    vend_document = vend.document()
    
    # Tomar los datos para el documento
    data = {
        'nombre': name,
        'apellido': lastname,
        'cedula': dni,
        'correo': email,
        'telefono': phone,
        'usuario': username,
        'contraseña': password,
    }
    
    # Creamos el documento
    vend_document.create(data)
    
    
# Eliminar vendedor
def eliminar_vend(vend_name):
    query = db.collection('personal').where('usuario', '==', vend_name).get()
    
    for doc in query:
        doc.reference.delete()
        
# Eliminar Vendedor
def update_vend(vend_name, name, lastname, dni, email,phone, username, password):
    query = db.collection('personal').where('usuario', '==', vend_name).get()
    
    for doc in query:
        doc.reference.update({
            'nombre': name,
            'apellido': lastname,
            'cedula': dni,
            'correo': email,
            'telefono': phone,
            'usuario': username,
            'contraseña': password,
        })
        


        
    
    

    
