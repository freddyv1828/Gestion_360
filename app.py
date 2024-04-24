from flask import Flask, render_template, request, flash, redirect, url_for, session
from bd.db import create_admin, search_clave, login, datos_register, obtener_iva, obtener_igtf, obtener_igtf_especial
from scrapper.scrapping import obtener_valor_dolar




# Instancia de la aplicacion
app = Flask(__name__)
app.config['SECRET_KEY'] ='secret!'


# Routers
# main
@app.route('/', methods = ['GET', 'POST'])
def index():
    if request.method == 'GET':
        return render_template('index.html')
    
    # Entrada o login a la app
    if request.method == 'POST':
        # Se toman los valores de los cmapos
        username = request.form['username']
        password = request.form['password']
        rol = request.form['rol']
        
        # Caso rol = Administrador
        if rol == 'administrador':
            # Valoidar qye los campos no esten vacios
            if username != '' and password != '':
                logged = login(username, password)
                if logged != False:
                    session = logged
                    iva = obtener_iva()
                    igtf = obtener_igtf()
                    dolar = obtener_valor_dolar()
                    igtf_especial = obtener_igtf_especial()
                    context = {
                        'iva': iva,
                        'igtf': igtf,
                        'dolar': dolar,
                        'igtf_especial': igtf_especial
                    } 
                    return render_template('principal.html', session= session, context=context)
                else:
                    flash('Usuario o conytraseña incorrecta', 'error')
                    return render_template('index.html')
# Register
@app.route('/register', methods =['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')
    
    if request.method == 'POST':
        # Tomamos los valores del formulario de registro
        name = request.form['name']
        lastname = request.form['lastname']
        dni = request.form['dni']
        phone = request.form['phone']
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']
        clave_acti = request.form['clave']
        
        # Buscar la clave de activacion en la coleccion de firebase
        doc = search_clave()
        
        # Validar si la clave existe
        if doc == clave_acti:
            if name != '' and lastname != '' and dni != '' and phone != '' and email != '' and username != '' and password != '':
                logged = datos_register(username, email, dni)
                if logged == True:
                    create_admin(name, lastname, dni, email, phone, username, password)
                    flash('Cuenta de administrador creada exitosamente!', 'success')
                    return render_template('index.html')
                
                if logged == 'user':
                    flash('El nombre de usuario ya se encuentra en uso', 'error')
                    return render_template('register.html')
                
                if logged == 'email':
                    flash('El correo electronico ya se encuentra en uso', 'error')
                    return render_template('register.html')
                
                if logged == 'dni':
                    flash('El numero de documento ya se encuentra asigando a un usuario', 'error')
                    return render_template('register.html')
                
            else:
                flash('Todos los campos deben estar completados', 'error')
                return render_template('register.html')
        else:
            flash('Clave de producto no valida', 'error')
            return render_template('register.html') 

# Ruta principal
@app.route('/prueba.html', methods = ['GET', 'POST'])
def principal():
    if request.method == 'GET':
        
        
        return render_template('principal.html')
        
    
    
        
        

       

# Run aplication

if __name__ == '__main__':
    app.run(debug=True)