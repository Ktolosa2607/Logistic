import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import mysql.connector
import zipfile
import io
import re
from datetime import datetime

# =========================================================================
# 1. CONFIGURACIÓN PREMIUM Y ESTILOS INYECTADOS (Fidelidad de UI)
# =========================================================================
st.set_page_config(
    page_title="Suite Aduanera Pro - Flujo Multi-Máster Consolidado",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Inyección de fuentes Inter y el diseño CSS Premium original de tu app
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
        /* Estilos del Stepper */
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
        /* Contenedores */
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
# 2. CONEXIÓN A BASE DE DATOS (TiDB Cloud)
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
        st.error(f"⚠️ Error al conectar con TiDB Cloud: {e}. Revisa tus credenciales en Secrets.")
        return None

# =========================================================================
# 3. CONTROL DE ESTADOS DE SESIÓN (Control del Flujo del Stepper)
# =========================================================================
if "step" not in st.session_state:
    st.session_state.step = 1
if "master_sessions" not in st.session_state:
    st.session_state.master_sessions = {}
if "macro_zip_data" not in st.session_state:
    st.session_state.macro_zip_data = None

def ir_a_paso(paso):
    st.session_state.step = paso
    st.rerun()

# Renderizado dinámico del Stepper Original
s1, s2, s3, s4 = "completed" if st.session_state.step > 1 else ("active" if st.session_state.step == 1 else ""), "completed" if st.session_state.step > 2 else ("active" if st.session_state.step == 2 else ""), "completed" if st.session_state.step > 3 else ("active" if st.session_state.step == 3 else ""), "active" if st.session_state.step == 4 else ""
l1, l2, l3 = "completed" if st.session_state.step > 1 else "", "completed" if st.session_state.step > 2 else "", "completed" if st.session_state.step > 3 else ""

st.markdown(f"""
    <div class='premium-card' style='padding: 20px 35px; margin-bottom: 20px;'>
        <div style='display: flex; justify-content: space-between; align-items: center;'>
            <div>
                <div class='main-header'>Suite Aduanera Pro</div>
                <div class='subtitle' style='margin: 0;'>Flujo por Lotes Multi-Máster Consolidado en la Nube</div>
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
# PASO 1: INGRESOS Y PARSEO AVANZADO EN PARALELO
# =========================================================================
if st.session_state.step == 1:
    st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
    st.write("### 📁 Carga de Estructuras del Lote")
    
    col1, col2 = st.columns(2)
    with col1:
        xml_folder_files = st.file_uploader(
            "Arrastra las Declaraciones XML de tus Másters aquí", 
            accept_multiple_files=True, type=["xml"], key="xmls"
        )
    with col2:
        starship_excel_files = st.file_uploader(
            "Arrastra los archivos de Control Excel (StarShip) aquí", 
            accept_multiple_files=True, type=["xlsx", "xls"], key="excels"
        )
        
    pdf_files = st.file_uploader(
        "Arrastra los PDFs de tus DUCAs correspondientes aquí", 
        accept_multiple_files=True, type=["pdf"], key="pdfs"
    )

    # Contador en tiempo real idéntico al HTML original
    total_xmls = len(xml_folder_files) if xml_folder_files else 0
    total_excels = len(starship_excel_files) if starship_excel_files else 0
    total_pdfs = len(pdf_files) if pdf_files else 0
    
    st.markdown(f"""
        <div style='display: flex; justify-content: space-between; align-items: center; background: #f8fafc; padding: 20px; border-radius: 12px; border: 1px solid #e2e8f0; margin-top: 20px;'>
            <div style='font-weight: 600;'>
                <span style='color: #4f46e5;'>{total_xmls} Archivos XML detectados</span> &nbsp;|&nbsp; 
                <span style='color: #10b981;'>{total_excels} Libros StarShip</span> &nbsp;|&nbsp;
                <span style='color: #f59e0b;'>{total_pdfs} Documentos PDF</span>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    st.write("")
    if st.button("Siguiente: Auditar Datos ➡️", type="primary", disabled=(total_xmls == 0 or total_excels == 0)):
        with st.spinner("Procesando matriz logística Multi-Máster..."):
            # 1. Parsear e indexar datos desde StarShip (Excel)
            db_starship = {}
            for f in starship_excel_files:
                try:
                    df_star = pd.read_excel(f, skiprows=2, header=None)
                    for _, row in df_star.iterrows():
                        if len(row) >= 27 and pd.notna(row[26]):
                            pkg_z = str(row[26]).strip()
                            db_starship[pkg_z] = {
                                "awb": str(row[1]).strip() if pd.notna(row[1]) else "N/A",
                                "tracking": str(row[2]).strip() if pd.notna(row[2]) else "N/A",
                                "origen": f.name
                            }
                except Exception as e:
                    st.error(f"Error procesando StarShip ({f.name}): {e}")

            # 2. Parsear XMLs detallando aranceles específicos (DAI e IVA)
            master_sessions = {}
            for f in xml_folder_files:
                try:
                    tree = ET.parse(f)
                    root = tree.getroot()
                    
                    for item in root.findall('.//Item'):
                        summary = item.find('.//Summary_declaration').text if item.find('.//Summary_declaration') is not None else "N/A"
                        summary = summary.strip()
                        
                        fob = float(item.find('.//Item_Invoice_Amount_national_currency').text or 0) if item.find('.//Item_Invoice_Amount_national_currency') is not None else 0.0
                        freight = float(item.find('.//item_external_freight_Amount_national_currency').text or 0) if item.find('.//item_external_freight_Amount_national_currency') is not None else 0.0
                        insurance = float(item.find('.//item_insurance_Amount_national_currency').text or 0) if item.find('.//item_insurance_Amount_national_currency') is not None else 0.0
                        cif = float(item.find('.//Total_CIF_itm').text or 0) if item.find('.//Total_CIF_itm') is not None else 0.0
                        
                        dai, iva = 0.0, 0.0
                        for tax in item.findall('.//Taxation_line'):
                            code = tax.find('.//Duty_tax_code').text if tax.find('.//Duty_tax_code') is not None else ""
                            amount = float(tax.find('.//Duty_tax_amount').text or 0) if tax.find('.//Duty_tax_amount') is not None else 0.0
                            if code == "DAI": dai = amount
                            elif code == "IVA": iva = amount

                        # Realizar cruce de llaves primarias
                        match = db_starship.get(summary, {"awb": "N/A", "tracking": "N/A"})
                        id_master = match["awb"] if match["awb"] != "N/A" else f"Desconocido_{f.name}"
                        
                        if id_master not in master_sessions:
                            master_sessions[id_master] = {"final_data": [], "processed_pdfs": []}
                            
                        master_sessions[id_master]["final_data"].append({
                            "master": id_master, "guia": summary, "awb": match["awb"], "tracking": match["tracking"],
                            "fob": fob, "freight": freight, "insurance": insurance, "cif": cif, "dai": dai, "iva": iva
                        })
                except Exception as e:
                    st.error(f"Error estructural en XML ({f.name}): {e}")

            # 3. Asignación avanzada de PDFs a sus Másters por concordancia de Guía
            if pdf_files:
                for pdf in pdf_files:
                    # Encontrar primer grupo de dígitos continuos en el nombre del archivo
                    match_num = re.match(r'^\d+', pdf.name) or re.search(r'\d+', pdf.name)
                    num_duca = match_num.group(0) if match_num else ""
                    new_name = f"Duca_{num_duca}.pdf" if num_duca else "---"
                    status = "success" if num_duca else "error"
                    
                    # Buscar a qué sesión de máster pertenece comparando la guía procesada
                    asignado = False
                    for m_id, session in master_sessions.items():
                        for data_row in session["final_data"]:
                            if num_duca in data_row["guia"] or data_row["guia"] in pdf.name:
                                session["processed_pdfs"].append({
                                    "file_bytes": pdf.read(), "original_name": pdf.name,
                                    "new_name": new_name, "status": status, "master": m_id
                                })
                                asignado = True
                                break
                        if asignado: break
                    if not asignado:
                        # Si no se cruza de forma limpia, inyectar en la primera sesión disponible
                        if master_sessions:
                            primer_master = list(master_sessions.keys())[0]
                            master_sessions[primer_master]["processed_pdfs"].append({
                                "file_bytes": pdf.read(), "original_name": pdf.name,
                                "new_name": new_name, "status": status, "master": primer_master
                            })

            st.session_state.master_sessions = master_sessions
            ir_a_paso(2)
    st.markdown("</div>", unsafe_allow_html=True)

# =========================================================================
# PASO 2: AUDITORÍA MATEMÁTICA Y AJUSTES DE FLETE AUTOMÁTICOS
# =========================================================================
elif st.session_state.step == 2:
    st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
    st.write("### 📊 Tablero de Auditoría y Control de Desajustes")
    
    # Aplanar las estructuras de la sesión para mostrarlas en un DataFrame unificado
    rows = []
    for m_id, sesion in st.session_state.master_sessions.items():
        for item in sesion["final_data"]:
            suma_calc = round(item["fob"] + item["freight"] + item["insurance"], 2)
            cif_val = round(item["cif"], 2)
            dif = round(cif_val - Glen := suma_calc, 2)
            
            rows.append({
                "Máster Asignado": item["master"], "Guía": item["guia"], "AWB": item["awb"], "Tracking": item["tracking"],
                "FOB": item["fob"], "Freight (Flete)": item["freight"], "Insurance (Seguro)": item["insurance"],
                "Suma Calc.": suma_calc, "Value For Duty (CIF)": cif_val, "Diferencia": dif
            })
            
    df_audit = pd.DataFrame(rows)
    
    # Filtros e Interacciones idénticas a la UI original
    col_btn1, col_btn2 = st.columns([1, 4])
    with col_btn1:
        solo_errores = st.toggle("👁️ Mostrar Solo Errores")
    if solo_errores:
        df_audit = df_audit[df_audit["Diferencia"] != 0.0]

    # Renderizar la tabla aplicando color de alerta a los errores detectados
    def highlight_errors(row):
        return ['background-color: #fff1f2; color: #991b1b' if row["Diferencia"] != 0.0 else '' for _ in row]
    
    st.dataframe(
        df_audit.style.apply(highlight_errors, axis=1).format(precision=2), 
        use_container_width=True, height=400
    )
    
    col_act1, col_act2 = st.columns(2)
    with col_act1:
        if st.button("🔧 Corregir Automáticamente (Ajustar Fletes)", type="secondary"):
            # Lógica aduanera exacta: Flete = CIF - FOB - Seguro
            for m_id, sesion in st.session_state.master_sessions.items():
                for item in sesion["final_data"]:
                    item["freight"] = round(item["cif"] - item["fob"] - item["insurance"], 2)
            st.success("Todos los fletes desalineados han sido ajustados al CIF.")
            st.rerun()
            
    with col_act2:
        if st.button("📥 Validar, Exportar y Procesar PDFs ➡️", type="primary"):
            ir_a_paso(3)
            
    st.markdown("</div>", unsafe_allow_html=True)

# =========================================================================
# PASO 3: CONSOLIDACIÓN DE PLANTILLA TEMU BILINGÜE Y MACRO-ZIP
# =========================================================================
elif st.session_state.step == 3:
    st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
    st.write("### 📦 Estado de Consolidación por Lotes Masivos")
    
    total_masters = len(st.session_state.master_sessions)
    st.info(f"🔗 **{total_masters} Másters** procesados en paralelo listos para empaquetado estructurado.")
    
    # Listar resumen de PDFs mapeados tal cual la tabla original
    pdf_rows = []
    for m_id, sesion in st.session_state.master_sessions.items():
        for p in sesion["processed_pdfs"]:
            pdf_rows.append({
                "Máster Origen": p["master"], "Archivo Original": p["original_name"],
                "Nuevo Nombre Estructurado": p["new_name"], "Estado": "✓ Listo" if p["status"] == "success" else "✗ Sin Números"
            })
            
    if pdf_rows:
        st.dataframe(pd.DataFrame(pdf_rows), use_container_width=True, height=250)
    else:
        st.warning("No se cargaron o vincularon PDFs en el lote actual.")

    if st.button("📦 Generar MACRO-ZIP Consolidado Final ✓", type="primary"):
        with st.spinner("Compilando arquitecturas ZIP y subiendo a TiDB Cloud..."):
            
            # Crear el buffer binario en memoria del MACRO-ZIP principal
            macro_zip_buffer = io.BytesIO()
            trackings_totales_lote = []
            
            with zipfile.ZipFile(macro_zip_buffer, "w", zipfile.ZIP_DEFLATED) as macro_zip:
                
                for m_name, session in st.session_state.master_sessions.items():
                    # 1. Reconstrucción estricta de las 19 Columnas Bilingües exigidas por Aduanas / TEMU
                    headers_temu = [
                        "Platform包裹号（必填）|Platform Package Number (required)", 
                        "包裹清关所属国家（必填）|Country (required)", 
                        "包裹清关所在省（非必填）|Province of customs clearance (optional)", 
                        "包裹收货所在省（非必填）|Province of receipt (optional)", 
                        "币种（申报金额与税费）（必填）|Currency (required)", 
                        "包裹的申报价值金额（必填）|Value For Duty (required)", 
                        "服务商申报包裹代缴税费总金额（必填）|Total payable amount (required)", 
                        "服务商申报包裹代缴关税总金额（必填）|Total Duty (required)", 
                        "服务商申报包裹代缴消费税金额（必填）|Total Excise Tax (required)", 
                        "服务商申报包裹代缴增值税金额（必填）|Total GST (required)", 
                        "服务商申报包裹代缴反倾销税金额（必填）|Total SIMA (required)", 
                        "服务商申报包裹代缴其他税金额（必填）|Total Other Tax (required)", 
                        "币种（手续费）|Currency（Service Fee)", 
                        "服务商申报包裹手续费（必填）|Service Fee (required)", 
                        "服务商单号（必填）|Logistics number(required)", 
                        "提单号（非必填）|AWB Number(optional)", 
                        "FOB价（必填）|FOB Price (required)", 
                        "运费（必填）|Freight (required)", 
                        "保险费（必填）|Insurance(required)"
                    ]
                    
                    rows_export = []
                    for row in session["final_data"]:
                        trackings_totales_lote.append(row["tracking"])
                        rows_export.append([
                            row["tracking"] if row["tracking"] != "N/A" else "", "El Salvador", "", "", "USD",
                            round(row["cif"], 2), round(row["dai"] + row["iva"], 2), round(row["dai"], 2),
                            0, round(row["iva"], 2), 0, 0, "USD", 0, row["guia"],
                            row["awb"] if row["awb"] != "N/A" else "",
                            round(row["fob"], 2), round(row["freight"], 2), round(row["insurance"], 2)
                        ])
                        
                    df_temu = pd.DataFrame(rows_export, columns=headers_temu)
                    
                    # Guardar excel del Máster a binario
                    excel_buffer = io.BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                        df_temu.to_excel(writer, index=False, sheet_name="Template")
                    
                    # Inyectar el Excel en la raíz del MACRO-ZIP
                    macro_zip.writestr(f"{m_name}.xlsx", excel_buffer.getvalue())
                    
                    # 2. Construir sub-ZIP exclusivo de PDFs de DUCAs para este Máster
                    if session["processed_pdfs"]:
                        sub_zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(sub_zip_buffer, "w", zipfile.ZIP_DEFLATED) as sub_zip:
                            for p in session["processed_pdfs"]:
                                if p["status"] == "success":
                                    sub_zip.writestr(p["new_name"], p["file_bytes"])
                                    
                        # Inyectar el sub-ZIP de PDFs al lado de su Excel
                        macro_zip.writestr(f"{m_name}_Ducas.zip", sub_zip_buffer.getvalue())

            # Guardar el binario finalizado en la sesión
            st.session_state.macro_zip_data = macro_zip_buffer.getvalue()
            
            # 3. PERSISTENCIA EN TIDB CLOUD (Sustituyendo por completo a IndexedDB)
            conn = conectar_tidb()
            if conn:
                cursor = conn.cursor()
                master_name_principal = list(st.session_state.master_sessions.keys())[0] if st.session_state.master_sessions else "Lote_Consolidado"
                search_index_text = ", ".join(filter(lambda x: x != "N/A", trackings_totales_lote))
                
                # Inyección SQL parametrizada directa a tu tabla control_ducas en la DB test
                query = "INSERT INTO control_ducas (master_name, search_data) VALUES (%s, %s)"
                cursor.execute(query, (f"Lote_{master_name_principal}", search_index_text))
                conn.commit()
                cursor.close()
                conn.close()
                
            ir_a_paso(4)
            
    st.markdown("</div>", unsafe_allow_html=True)

# =========================================================================
# PASO 4: PANTALLA DE ÉXITO Y DESCARGA DIRECTA
# =========================================================================
elif st.session_state.step == 4:
    st.markdown("<div class='finish-card'>", unsafe_allow_html=True)
    st.write("<div style='font-size: 4.5em;'>🎉</div>", unsafe_allow_html=True)
    st.write("## ¡Proceso por Lotes Completado de Forma Segura!")
    st.write("Los manifiestos Excel indexados y los paquetes ZIP individuales de las DUCAs han sido inyectados con éxito en la infraestructura central.")
    st.write("")
    
    # Botón nativo de descarga para el MACRO-ZIP masivo generado
    if st.session_state.macro_zip_data:
        st.download_button(
            label="📦 Descargar MACRO-ZIP Consolidado",
            data=st.session_state.macro_zip_data,
            file_name=f"Lote_Consolidado_Aduana_{int(datetime.now().timestamp())}.zip",
            mime="application/zip",
            type="primary"
        )
    st.write("")
    if st.button("+ Iniciar Nuevo Proceso"):
        st.session_state.master_sessions = {}
        st.session_state.macro_zip_data = None
        ir_a_paso(1)
        
    st.markdown("</div>", unsafe_allow_html=True)

# =========================================================================
# GESTOR DE HISTORIAL EN LA NUBE (Buscador SQL Avanzado Permanente)
# =========================================================================
st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
st.write("### 🗄️ Gestor de Manifiestos Históricos en la Nube")

query_busqueda = st.text_input(
    "Filtro Avanzado Cloud", 
    placeholder="🔍 Busca por Máster o pega múltiples Trackings/Guías separados por comas..."
)

if st.button("Consultar Base de Datos (TiDB)", type="secondary"):
    conn = conectar_tidb()
    if conn:
        cursor = conn.cursor(dictionary=True)
        if query_busqueda:
            # Replicar la búsqueda multitérmino exacta que hacías localmente
            terminos = [t.strip() for t in re.split(r'[\n\t,]+', query_busqueda) if t.strip()]
            if terminos:
                conditions = " OR ".join(["search_data LIKE %s OR master_name LIKE %s"] * len(terminos))
                params = []
                for t in terminos:
                    params.extend([f"%{t}%", f"%{t}%"])
                sql = f"SELECT id, master_name, fecha_procesado FROM control_ducas WHERE {conditions} ORDER BY fecha_procesado DESC"
                cursor.execute(sql, params)
            else:
                sql = "SELECT id, master_name, fecha_procesado FROM control_ducas ORDER BY fecha_procesado DESC LIMIT 15"
                cursor.execute(sql)
        else:
            sql = "SELECT id, master_name, fecha_procesado FROM control_ducas ORDER BY fecha_procesado DESC LIMIT 15"
            cursor.execute(sql)
            
        resultados = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if resultados:
            st.success(f"Se encontraron {len(resultados)} lotes coincidentes guardados en la nube por tu equipo:")
            df_res = pd.DataFrame(resultados)
            df_res.columns = ["ID Registro", "Identificador de Lote", "Fecha de Inyección"]
            st.table(df_res)
        else:
            st.warning("No se encontraron registros históricos en TiDB Cloud que coincidan con los términos ingresados.")
st.markdown("</div>", unsafe_allow_html=True)
