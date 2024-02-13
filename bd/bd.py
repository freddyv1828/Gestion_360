from sqlalchemy import Column, Integer, String, ForeignKey, TIMESTAMP, text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base() 

# Configuración de la base de datos
DATABASE_HOST = 'pg.neon.tech'
DATABASE_PORT = 5432
DATABASE_NAME = 'gestionbd'
DATABASE_USERNAME = 'freddyv1828'
DATABASE_PASSWORD = 'oKzWyH8pYv2I'


class administrador(Base):
    __tablename__ = 'administrador'
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    lastname = Column(String(255), nullable=False)
    dni = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    phone = Column(String(255), nullable=False)
    username = Column(String(255), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    clave_acti_id = Column(Integer, ForeignKey('clave_acti.id'))
    clave_actived = Column(String(255))
    
    clave_acti = relationship('clave_acti') 
    

class clave_acti(Base):
    
    __tablename__ = 'clave_acti'
    id = Column(Integer, primary_key=True)
    clave = Column(String(255), unique=True)
    fecha_creacion = Column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))
    used = Column(Boolean)
    
# Funciones de la base de datos


    
    
    