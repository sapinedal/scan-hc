import requests
import json
import time
import os
import sys

# --- CONFIGURACIÓN ---
BASE_URL = "http://192.168.0.25:9700"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1bmlxdWVfbmFtZSI6IjQwODUiLCJuYW1laWQiOiI0MDg1IiwiQ2VudHJvQXRlbmNpb24iOiIxIiwibmJmIjoxNzc3MzA2ODY2LCJleHAiOjE3NzczOTMyNjYsImlhdCI6MTc3NzMwNjg2Nn0.X85Jzbmz3suL0mBNRWGTkyyxktlB1IRC7AtuForZbBA"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/x-www-form-urlencoded"
}

def automatizar_descarga(cedula, id_ingreso):
    """
    Automatiza el flujo de descarga de Historias Clínicas desde DevExpress Reporting.
    """
    try:
        print(f"\n[*] Procesando Paciente - Cédula: {cedula}, Ingreso: {id_ingreso}")

        # 1. Obtener Oid del Paciente
        url_p = f"{BASE_URL}/api/CitasMedicas/ApiCmAdmonCitas/ListadoPacienteApi?filter=[%22Documento%22,%22{cedula}%22]"
        print(f"[*] Consultando datos del paciente...")
        res_p = requests.get(url_p, headers=HEADERS)
        res_p.raise_for_status()
        data_p = res_p.json()

        if not data_p.get('data'):
            print(f"[!] No se encontró el paciente con cédula {cedula}")
            return

        paciente_oid = data_p['data'][0]['Oid']
        nombre_raw = data_p['data'][0]['NombreCompleto']
        nombre_limpio = "".join([c for c in nombre_raw if c.isalnum() or c==' ']).strip().replace(" ", "_")
        print(f"[+] Paciente encontrado: {nombre_raw} (Oid: {paciente_oid})")

        # 2. Obtener Oids de los folios
        url_f = f"{BASE_URL}/api/HistoriaClinica/HistoriaClinicaConsulta/ObtenerHistoricoFolios/?id={paciente_oid}&oidIngreso={id_ingreso}&directivas=true&hcUnificada=false"
        print(f"[*] Consultando folios médicos...")
        res_f = requests.get(url_f, headers=HEADERS)
        res_f.raise_for_status()
        data_f = res_f.json()

        if data_f and len(data_f) > 0:
            # Filtrar los folios que coincidan con el IngresoConsecutivo solicitado
            list_oids = []
            for folio in data_f:
                # El campo correcto según el JSON del servidor es 'IngresoConsecutivo'
                if str(folio.get('IngresoConsecutivo')) == str(id_ingreso):
                    list_oids.append(folio['Oid'])
            
            if not list_oids and id_ingreso:
                print(f"[!] ADVERTENCIA: No se encontraron folios con IngresoConsecutivo: {id_ingreso}")
                # Mostrar el primer ingreso encontrado para ayudar al usuario
                ejemplo = data_f[0].get('IngresoConsecutivo')
                print(f"    [>] El primer folio encontrado tiene IngresoConsecutivo: {ejemplo}")
                return
        else:
            list_oids = []

        if not list_oids:
            print(f"[-] Sin folios válidos para procesar.")
            return

        print(f"[+] Se filtraron {len(list_oids)} folios para el ingreso {id_ingreso} (de {len(data_f)} totales).")

        # Definir nombre de archivo y carpeta específica por paciente
        folder_path = os.path.join("descargas", str(cedula))
        filename = f"{nombre_limpio}_{cedula}_{id_ingreso}.pdf"
        filepath = os.path.join(folder_path, filename)
        
        # Crear la carpeta del paciente si no existe
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        if os.path.exists(filepath):
            print(f"[!] El archivo ya existe en {folder_path}. Saltando...")
            return

        # 3. Open Report (Obtener reportId)
        arg_open = {
            "modulo": "HistoriaClinica",
            "nombreOpcion": "HCFRConsultarHistoricoPaciente",
            "reporte": "HCRPListadoFolios",
            "parametros": {"Oid": 1, "ListOids": list_oids},
            "carpeta": f"Reportes\\{cedula}\\HC\\{id_ingreso}_temp"
        }
        data_open = {"actionKey": "openReport", "arg": json.dumps(arg_open)}
        
        print(f"[*] Iniciando reporte en DevExpress...")
        res_open = requests.post(f"{BASE_URL}/DXXRDV", headers=HEADERS, data=data_open)
        res_open.raise_for_status()
        report_id = res_open.json()['result']['reportId']

        # 4. Start Build (Obtener documentId)
        arg_build = {"reportId": report_id, "reportUrl": json.dumps(arg_open), "parameters": []}
        data_build = {"actionKey": "startBuild", "arg": json.dumps(arg_build)}
        
        res_build = requests.post(f"{BASE_URL}/DXXRDV", headers=HEADERS, data=data_build)
        res_build.raise_for_status()
        doc_id = res_build.json()['result']['documentId']

        # 5. Polling (Esperar a que el servidor termine de generar el PDF)
        print(f"[*] Generando PDF para {nombre_limpio} ({len(list_oids)} folios).")
        print("[*] Esta operación puede tardar varios minutos. Espere...")
        
        completed = False
        attempts = 0
        max_attempts = 600 # Aumentado a 20 minutos (2s * 600) para reportes muy grandes
        
        while not completed and attempts < max_attempts:
            arg_status = {"documentId": doc_id, "isFirstRequest": False, "timeOut": 10000}
            data_status = {"actionKey": "getBuildStatus", "arg": json.dumps(arg_status)}
            
            res_status = requests.post(f"{BASE_URL}/DXXRDV", headers=HEADERS, data=data_status)
            res_status.raise_for_status()
            status_json = res_status.json()
            
            result = status_json.get('result', {})
            completed = result.get('completed', False)
            progress = result.get('progress', None)
            
            if not completed:
                attempts += 1
                if attempts % 5 == 0 or progress:
                    prog_str = f" - {progress}%" if progress is not None else ""
                    print(f"    [>] Procesando... (intento {attempts}/{max_attempts}){prog_str}")
                time.sleep(2)
        
        if not completed:
            print(f"[!] Tiempo de espera agotado para {cedula} después de 20 minutos.")
            return
        
        # 6. Descargar el archivo final (POST DIRECTO)
        print(f"[*] Descargando PDF final (vía POST)...")
        time.sleep(2)
        
        arg_export = {"format": "pdf", "documentId": doc_id}
        data_export = {"actionKey": "exportTo", "arg": json.dumps(arg_export)}
        
        try:
            final_res = requests.post(f"{BASE_URL}/DXXRDV", headers=HEADERS, data=data_export)
            final_res.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(f"[!] Error de exportación: {e}")
            if final_res is not None:
                print(f"    [Detalle del servidor]: {final_res.text[:200]}")
            return

        filename = f"{nombre_limpio}_{cedula}_{id_ingreso}.pdf"
        
        # El filepath ya fue definido y la carpeta creada al inicio de la función
        with open(filepath, "wb") as f:
            f.write(final_res.content)
        
        print(f"[#] ÉXITO: Archivo guardado en {filepath}")

    except requests.exceptions.RequestException as e:
        print(f"[!] Error de red/HTTP: {e}")
    except Exception as e:
        print(f"[!] Error inesperado con {cedula}: {e}")

if __name__ == "__main__":
    # Configuración por defecto
    pacientes = [
        {"cedula": "22114433", "ingreso": "88491"}
    ]
    
    # 1. Prioridad: Argumentos de línea de comandos
    if len(sys.argv) == 3:
        pacientes = [{"cedula": sys.argv[1], "ingreso": sys.argv[2]}]
    
    # 2. Segunda Prioridad: Archivo pacientes.json
    elif os.path.exists("pacientes.json"):
        try:
            with open("pacientes.json", "r", encoding="utf-8") as f:
                pacientes = json.load(f)
            print(f"[*] Cargados {len(pacientes)} pacientes desde pacientes.json")
        except Exception as e:
            print(f"[!] Error al leer pacientes.json: {e}")
            sys.exit(1)

    # Procesar la lista
    for p in pacientes:
        if 'cedula' in p and 'ingreso' in p:
            automatizar_descarga(p['cedula'], p['ingreso'])
        else:
            print(f"[!] Entrada inválida en la lista: {p}")
