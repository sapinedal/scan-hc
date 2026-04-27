# Automatización de Descarga de Historias Clínicas (DevExpress)

Este script automatiza el proceso de descarga de Historias Clínicas desde un servidor local que utiliza DevExpress Reporting. El proceso es asíncrono y requiere múltiples pasos de validación y polling.

## Requisitos

- Python 3.x
- Librería `requests` (`pip install requests`)

## Configuración Inicial

El script ya cuenta con el **Token Bearer** y la **Base URL** proporcionados. 

Si el token expira (Error 401), actualiza la variable `TOKEN` en `downloader.py`.

## Uso

### 1. Ejecución Directa (Lista interna)
Modifica la lista `pacientes` al final del archivo `downloader.py` y ejecuta:
```bash
python downloader.py
```

### 2. Por línea de comandos (Individual)
```bash
python downloader.py <CEDULA> <INGRESO>
```
Ejemplo:
```bash
python downloader.py 22114433 88491
```

### 3. Carga Masiva desde JSON (Recomendado)
Puedes crear un archivo `pacientes.json` con la siguiente estructura:
```json
[
    {"cedula": "22114433", "ingreso": "88491"},
    {"cedula": "12345678", "ingreso": "99001"}
]
```
Y el script procesará cada entrada secuencialmente.

## Estructura de Archivos
- `downloader.py`: Script principal.
- `descargas/`: Carpeta donde se guardarán los PDFs generados.
- Nomenclatura: `NOMBRE_CEDULA_INGRESO.pdf`
