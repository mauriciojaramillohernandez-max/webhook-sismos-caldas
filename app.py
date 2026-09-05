import os
import requests
from flask import Flask, request, jsonify
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Inches

app = Flask(__name__)

WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID")
FEATURE_SERVER_URL = "https://services6.arcgis.com/1nAgWaTpcz1xqHWX/arcgis/rest/services/survey123_277ceb6f446641289a666384c41cb519/FeatureServer/0"

REPORTS_DIR = "static/reports"
os.makedirs(REPORTS_DIR, exist_ok=True)

def descargar_adjuntos(object_id):
    url_attachments = f"{FEATURE_SERVER_URL}/{object_id}/attachments?f=json"
    response = requests.get(url_attachments).json()

    fotos_paths = {}
    attachments = response.get("attachmentInfos", [])
    temp_dir = "temp_fotos"
    os.makedirs(temp_dir, exist_ok=True)

    for i, att in enumerate(attachments):
        att_id = att["id"]
        att_name = att["name"]
        download_url = f"{FEATURE_SERVER_URL}/{object_id}/attachments/{att_id}"

        img_data = requests.get(download_url).content
        img_path = f"{temp_dir}/foto_{i+1}_{att_name}"

        with open(img_path, "wb") as f:
            f.write(img_data)

        fotos_paths[f"foto_{i+1}"] = img_path

    return fotos_paths

def enviar_whatsapp(numero, url_documento, nombre_archivo):
    url_api = f"https://graph.facebook.com/v17.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "document",
        "document": {
            "link": url_documento,
            "filename": nombre_archivo,
            "caption": "⚠️ Reporte de Inspección Post-Sismo generado exitosamente (0 créditos de ArcGIS)."
        }
    }
    return requests.post(url_api, headers=headers, json=data).json()

@app.route('/webhook', methods=['POST'])
def procesar_encuesta():
    try:
        data = request.json
        atributos = data.get('feature', {}).get('attributes', {})
        object_id = atributos.get('OBJECTID')

        numero_celular = str(atributos.get('celular_contacto', ''))
        if not numero_celular.startswith("57"):
            numero_celular = f"57{numero_celular}"

        doc = DocxTemplate("template.docx")
        contexto_fotos = descargar_adjuntos(object_id)

        imagenes_render = {}
        for key, path in contexto_fotos.items():
            imagenes_render[key] = InlineImage(doc, path, width=Inches(3.5))

        contexto = {**atributos, **imagenes_render}
        doc.render(contexto)

        nombre_archivo = f"Reporte_Inspeccion_{object_id}.docx"
        output_path = os.path.join(REPORTS_DIR, nombre_archivo)
        doc.save(output_path)

        url_publica = f"{request.host_url}static/reports/{nombre_archivo}"
        enviar_whatsapp(numero_celular, url_publica, nombre_archivo)

        for path in contexto_fotos.values():
            if os.path.exists(path):
                os.remove(path)

        return jsonify({"status": "Éxito - Reporte generado y enviado"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))