import requests
from bs4 import BeautifulSoup


def obtener_valor_dolar():
  
  url = "https://www.bcv.org.ve/" 


  try:
    respuesta = requests.get(url, verify=False)
    respuesta.raise_for_status()  # Genera una excepción para códigos de estado distintos a 200

    soup = BeautifulSoup(respuesta.content, 'html.parser')

    # Busca el elemento con el selector CSS actualizado
    valor_dolar_element = soup.find('div', id='dolar').find('div', class_='col-sm-6 col-xs-6 centrado')

    valor_dolar_texto = valor_dolar_element.find('strong').text.strip()
    
    # Extrae el valor del dólar como texto
    valor_dolar_texto = valor_dolar_element.find('strong').text.strip()
    valor_dolar_texto = valor_dolar_texto.replace(',', '.')
    valor_dolar_texto = float(valor_dolar_texto)
    valor_dolar_texto = round(valor_dolar_texto, 2)

    return valor_dolar_texto

  except requests.exceptions.RequestException as e:
    print(f"Ocurrió un error al obtener la URL: {e}")
  
  return None



  
  
   

  
  