import os
import requests
from flask import Flask, request, jsonify
from docxtpl import DocxTemplate

app = Flask(__name__)

WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID")

@app.route('/webhook', methods=['POST'])
def procesar_encuesta():
    output_path = ""
    try:
        data = request.json
        print("================ DATOS RECIBIDOS ================", flush=True)
        
        feature = data.get('feature', {})
        atributos = feature.get('attributes', {})
        geometria = feature.get('geometry', {})
        
        # Inyectar coordenadas
        atributos['longitud'] = geometria.get('x', 'No disponible')
        atributos['latitud'] = geometria.get('y', 'No disponible')
        
        object_id = feature.get('result', {}).get('objectId')
        if not object_id:
            object_id = atributos.get('objectid')
            
        numero_celular = str(atributos.get('celular_contacto', '')).strip().replace('+', '')
        
        if not numero_celular or numero_celular == 'None':
            print("Error: El campo 'celular_contacto' llegó vacío.", flush=True)
            return jsonify({"error": "Falta el número de celular"}), 400
            
        if not object_id:
            print("Error: No se encontró el OBJECTID.", flush=True)
            return jsonify({"error": "Falta el OBJECTID"}), 400

        if not numero_celular.startswith("57"):
            numero_celular = f"57{numero_celular}"

        print(f"Procesando ID: {object_id} para el celular: {numero_celular}", flush=True)

        # ---------------------------------------------------------
        # GENERAR EL REPORTE EN WORD
        # ---------------------------------------------------------
        template_path = "template.docx"
        output_path = f"Reporte_Inspeccion_{object_id}.docx"
        
        if not os.path.exists(template_path):
            print("Error: No se encontró el archivo template.docx en el servidor.", flush=True)
            return jsonify({"error": "Plantilla no encontrada"}), 500
            
        doc = DocxTemplate(template_path)
        doc.render(atributos)
        doc.save(output_path)
        print("Documento Word generado exitosamente.", flush=True)

        # ---------------------------------------------------------
        # ENVIAR A WHATSAPP (API DE META)
        # ---------------------------------------------------------
        upload_url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/media"
        headers_auth = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
        
        with open(output_path, "rb") as file:
            files = {
                "file": (output_path, file, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            }
            payload_media = {
                "messaging_product": "whatsapp",
                "type": "document"
            }
            print("Subiendo archivo a Meta...", flush=True)
            upload_response = requests.post(upload_url, headers=headers_auth, data=payload_media, files=files)
            upload_result = upload_response.json()
            
        if "id" not in upload_result:
            print(f"Error de Meta al subir archivo: {upload_result}", flush=True)
            return jsonify({"error": "Fallo al subir documento a WhatsApp", "details": upload_result}), 500
            
        media_id = upload_result["id"]

        message_url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
        payload_message = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": numero_celular,
            "type": "document",
            "document": {
                "id": media_id,
                "caption": "Adjunto el reporte oficial de inspección estructural post-sismo.",
                "filename": f"Reporte_Habitabilidad_{object_id}.docx"
            }
        }
        headers_msg = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }
        
        print("Enviando mensaje de WhatsApp...", flush=True)
        msg_response = requests.post(message_url, headers=headers_msg, json=payload_message)
        msg_result = msg_response.json()
        
        print(f"Resultado final Meta: {msg_result}", flush=True)

        # Limpieza del archivo temporal
        if os.path.exists(output_path):
            os.remove(output_path)

        # Respuesta limpia y directa para que Survey123 cierre el ciclo sin errores
        return jsonify({"status": "success", "message": "Reporte generado y enviado por WhatsApp"}), 200

    except Exception as e:
        print(f"Error interno fatal: {str(e)}", flush=True)
        if output_path and os.path.exists(output_path):
            os.remove(output_path)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
