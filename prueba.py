from turtle import position
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from typing import Dict
import requests
from requests.auth import HTTPDigestAuth
import json
import time
import threading
import uvicorn
from datetime import datetime

app = FastAPI()
# Almacenamiento en memoria para las imágenes base64
imagenes_base64 = {}

# Crear una sesión que podemos reutilizar
session = requests.Session()

# Credenciales para autenticación digest
username = "admin"
password = "admin"

# URLs para las diferentes peticiones
login_url = "http://172.16.2.223/API/Web/Login"
alarm_url = "http://172.16.2.223/API/AI/processAlarm/Get"
position_url = "http://172.16.2.223/API/AI/Setup/FD/Get"
heartbeat_url = "http://172.16.2.223/API/Login/Heartbeat"
face_url = "http://172.16.2.223/API/AI/Setup/FD/Set"


def heartbeat(session, auth, headers, stop_event):
    while not stop_event.is_set():
        try:
            response = session.post(
                heartbeat_url,
                auth=auth,
                headers=headers,
                verify=False
            )
            print("Heartbeat status:", response.status_code)
        except Exception as e:
            print("Error en heartbeat:", e)
        stop_event.wait(20)  # Espera 20 segundos

def monitorear_alarmas():
    try:
        # Primero hacemos login
        print("Iniciando sesión...")
        
        # Hacer el login inicial
        login_response = session.post(
            login_url,
            auth=HTTPDigestAuth(username, password),
            verify=False
        )
        print("Estado del login:", login_response.status_code)
        print("Respuesta del login:", login_response.text)
        
        # Obtener cookies y token CSRF de la respuesta del login
        cookies = login_response.cookies
        csrf_token = login_response.headers.get('X-csrftoken')
        
        if login_response.status_code == 200:
            print("Login exitoso, iniciando monitoreo continuo de alarmas...")
            print("Presiona Ctrl+C para detener el monitoreo")
            
            # Configurar headers con el token CSRF obtenido del login
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Agregar el token CSRF si existe
            if csrf_token:
                headers['X-csrftoken'] = csrf_token
                print("Token CSRF obtenido:", csrf_token)
            
            # Iniciar el heartbeat en un hilo separado
            stop_event = threading.Event()
            heartbeat_thread = threading.Thread(
                target=heartbeat,
                args=(session, HTTPDigestAuth(username, password), headers, stop_event)
            )
            heartbeat_thread.daemon = True
            heartbeat_thread.start()
            
            # Bucle infinito
            while True:
                try:
                    setup_params = {
                        "version": "1.0",
                        "data": {
                            "page_type": "ChannelConfig"
                        }
                    }
                    # Obtener configuración FD
                    setup_response = session.post(
                        position_url,
                        auth=HTTPDigestAuth(username, password),
                        headers=headers,
                        json=setup_params,
                        verify=False
                    )
                    print("\nEstado de la petición de configuración:", setup_response.status_code)
                    
                    # Procesar la respuesta de configuración
                    if setup_response.status_code == 200:
                        setup_data = setup_response.json()
                        #print("Configuración FD:", json.dumps(setup_data, indent=2))
                    
                    # Usar la misma sesión para obtener las alarmas
                    alarm_response = session.post(
                        alarm_url,
                        auth=HTTPDigestAuth(username, password),
                        headers=headers,
                        verify=False
                    )
                    print("\nEstado de la petición de alarmas:", alarm_response.status_code)
                    
                    # Obtener y procesar el JSON de la respuesta
                    json_response = alarm_response.json()
                    json_response_p = setup_response.json()
                    #print("Respuesta de alarmas:", alarm_response.text)
                    
                    try:
                        Name = json_response['data']['FaceInfo'][0]['Name']
                        print("Nombre:", Name)
                        Age = json_response['data']['FaceInfo'][0]['Age']
                        print("Edad:", Age)
                        position = json_response_p['data']['channel_info']
                        for info in position.values():
                            if info.get('switch'):  # Solo canales activos
                                rule_rect = info.get('rule_info', {}).get('rule_number1', {}).get('rule_rect')
        
                                if rule_rect:
                                    print(rule_rect)
                                    
                        # Enviar configuración facial después de 5 segundos
                        print("Esperando unos segundos antes de enviar la configuración...")
                        time.sleep(0.5)
                        print("Enviando configuración facial...")
                        
                        # Configuración facial a enviar
                        datos_config = {
                            "version": "1.0",
                            "data": {
                                "channel_info": {
                                    "CH1": {
                                        "face_attribute": True,
                                        "face_recognition": True,
                                    }
                                },
                                "page_type": "ChannelConfig"  
                            }
                        }
                        
                        # Enviar la solicitud POST con la misma sesión y headers
                        face_response = session.post(
                            face_url,
                            auth=HTTPDigestAuth(username, password),
                            headers=headers,
                            json=datos_config,
                            verify=False
                        )
                        
                        print(f"Estado de la solicitud a {face_url}: {face_response.status_code}")
                        
                        if face_response.status_code == 200:
                            print("Configuración enviada exitosamente")
                            print(json.dumps(face_response.json(), indent=2))
                        else:
                            print(f"Error en la solicitud: {face_response.status_code}")
                            print(f"Respuesta: {face_response.text}")
                
                    except KeyError:
                       print("No hay datos de rostros disponibles en este momento")
                    
                except KeyboardInterrupt:
                    print("\nDetención manual del monitoreo...")
                    stop_event.set()
                    heartbeat_thread.join()
                    break
                except Exception as e:
                    print(f"\nError en la petición: {e}")
                    time.sleep(5)
                    continue
        else:
            print("Error en el login")

    except Exception as e:
        print("Error al hacer la petición:", e)

    finally:
        print("\nCerrando sesión...")
        session.close()



if __name__ == "__main__":
    # Iniciar el monitoreo de alarmas en un hilo separado
    monitoring_thread = threading.Thread(target=monitorear_alarmas)
    monitoring_thread.daemon = True
    monitoring_thread.start()

    
    # Iniciar el servidor FastAPI
    uvicorn.run(app, host="0.0.0.0", port=8000)





