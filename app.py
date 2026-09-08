import os
from flask import Flask, request, jsonify
# Importa aquí las demás librerías que estés usando (ej. docxtpl, requests, etc.)

app = Flask(__name__)

# Variables de entorno seguras (conectadas a Render)
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID")

@app.route('/webhook', methods=['POST'])
def procesar_encuesta():
    try:
        # 1. Recibir los datos de Survey123
        data = request.json
        
        # --- LÍNEAS DE DEPURACIÓN (Nuevas) ---
        print("================ DATOS RECIBIDOS DE SURVEY123 ================", flush=True)
        print(data, flush=True)
        print("==============================================================", flush=True)
        
        # 2. Extraer atributos del diccionario que envía Survey123
        atributos = data.get('feature', {}).get('attributes', {})
        object_id = atributos.get('OBJECTID')
        
        # 3. Extraer y formatear el número de celular
        numero_celular = str(atributos.get('celular_contacto', '')).strip()
        
        # 4. Validaciones (Estas son las que devuelven el error 400 si falta algo)
        if not numero_celular or numero_celular == 'None':
            print("Error: El campo 'celular_contacto' llegó vacío o no existe en el formulario.", flush=True)
            return jsonify({"error": "Falta el número de celular"}), 400
            
        if not object_id:
            print("Error: No se encontró el OBJECTID en la carga útil.", flush=True)
            return jsonify({"error": "Falta el OBJECTID"}), 400

        # Ajustar código de país (57 para Colombia)
        if not numero_celular.startswith("57"):
            numero_celular = f"57{numero_celular}"

        # ---------------------------------------------------------
        # AQUÍ VA TU LÓGICA EXISTENTE PARA CREAR EL REPORTE (template.docx)
        # Y HACER LA PETICIÓN POST A LA API DE WHATSAPP
        # ---------------------------------------------------------
        
        print(f"Proceso exitoso. Generando reporte para el celular: {numero_celular}", flush=True)
        
        # Retorno de éxito
        return jsonify({"status": "success", "message": "Reporte procesado"}), 200

    except Exception as e:
        # Si el código se estrella por otro motivo, lo mostrará en rojo aquí
        print(f"Error interno procesando webhook: {str(e)}", flush=True)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Configuración del puerto para Render
    app.run(host='0.0.0.0', port=10000)
