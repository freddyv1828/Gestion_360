import requests
from bs4 import BeautifulSoup


def obtener_valor_dolar(url):


  try:
    respuesta = requests.get(url, verify=False)
    respuesta.raise_for_status()  # Genera una excepción para códigos de estado distintos a 200

    soup = BeautifulSoup(respuesta.content, 'html.parser')

    # Busca el elemento con el selector CSS actualizado
    valor_dolar_element = soup.find('div', id='dolar').find('div', class_='col-sm-6 col-xs-6 centrado')

    valor_dolar_texto = valor_dolar_element.find('strong').text.strip()
    
    # Extrae el valor del dólar como texto
    valor_dolar_texto = valor_dolar_element.find('strong').text.strip()

    return valor_dolar_texto

  except requests.exceptions.RequestException as e:
    print(f"Ocurrió un error al obtener la URL: {e}")
  
  return None

# Reemplaza con la URL real de la página web
url = "https://www.bcv.org.ve/"  # Actualiza con la URL correcta

valor_dolar = obtener_valor_dolar(url)

if valor_dolar:
  print( valor_dolar)
else:
  print("Valor del dólar no encontrado en la página web.")

  
  
   

  
  