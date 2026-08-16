import requests
import urllib3

# Silencia las advertencias de certificados SSL locales
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 1. PON LA IP DE TU BRIDGE AQUÍ ---
BRIDGE_IP = "192.168.50.212" 

def paso_1_generar_llave():
    print("--- PASO 1: GENERAR AUTENTICACIÓN ---")
    print("¡ATENCIÓN! Ve físicamente al Hue Bridge y presiona el botón grande del centro.")
    input("Presiona ENTER en este teclado cuando ya lo hayas presionado...")
    
    url = f"https://{BRIDGE_IP}/api"
    # El payload exacto que pide la documentación
    payload = {"devicetype": "mi_app_python#consola", "generateclientkey": True}
    
    response = requests.post(url, json=payload, verify=False)
    data = response.json()[0]
    
    if "error" in data:
        print(f"\n[X] Error: {data['error']['description']}")
        print("¿Seguro que presionaste el botón del Bridge?")
        return None
    else:
        app_key = data["success"]["username"]
        client_key = data["success"]["clientkey"]
        print("\n[✓] ¡ÉXITO! Guarda este dato como si fuera oro, es tu llave de acceso:")
        print(f"HUE_APPLICATION_KEY = '{app_key}'")
        # El client_key servirá después para la API de música (UDP)
        print(f"CLIENT_KEY = '{client_key}'\n")
        return app_key

def paso_2_obtener_focos(app_key):
    print("--- PASO 2: OBTENER IDs DE LOS FOCOS ---")
    url = f"https://{BRIDGE_IP}/clip/v2/resource/light"
    # Aquí pasamos la llave en los Headers, como dice el tutorial
    headers = {"hue-application-key": app_key}
    
    response = requests.get(url, headers=headers, verify=False)
    data = response.json()
    
    print("Focos encontrados en tu sistema:")
    for light in data.get('data', []):
        nombre = light['metadata']['name']
        foco_id = light['id']
        print(f"-> Nombre: {nombre}")
        print(f"-> ID: {foco_id}\n")

if __name__ == "__main__":
    # Ejecutar el proceso
    llave = paso_1_generar_llave()
    if llave:
        paso_2_obtener_focos(llave)