import os
import requests
from flask import Flask, request, jsonify
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Inches

app = Flask(__name__)

WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID")

@app.route('/webhook', methods=['POST'])
def procesar_encuesta():
    output_path = ""
    downloaded_files = []
    try:
        data = request.json
        print("================ DATOS RECIBIDOS ================", flush=True)
        
        feature = data.get('feature', {})
        atributos = feature.get('attributes', {})
        geometria = feature.get('geometry', {})
        
        lon = geometria.get('x')
        lat = geometria.get('y')
        
        atributos['longitud'] = str(lon) if lon else 'No disponible'
        atributos['latitud'] = str(lat) if lat else 'No disponible'
        
        object_id = feature.get('result', {}).get('objectId')
        if not object_id:
            object_id = atributos.get('objectid', 'temp')
            
        numero_celular = str(atributos.get('celular_contacto', '')).strip().replace('+', '')
        
        if not numero_celular or numero_celular == 'None':
            return jsonify({"error": "Falta el celular"}), 400
            
        if not numero_celular.startswith("57"):
            numero_celular = f"57{numero_celular}"

        print(f"Procesando ID: {object_id} para el celular: {numero_celular}", flush=True)

        template_path = "template.docx"
        output_path = f"Reporte_Inspeccion_{object_id}.docx"
        
        if not os.path.exists(template_path):
            return jsonify({"error": "Plantilla no encontrada"}), 500
            
        doc = DocxTemplate(template_path)
        
        # ---------------------------------------------------------
        # 1. GENERAR IMAGEN DEL MAPA DE LOCALIZACIÓN (si hay coordenadas)
        # ---------------------------------------------------------
        if lon and lat:
            # Usamos un servicio estático para renderizar el mapa de las coordenadas
            map_url = f"https://static-maps.yandex.1.lt/1.x/?ll={lon},{lat}&z=16&size=450,250&l=map&pt={lon},{lat},comma"
            try:
                map_res = requests.get(map_url, timeout=10)
                if map_res.status_code == 200:
                    map_path = f"mapa_{object_id}.png"
                    with open(map_path, "wb") as f:
                        f.write(map_res.content)
                    downloaded_files.append(map_path)
                    # Insertar en la plantilla usando una etiqueta {{ mapa_ubicacion }}
                    atributos['mapa_ubicacion'] = InlineImage(doc, map_path, width=Inches(5.0))
                else:
                    atributos['mapa_ubicacion'] = "Mapa no disponible (error al generar imagen)"
            except Exception as e:
                print(f"No se pudo descargar el mapa: {e}", flush=True)
                atributos['mapa_ubicacion'] = "Mapa no disponible"
        else:
            atributos['mapa_ubicacion'] = "Coordenadas no disponibles"

        # ---------------------------------------------------------
        # 2. PROCESAR FOTOS DEL REGISTRO FOTOGRÁFICO
        # ---------------------------------------------------------
        # Survey123 envía los archivos adjuntos en la lista 'attachments' o en los atributos
        attachments = feature.get('attachments', [])
        
        # Procesamos las fotos disponibles de forma dinámica si llegan adjuntas
        for i, att in enumerate(attachments[:10], start=1):
            att_url = att.get('url')
            if att_url:
                try:
                    # Descargar la foto usando los permisos o token si es necesario
                    photo_res = requests.get(att_url, timeout=15)
                    if photo_res.status_code == 200:
                        photo_path = f"foto_{object_id}_{i}.jpg"
                        with open(photo_path, "wb") as f:
                            f.write(photo_res.content)
                        downloaded_files.append(photo_path)
                        
                        # Reemplazar en la plantilla (ej: registro_fotogr_fico_1)
                        tag_name = f"registro_fotogr_fico_{i}"
                        atributos[tag_name] = InlineImage(doc, photo_path, width=Inches(4.5))
                except Exception as ex:
                    print(f"Error descargando foto {i}: {ex}", flush=True)

        # Renderizar la plantilla con textos, coordenadas, mapa e imágenes
        doc.render(atributos)
        doc.save(output_path)
        print("Documento Word generado exitosamente con mapa y fotografías.", flush=True)

        # ---------------------------------------------------------
        # 3. ENVIAR A WHATSAPP (API DE META)
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
            upload_response = requests.post(upload_url, headers=headers_auth, data=payload_media, files=files)
            upload_result = upload_response.json()
            
        if "id" not in upload_result:
            return jsonify({"error": "Fallo al subir documento", "details": upload_result}), 500
            
        media_id = upload_result["id"]

        message_url = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"
        payload_message = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": numero_celular,
            "type": "document",
            "document": {
                "id": media_id,
                "caption": "Adjunto el reporte oficial de inspección estructural con mapa y registro fotográfico.",
                "filename": f"Reporte_Habitabilidad_{object_id}.docx"
            }
        }
        headers_msg = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }
        
        requests.post(message_url, headers=headers_msg, json=payload_message)

        # Limpieza de archivos temporales generados en el servidor
        if os.path.exists(output_path):
            os.remove(output_path)
        for f_path in downloaded_files:
            if os.path.exists(f_path):
                os.remove(f_path)

        return jsonify({"status": "success"}), 200

    except Exception as e:
        print(f"Error interno: {str(e)}", flush=True)
        if output_path and os.path.exists(output_path):
            os.remove(output_path)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
