import os
from flask import Flask, request, jsonify
# Importa aquí las demás librerías que estés usando (ej. docxtpl, requests, etc.)

app = Flask(__name__)

WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID")

@app.route('/webhook', methods=['POST'])
def procesar_encuesta():
    try:
        data = request.json
        print("================ DATOS RECIBIDOS DE SURVEY123 ================", flush=True)
        print(data, flush=True)
        print("==============================================================", flush=True)
        
        feature = data.get('feature', {})
        atributos = feature.get('attributes', {})
        
        # 1. Búsqueda inteligente del ID del registro
        object_id = feature.get('result', {}).get('objectId')
        if not object_id:
            object_id = atributos.get('objectid') # Respaldo por si llega en minúscula
            
        # 2. Extraer y limpiar el número de celular
        numero_celular = str(atributos.get('celular_contacto', '')).strip()
        numero_celular = numero_celular.replace('+', '') # Eliminar el símbolo + si lo escribieron
        
        # 3. Validaciones de seguridad
        if not numero_celular or numero_celular == 'None':
            print("Error: El campo 'celular_contacto' llegó vacío o no existe.", flush=True)
            return jsonify({"error": "Falta el número de celular"}), 400
            
        if not object_id:
            print("Error: No se encontró el OBJECTID en la carga útil.", flush=True)
            return jsonify({"error": "Falta el OBJECTID"}), 400

        # Ajustar código de país (57 para Colombia)
        if not numero_celular.startswith("57"):
            numero_celular = f"57{numero_celular}"

        # ---------------------------------------------------------
        # AQUÍ VA TU LÓGICA EXISTENTE PARA DESCARGAR FOTOS, CREAR EL REPORTE (template.docx)
        # Y HACER LA PETICIÓN POST A LA API DE WHATSAPP
        # ---------------------------------------------------------
        
        print(f"Proceso exitoso. ID: {object_id} | Celular destino: {numero_celular}", flush=True)
        return jsonify({"status": "success", "message": "Reporte procesado"}), 200

    except Exception as e:
        print(f"Error interno procesando webhook: {str(e)}", flush=True)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
