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
        
        # 1. Extraer token de ArcGIS para poder descargar fotos privadas
        arcgis_token = data.get('portalInfo', {}).get('token', '')
        
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
        # MAPA DE LOCALIZACIÓN (OpenStreetMap estático)
        # ---------------------------------------------------------
        if lon and lat:
            map_url = f"https://staticmap.openstreetmap.de/staticmap.php?center={lat},{lon}&zoom=15&size=450x250&markers={lat},{lon},lightblue"
            try:
                map_res = requests.get(map_url, timeout=10)
                if map_res.status_code == 200:
                    map_path = f"mapa_{object_id}.png"
                    with open(map_path, "wb") as f:
                        f.write(map_res.content)
                    downloaded_files.append(map_path)
                    atributos['mapa_ubicacion'] = InlineImage(doc, map_path, width=Inches(5.0))
                else:
                    atributos['mapa_ubicacion'] = f"Ubicación GPS -> Lat: {lat}, Lon: {lon}"
            except Exception:
                atributos['mapa_ubicacion'] = f"Ubicación GPS -> Lat: {lat}, Lon: {lon}"
        else:
            atributos['mapa_ubicacion'] = "Coordenadas no disponibles"

        # ---------------------------------------------------------
        # DESCARGA DEFINITIVA DE FOTOS (Extracción de Diccionario + Token)
        # ---------------------------------------------------------
        attachments = feature.get('attachments', {})
        
        # Aplanar el diccionario de Survey123 para sacar todos los adjuntos a una sola lista
        lista_adjuntos = []
        if isinstance(attachments, dict):
            for nombre_pregunta, lista_fotos in attachments.items():
                if isinstance(lista_fotos, list):
                    lista_adjuntos.extend(lista_fotos)
        elif isinstance(attachments, list):
            lista_adjuntos = attachments

        print(f"Total de fotos encontradas en el JSON: {len(lista_adjuntos)}", flush=True)

        # Descargar las fotos usando el token
        for i, att in enumerate(lista_adjuntos[:10], start=1):
            if isinstance(att, dict):
                att_url = att.get('url')
                if att_url:
                    download_url = att_url
                    # Agregar token de ArcGIS a la URL para saltar la seguridad
                    if arcgis_token:
                        separator = "&" if "?" in att_url else "?"
                        download_url = f"{att_url}{separator}token={arcgis_token}"
                        
                    try:
                        photo_res = requests.get(download_url, timeout=15)
                        
                        if photo_res.status_code == 200:
                            photo_path = f"foto_{object_id}_{i}.jpg"
                            with open(photo_path, "wb") as f:
                                f.write(photo_res.content)
                            downloaded_files.append(photo_path)
                            
                            # Inserta la foto en la etiqueta exacta de Word
                            tag_name = f"registro_fotogr_fico_{i}"
                            atributos[tag_name] = InlineImage(doc, photo_path, width=Inches(4.5))
                            print(f"Foto {i} descargada e insertada con éxito.", flush=True)
                        else:
                            print(f"Fallo al descargar foto {i}. Status: {photo_res.status_code}", flush=True)
                    except Exception as ex:
                        print(f"Excepción descargando foto {i}: {ex}", flush=True)

        # Renderizar y guardar documento
        doc.render(atributos)
        doc.save(output_path)
        print("Documento Word generado exitosamente.", flush=True)

        # ---------------------------------------------------------
        # ENVIAR A WHATSAPP
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
            
        # Validación mejorada con impresión de error exacto
        if "id" not in upload_result:
            print(f"Error de Meta al subir archivo: {upload_result}", flush=True)
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
                "caption": "Adjunto el reporte oficial de inspección con mapa y registro fotográfico.",
                "filename": f"Reporte_Inspeccion_{object_id}.docx"
            }
        }
        headers_msg = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }
        
        msg_response = requests.post(message_url, headers=headers_msg, json=payload_message)
        print(f"Resultado final Meta: {msg_response.json()}", flush=True)

        # Limpieza de archivos temporales
        if os.path.exists(output_path):
            os.remove(output_path)
        for f_path in downloaded_files:
            if os.path.exists(f_path):
                os.remove(f_path)

        return jsonify({"status": "success"}), 200

    except Exception as e:
        print(f"Error interno: {str(e)}", flush=True)
        # Limpieza de emergencia
        if output_path and os.path.exists(output_path):
            os.remove(output_path)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
