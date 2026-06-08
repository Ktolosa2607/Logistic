import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import mysql.connector
import zipfile
import io
import re
from datetime import datetime

# =========================================================================
# 1. CONFIGURACIÓN DE INTERFAZ Y ESTILOS PREMIUM ORIGINALES
# =========================================================================
st.set_page_config(
    page_title="Suite Aduanera Pro - Flujo Multi-Máster Consolidado",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        html, body, [data-testid="stAppViewContainer"] {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #f0f9ff 0%, #e0e7ff 100%) !important;
        }
        .main-header {
            font-size: 2.2em;
            font-weight: 800;
            background: linear-gradient(90deg, #4f46e5, #8b5cf6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 5px;
        }
        .subtitle {
            color: #64748b;
            font-weight: 500;
            margin-bottom: 25px;
        }
        .stepper-container {
            display: flex;
            justify-content: center;
            margin-bottom: 35px;
            gap: 15px;
            align-items: center;
        }
        .step-box {
            display: flex;
            align-items: center;
            gap: 10px;
            font-weight: 600;
            color: #64748b;
            opacity: 0.5;
        }
        .step-box.active {
            color: #4f46e5;
            opacity: 1;
            transform: scale(1.02);
        }
        .step-box.completed {
            color: #10b981;
            opacity: 1;
        }
        .circle {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            background: #e2e8f0;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            font-weight: 700;
            color: #1e293b;
        }
        .step-box.active .circle {
            background: #4f46e5;
            color: white;
            box-shadow: 0 0 0 6px rgba(79, 70, 229, 0.15);
        }
        .step-box.completed .circle {
            background: #10b981;
            color: white;
        }
        .line {
            width: 50px;
            height: 4px;
            background: #e2e8f0;
            border-radius: 2px;
        }
        .line.completed {
            background: #10b981;
        }
        .premium-card {
            background: rgba(255, 255, 255, 0.95);
            padding: 35px;
            border-radius: 20px;
            box-shadow: 0 10px 40px -10px rgba(79, 70, 229, 0.15);
            backdrop-filter: blur(10px);
            margin-bottom: 25px;
        }
        .finish-card {
            text-align: center;
            padding: 50px;
            background: linear-gradient(180deg, #ecfdf5 0%, #ffffff 100%);
            border: 2px dashed #34d399;
            border-radius: 20px;
        }
    </style>
""", unsafe_allow_html=True)

# =========================================================================
# 2. CONEXIÓN A TiDB CLOUD (Database: test)
# =========================================================================
def conectar_tidb():
    try:
        return mysql.connector.connect(
            host=st.secrets["tidb"]["host"],
            user=st.secrets["tidb"]["user"],
            password=st.secrets["tidb"]["password"],
            database=st.secrets["tidb"]["database"],
            port=st.secrets["tidb"]["port"],
            ssl_verify_identity=True
        )
    except Exception as e:
        st.error(f"⚠️ Error de enlace con TiDB Cloud: {e}")
        return None

# =========================================================================
# 3. CONTROL DE PERSISTENCIA DE PASOS (Stepper)
# =========================================================================
if "step" not in st.session_state:
    st.session_state.step = 1
if "raw_folder_data" not in st.session_state:
    st.session_state.raw_folder_data = []
if "master_sessions" not in st.session_state:
    st.session_state.master_sessions = {}
if "macro_zip_data" not in st.session_state:
    st.session_state.macro_zip_data = None

def ir_a_paso(paso):
    st.session_state.step = paso
    st.rerun()

# Dibujar cabeceras estéticas de la App original
s1, s2, s3, s4 = "completed" if st.session_state.step > 1 else ("active" if st.session_state.step == 1 else ""), "completed" if st.session_state.step > 2 else ("active" if st.session_state.step == 2 else ""), "completed" if st.session_state.step > 3 else ("active" if st.session_state.step == 3 else ""), "active" if st.session_state.step == 4 else ""
l1, l2, l3 = "completed" if st.session_state.step > 1 else "", "completed" if st.session_state.step > 2 else "", "completed" if st.session_state.step > 3 else ""

st.markdown(f"""
    <div class='premium-card' style='padding: 20px 35px; margin-bottom: 20px;'>
        <div style='display: flex; justify-content: space-between; align-items: center;'>
            <div>
                <div class='main-header'>Suite Aduanera Pro</div>
                <div class='subtitle' style='margin: 0;'>Flujo por Lotes Multi-Máster Consolidado</div>
            </div>
        </div>
    </div>
    <div class='stepper-container'>
        <div class='step-box {s1}'><div class='circle'>1</div> Datos Base</div>
        <div class='line {l1}'></div>
        <div class='step-box {s2}'><div class='circle'>2</div> Auditoría</div>
        <div class='line {l2}'></div>
        <div class='step-box {s3}'><div class='circle'>3</div> PDFs DUCAs</div>
        <div class='line {l3}'></div>
        <div class='step-box {s4}'><div class='circle'>✓</div> Fin</div>
    </div>
""", unsafe_allow_html=True)

# =========================================================================
# PASO 1: LECTURA COINCIDENTE CON LA ESTRUCTURA ORIGINAL DE CARPETAS
# =========================================================================
if st.session_state.step == 1:
    st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
    st.write("### 📁 Carga de Archivos e Inyección Estructurada")
    
    col1, col2 = st.columns(2)
    with col1:
        # Recomendación técnica para mantener webkitdirectory mediante ZIP en servidores remotos
        master_zip = st.file_uploader(
            "Arrastra aquí el archivo .ZIP de la Carpeta de tus Másters (Mantiene la estructura de subcarpetas)", 
            type=["zip"], key="master_zip"
        )
    with col2:
        starship_excels = st.file_uploader(
            "Arrastra los archivos Excel (StarShip) aquí", 
            accept_multiple_files=True, type=["xlsx", "xls"], key="starship_excels"
        )

    if master_zip and starship_excels:
        if st.button("Siguiente: Auditar Datos ➡️", type="primary"):
            with st.spinner("Ejecutando parseo recursivo y discriminación de carpetas..."):
                
                # --- PARSEO DE EXCEL (STARSHIP LOGIC) ---
                db_starship = []
                for f in starship_excels:
                    try:
                        df_sheet = pd.read_excel(f, skiprows=2, header=None)
                        for _, row in df_sheet.iterrows():
                            if len(row) >= 27 and pd.notna(row[26]):
                                db_starship.append({
                                    "awb": str(row[1]).strip() if pd.notna(row[1]) else "",
                                    "tracking": str(row[2]).strip() if pd.notna(row[2]) else "",
                                    "pkgZ": str(row[26]).strip(),
                                    "archivoOrigen": f.name
                                })
                    except Exception as e:
                        st.error(f"Error procesando Excel {f.name}: {e}")

                # --- LÓGICA DE EXTRACCIÓN RECURSIVA COINCIDENTE CON EL COGNITIVO DEL JS ---
                folder_groups = {}  # Map() simulado en Python
                
                with zipfile.ZipFile(master_zip, "r") as z:
                    for file_info in z.infolist():
                        if file_info.is_dir():
                            continue
                        
                        filename = file_info.filename
                        # Limpieza y separación exacta por niveles (webkitRelativePath split)
                        parts = [p for p in filename.split('/') if p]
                        folder_name = "Carpeta_Independiente"
                        
                        if len(parts) >= 3:
                            folder_name = parts[1]  # Mismo mapeo indexado de tu JS
                        elif len(parts) == 2:
                            folder_name = parts[0]
                            
                        if folder_name not in folder_groups:
                            folder_groups[folder_name] = {"xmls": [], "pdfs": []}
                            
                        # Clasificación por extensiones
                        if filename.lower().endswith('.xml'):
                            folder_groups[folder_name]["xmls"].append((filename, z.read(filename)))
                        elif filename.lower().endswith('.pdf'):
                            folder_groups[folder_name]["pdfs"].append((filename, z.read(filename)))

                # --- REPLICACIÓN DEL PROCESAMIENTO PARSE-XML-PROMISIFIED ---
                raw_folder_data = []
                for f_name, group in folder_groups.items():
                    guias_acumuladas = []
                    
                    for xml_path, xml_bytes in group["xmls"]:
                        try:
                            root = ET.fromstring(xml_bytes)
                            for item in root.findall('.//Item'):
                                summary_node = item.find('.//Summary_declaration')
                                summary = summary_node.text if summary_node is not None else "N/A"
                                
                                # Extraer montos aduaneros exactos aplicando reemplazo de comas
                                def clean_monto(node_name):
                                    node = item.find(f'.//{node_name}')
                                    if node is not None and node.text:
                                        num = float(str(node.text).replace(',', '').strip())
                                        return num
                                    return 0.0

                                fob = clean_monto("Item_Invoice_Amount_national_currency")
                                freight = clean_monto("item_external_freight_Amount_national_currency")
                                insurance = clean_monto("item_insurance_Amount_national_currency")
                                cif = clean_monto("Total_CIF_itm")
                                
                                dai, iva = 0.0, 0.0
                                for line in item.findall('.//Taxation_line'):
                                    code_node = line.find('.//Duty_tax_code')
                                    amount_node = line.find('.//Duty_tax_amount')
                                    if code_node is not None and amount_node is not None:
                                        code = code_node.text
                                        amount = float(str(amount_node.text).replace(',', '').strip() or 0)
                                        if code == "DAI": dai = amount
                                        elif code == "IVA": iva = amount
                                        
                                guias_acumuladas.append({
                                    "guia": summary.strip(), "fob": fob, "freight": freight, 
                                    "insurance": insurance, "cif": cif, "dai": dai, "iva": iva
                                })
                        except Exception as e:
                            st.error(f"Error procesando XML {xml_path}: {e}")
                            
                    raw_folder_data.append({
                        "folderName": f_name,
                        "xmls": guias_acumuladas,
                        "pdfFiles": group["pdfs"]
                    })

                # --- DISCRIMINACIÓN Y CONSOLIDACIÓN MULTI-MÁSTER (PASO 2 ORIGINAL) ---
                master_sessions = {}
                starship_map = {reg["pkgZ"]: reg for reg in dbStarship}
                
                for folder in raw_folder_data:
                    awb_detectado = None
                    for xml in folder["xmls"]:
                        match = starship_map.get(xml["guia"])
                        if match and match["awb"]:
                            awb_detectado = match["awb"]
                            
                    id_master_final = awb_detectado if awb_detectado else f"Desconocido_{folder['folderName']}"
                    
                    if id_master_final not in master_sessions:
                        master_sessions[id_master_final] = {"master": id_master_final, "finalData": [], "processedPdfs": []}
                        
                    sesion_actual = master_sessions[id_master_final]
                    
                    for xml in folder["xmls"]:
                        match = starship_map.get(xml["guia"])
                        sesion_actual["finalData"].append({
                            **xml,
                            "masterPertenece": id_master_final,
                            "awb": match["awb"] if match else "N/A",
                            "tracking": match["tracking"] if match else "N/A"
                        })
                        
                    # Agrupar PDFs correspondientes a esta subcarpeta de origen exacta
                    for pdf_path, pdf_bytes in folder["pdfFiles"]:
                        pdf_name_only = pdf_path.split('/')[-1]
                        match_num = re.match(r'^\d+', pdf_name_only) or re.search(r'\d+', pdf_name_only)
                        num = match_num.group(0) if match_num else ""
                        
                        if num != "":
                            sesion_actual["processedPdfs"].append({
                                "file_bytes": pdf_bytes, "newName": f"Duca_{num}.pdf", 
                                "status": "success", "originalName": pdf_name_only, "master": id_master_final
                            })
                        else:
                            sesion_actual["processedPdfs"].append({
                                "file_bytes": pdf_bytes, "newName": "---", 
                                "status": "error", "originalName": pdf_name_only, "master": id_master_final
                            })

                st.session_state.master_sessions = master_sessions
                ir_a_paso(2)
    st.markdown("</div>", unsafe_allow_html=True)

# =========================================================================
# PASO 2: RENDIMIENTO E INTERFAZ GRÁFICA DE AUDITORÍA
# =========================================================================
elif st.session_state.step == 2:
    st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
    st.write("### 📊 Cuadre y Discriminación de Declaraciones")
    
    if "mostrando_solo_errores" not in st.session_state:
        st.session_state.mostrando_solo_errores = False

    rows_audit = []
    for session in st.session_state.master_sessions.values():
        for row in session["finalData"]:
            calc_text = round(row["fob"] + row["freight"] + row["insurance"], 2)
            cif_text = round(row["cif"], 2)
            tiene_error = (calc_text != cif_text)
            dif = round(cif_text - calc_text, 2)
            
            if st.session_state.mostrando_solo_errores and not tiene_error:
                continue
                
            rows_audit.append({
                "Máster Asignado": row["masterPertenece"], "Guía": row["guia"], "AWB": row["awb"], "Tracking": row["tracking"],
                "FOB": row["fob"], "Freight": row["freight"], "Insurance": row["insurance"],
                "Suma Calc.": calc_text, "Value For Duty": cif_text, "Diferencia": dif, "is_error": tiene_error
            })

    df_audit = pd.DataFrame(rows_audit)
    
    col_f1, col_f2 = st.columns([2, 5])
    with col_f1:
        txt_filtro = "👁️ Mostrar Todos" if st.session_state.mostrando_solo_errores else "👁️ Mostrar Solo Errores"
        if st.button(txt_filtro, use_container_width=True):
            st.session_state.mostrando_solo_errores = not st.session_state.mostrando_solo_errores
            st.rerun()
            
    with col_f2:
        if st.button("🔧 Corregir Automáticamente (Ajustes de Flete Lote)", type="secondary"):
            for session in st.session_state.master_sessions.values():
                for row in session["finalData"]:
                    if round(row["fob"] + row["freight"] + row["insurance"], 2) != round(row["cif"], 2):
                        row["freight"] = round(row["cif"] - row["fob"] - row["insurance"], 2)
            st.success("¡Cuadre matemático forzado exitosamente contra el Value For Duty!")
            st.rerun()

    # Estilización condicional de la grilla tipo CSS original (.row-error)
    if not df_audit.empty:
        def style_rows(data):
            return ['background-color: #fff1f2; color: #991b1b;' if data["is_error"] else '' for _ in data]
        
        df_display = df_audit.drop(columns=["is_error"])
        st.dataframe(df_display.style.apply(style_rows, axis=1).format(precision=2), use_container_width=True, height=380)
    else:
        st.info("No se encontraron registros bajo el criterio seleccionado.")

    st.write("")
    if st.button("📥 Validar y Procesar PDFs ➡️", type="primary"):
        ir_a_paso(3)
    st.markdown("</div>", unsafe_allow_html=True)

# =========================================================================
# PASO 3: CONTROL VISUAL DE PDFs RENOMBRADOS EN PARALELO
# =========================================================================
elif st.session_state.step == 3:
    st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
    st.write("### 📦 Estado de Consolidación Estructurada")
    
    total_m = len(st.session_state.master_sessions)
    st.markdown(f"""
        <div style='background: #eef2ff; border: 1px solid #c7d2fe; color: #3730a3; padding: 20px; border-radius: 12px; margin-bottom: 25px;'>
            <div style='font-size: 0.85em; text-transform: uppercase; font-weight: 700;'>Estado de consolidación por lotes</div>
            <strong style='font-size: 1.4em;'>{total_m} Másters Cargados</strong>
        </div>
    """, unsafe_allow_html=True)

    pdf_table_rows = []
    total_validos = 0
    total_pdfs = 0
    
    for session in st.session_state.master_sessions.values():
        for item in session["processedPdfs"]:
            total_pdfs += 1
            if item["status"] == "success":
                total_validos += 1
            pdf_table_rows.append({
                "Máster Origen": item["master"], "Archivo Original": item["originalName"],
                "Nuevo Nombre Estructurado": item["newName"], "Estado": "✓ Listo" if item["status"] == "success" else "✗ Sin Números"
            })

    if pdf_table_rows:
        st.dataframe(pd.DataFrame(pdf_table_rows), use_container_width=True, height=280)
    st.write(f"**{total_validos} de {total_pdfs} PDFs mapeados correctamente.**")

    if st.button("📦 Generar MACRO-ZIP Consolidado ✓", type="primary", disabled=(total_validos == 0)):
        with st.spinner("Compilando empaquetado estructural final bilingüe..."):
            macro_buffer = io.BytesIO()
            busqueda_historica = []
            
            with zipfile.ZipFile(macro_buffer, "w", zipfile.ZIP_DEFLATED) as macro_zip:
                for master_name, session in st.session_state.master_sessions.items():
                    
                    # Estructura estricta de las 19 Columnas bilingües exigidas por TEMU
                    headers = [
                        "Platform包裹号（必填）|Platform Package Number (required)", "包裹清关所属国家（必填）|Country (required)",
                        "包裹清关所在省（非必填）|Province of customs clearance (optional)", "包裹收货所在省（非必填）|Province of receipt (optional)",
                        "币种（申报金额与税费）（必填）|Currency (required)", "包裹的申报价值金额（必填）|Value For Duty (required)",
                        "服务商申报包裹代缴税费总金额（必填）|Total payable amount (required)", "服务商申报包裹代缴关税总金额（必填）|Total Duty (required)",
                        "服务商申报包裹代缴消费税金额（必填）|Total Excise Tax (required)", "服务商申报包裹代缴增值税金额（必填）|Total GST (required)",
                        "服务商申报包裹代缴反倾销税金额（必填）|Total SIMA (required)", "服务商申报包裹代缴其他税金额（必填）|Total Other Tax (required)",
                        "币种（手续费）|Currency（Service Fee)", "服务商申报包裹手续费（必填）|Service Fee (required)",
                        "服务商单号（必填）|Logistics number(required)", "提单号（非必填）|AWB Number(optional)",
                        "FOB价（必填）|FOB Price (required)", "运费（必填）|Freight (required)", "保险费（必填）|Insurance(required)"
                    ]
                    
                    rows_export = []
                    for row in session["finalData"]:
                        tracking_str = row["tracking"] if row["tracking"] != "N/A" else ""
                        busqueda_historica.append(f"{row['guia']} {row['tracking']}")
                        
                        rows_export.append([
                            tracking_str, "El Salvador", "", "", "USD", round(row["cif"], 2),
                            round(row["dai"] + row["iva"], 2), round(row["dai"], 2), 0, round(row["iva"], 2), 0, 0,
                            "USD", 0, row["guia"], row["awb"] if row["awb"] != "N/A" else "",
                            round(row["fob"], 2), round(row["freight"], 2), round(row["insurance"], 2)
                        ])
                        
                    df_out = pd.DataFrame(rows_export, columns=headers)
                    excel_buf = io.BytesIO()
                    with pd.ExcelWriter(excel_buf, engine="openpyxl") as w:
                        df_out.to_excel(w, sheet_name="Template", index=False)
                        
                    # Guardar XLSX en la raíz del empaquetado
                    macro_zip.writestr(f"{master_name}.xlsx", excel_buf.getvalue())
                    
                    # Generar sub-ZIP individual interno de DUCAs
                    valid_pdfs = [p for p in session["processedPdfs"] if p["status"] == "success"]
                    if valid_pdfs:
                        sub_zip_buf = io.BytesIO()
                        with zipfile.ZipFile(sub_zip_buf, "w", zipfile.ZIP_DEFLATED) as sub_zip:
                            for p in valid_pdfs:
                                sub_zip.writestr(p["newName"], p["file_bytes"])
                        macro_zip.writestr(f"{master_name}_Ducas.zip", sub_zip_buf.getvalue())

            st.session_state.macro_zip_data = macro_buffer.getvalue()
            
            # --- PERSISTENCIA CENTRALIZADA CLOUD (REEMPLAZO DE INDEXED DB) ---
            conn = conectar_tidb()
            if conn:
                cursor = conn.cursor()
                m_label = list(st.session_state.master_sessions.keys())[0] if st.session_state.master_sessions else "Lote"
                indice_texto = " ".join(busqueda_historica)
                
                # Inyección SQL directa a la tabla control_ducas de tu base test
                query = "INSERT INTO control_ducas (master_name, search_data) VALUES (%s, %s)"
                cursor.execute(query, (f"Lote_{m_label}", indice_texto))
                conn.commit()
                cursor.close()
                conn.close()
                
            ir_a_paso(4)
    st.markdown("</div>", unsafe_allow_html=True)

# =========================================================================
# PASO 4: ENTREGA DE ARCHIVOS Y REINICIO
# =========================================================================
elif st.session_state.step == 4:
    st.markdown("<div class='finish-card'>", unsafe_allow_html=True)
    st.write("<div style='font-size: 5em; margin-bottom: 15px;'>🎉</div>", unsafe_allow_html=True)
    st.write("<h2 style='color: #047857; margin-bottom: 10px;'>¡Proceso por Lotes Completado!</h2>", unsafe_allow_html=True)
    st.write("<p style='color: #065f46; font-size: 1.2em; margin-bottom: 40px;'>Los archivos Excel y los ZIPs individuales de las DUCAs han sido estructurados de forma segura dentro del paquete final.</p>", unsafe_allow_html=True)
    
    if st.session_state.macro_zip_data:
        st.download_button(
            label="📥 Descargar MACRO-ZIP Consolidado",
            data=st.session_state.macro_zip_data,
            file_name=f"Lote_Consolidado_Aduana_{int(datetime.now().timestamp())}.zip",
            mime="application/zip",
            type="primary"
        )
    st.write("")
    if st.button("+ Iniciar Nuevo Proceso", type="secondary"):
        st.session_state.master_sessions = {}
        st.session_state.macro_zip_data = None
        ir_a_paso(1)
    st.markdown("</div>", unsafe_allow_html=True)

# =========================================================================
# GESTOR DE HISTORIAL INTEGRADO EN LA NUBE (TiDB CLOUD)
# =========================================================================
st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
st.write("### 🗄️ Gestor de Archivos Locales en la Nube")

query_input = st.text_input(
    "Filtro del Historial", 
    placeholder="🔍 Buscar por Máster, tracking, guía... o pega varios separados por comas"
)

if st.button("Consultar Base de Datos (TiDB)"):
    conn = conectar_tidb()
    if conn:
        cursor = conn.cursor(dictionary=True)
        if query_input:
            terminos = [t.strip() for t in re.split(r'[\n\t,]+', query_input) if t.strip()]
            if terminos:
                condiciones = " OR ".join(["search_data LIKE %s OR master_name LIKE %s"] * len(terminos))
                parametros = []
                for t in terminos:
                    parametros.extend([f"%{t}%", f"%{t}%"])
                sql = f"SELECT id, master_name, fecha_procesado FROM control_ducas WHERE {condiciones} ORDER BY fecha_procesado DESC"
                cursor.execute(sql, parametros)
            else:
                sql = "SELECT id, master_name, fecha_procesado FROM control_ducas ORDER BY fecha_procesado DESC LIMIT 10"
                cursor.execute(sql)
        else:
            sql = "SELECT id, master_name, fecha_procesado FROM control_ducas ORDER BY fecha_procesado DESC LIMIT 10"
            cursor.execute(sql)
            
        res = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if res:
            st.success(f"Se encontraron {len(res)} registros en TiDB Cloud:")
            df_res = pd.DataFrame(res)
            df_res.columns = ["ID", "Identificador de Máster", "Fecha de Inyección"]
            st.table(df_res)
        else:
            st.warning("No se encontraron coincidencias en el historial de la nube.")
st.markdown("</div>", unsafe_allow_html=True)
