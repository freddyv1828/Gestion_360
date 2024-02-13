from flask import Flask, render_template, request, flash, redirect, url_for
from bd.bd import DATABASE_HOST, DATABASE_PORT, DATABASE_NAME, DATABASE_USERNAME, DATABASE_PASSWORD
from bd.bd import administrador, Base, clave_acti
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from werkzeug.security import generate_password_hash
import sqlalchemy




# Instancia de la aplicacion
app = Flask(__name__)

# configuracion de la clave 
app.config['SECRET_KEY'] ='secret!'
# Conexión a la base de datos

engine = create_engine (
    'postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}'.format(
        user=DATABASE_USERNAME,
        password=DATABASE_PASSWORD,
        host=DATABASE_HOST,
        port=DATABASE_PORT,
        database=DATABASE_NAME,
    )
)

Session = sessionmaker(bind=engine)
session =  Session()



Base.metadata.create_all(engine)

# Routers
# main
@app.route('/', methods= ["GET", "POST"])
def index():
    # Validacion metodo get
    if request.method == "GET":
        return render_template('index.html')
    
    # Validacion metodo post
    if request.method == "POST":
        # Tomamos los valores del formulario
        username = request.form['username']
        password = request.form['password']
        rol = request.form['rol']
        
        # Validamos rol
        if rol == 'administrador':
            # Validamos que los campos no esten vacios
            try:
                if username != '' and password!= '':
                    admins = session.query(administrador).filter_by(username=username).all()
                    if admins:
                        for admini in admins:
                            if username == admini.username and password == admini.password:
                                flash('Bienvenido {}'.format(username),'success')
                                return redirect(url_for('principal'))
                            else:
                                flash('Usuario o contraseña incorrectos', 'error')
                                return render_template('index.html')
                    else:
                        flash('Usuario o contraseña incorrectos', 'error')
                        return render_template('index.html')
                else:
                    flash('Todos los campos son obligatorios', 'error')
                    return render_template('index.html')
            except sqlalchemy.exc.OperationalError as e:
                flash('Usuarios o contraseñas incorrectos', 'error')
                return redirect(url_for('index'))

#register
@app.route('/register', methods= ["GET", "POST"])
def register():
    # Validacion para el method gest
    if request.method == "GET":
        return render_template('register.html')
    
    # Validacion para el method post
    if request.method == "POST":
        # Tomamos los valores del formulario
        name = request.form['name']
        lastname = request.form['lastname']
        dni = request.form['dni']
        email = request.form['email']
        phone = request.form['phone']
        username = request.form['username']
        password = request.form['password']
        clave = request.form['clave']
        
        # filtramos y buscamos la clave de activacion
        clave_acti_id = session.query(clave_acti).filter_by(clave=clave).first()

        try:
            # Validamos si la clave de activacion esta en blanco
            if clave_acti_id is None:
                flash('Necesita una clave para activar su producto', 'error')
                return render_template('register.html')
            
            # Vlaidamos si la clave de activacion es igual a una lave en la base de datos
            if clave_acti_id.clave == clave:
                # Validamnos que los campos no esten vacios
                if name!= '' and lastname!= '' and dni!= '' and email!= '' and phone!= '' and username!= '' and password!= '' and clave!= '': 
                    # Validamos que la clave de activacion no este en uso
                    if clave_acti_id.used != True:   
                        # Crearadministrador
                        admin = administrador(
                            name = name,
                            lastname = lastname,
                            dni = dni,
                            email = email,
                            phone = phone,
                            username = username,
                            password = password,
                            clave_acti_id = clave_acti_id.id,
                            clave_actived = clave_acti_id.clave,
                        )
                        # Crear usado de la clave de actvacion
                        session.add(admin)
                        clave_acti_id.used = True
                        session.commit()
                        flash('Registro exitoso','success')
                        return render_template('index.html')
                    else:
                        flash('La clave de activacion ya ha sido usada', 'error')
                        return render_template('register.html')
                else:
                    flash('Todos los campos son obligatorios', 'error')
                    return redirect(url_for('register'))
            else:
                flash('Clave de activacion incorrecta', 'error')
                return render_template('register.html')
        except sqlalchemy.exc.OperationalError as e:
            if "SSL connection has been closed unexpectedly" in str(e):
                flash('No se ha podido conectar con la base de datos', 'error')
                return render_template('register.html')
            raise e


# Principal

@app.route('/principal', methods= ["GET", "POST"])
def principal():
    # Validacion metodo get
    if request.method == "GET":
        return render_template('principal.html')
        
        

       

# Run aplication

if __name__ == '__main__':
    app.run(debug=True)