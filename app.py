import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
import mysql.connector
import zipfile
import io
import time

# Configuración de la página premium
st.set_page_config(page_title="Suite Aduanera Pro", page_icon="📦", layout="wide")

st.title("Suite Aduanera Pro 🚀")
st.subheader("Flujo Multi-Máster Consolidado en la Nube")

# --- CONEXIÓN A TiDB (Utilizando los Secrets seguros de Streamlit) ---
def conectar_tidb():
    try:
        return mysql.connector.connect(
            host=st.secrets["tidb"]["host"],
            user=st.secrets["tidb"]["user"],
            password=st.secrets["tidb"]["password"],
            database=st.secrets["tidb"]["database"],
            port=st.secrets["tidb"]["port"],
            ssl_verify_identity=True # TiDB Cloud requiere SSL por seguridad
        )
    except Exception as e:
        st.error(f"❌ Error de conexión con TiDB: {e}")
        return None

# --- CREACIÓN DE PESTAÑAS (Simula tu Stepper de HTML) ---
tab1, tab2, tab3 = st.tabs(["📁 1. Datos Base", "📊 2. Auditoría y Cuadre", "🗄️ 3. Historial Cloud"])

# --- PASO 1: DATOS BASE ---
with tab1:
    st.header("Carga de Archivos Masivos")
    col1, col2 = st.columns(2)
    
    with col1:
        xml_files = st.file_uploader("Arrastra los XMLs de tus Másters aquí", accept_multiple_files=True, type=["xml"])
    with col2:
        excel_files = st.file_uploader("Arrastra los Excel (StarShip) aquí", accept_multiple_files=True, type=["xlsx", "xls"])

    # Inicializar estados en la sesión para guardar datos entre clics
    if "df_auditoria" not in st.session_state:
        st.session_state.df_auditoria = None

    if st.button("Procesar y Avanzar ➡️", type="primary"):
        if not xml_files or not excel_files:
            st.warning("⚠️ Por favor, sube tanto los archivos XML como los archivos Excel para continuar.")
        else:
            with st.spinner("Parseando XMLs y cruzando con StarShip..."):
                # 1. Parsear XMLs
                lista_xml = []
                for f in xml_files:
                    try:
                        tree = ET.parse(f)
                        root = tree.getroot()
                        # Buscamos los items en el XML (ajusta los tags según tus XMLs reales)
                        for item in root.findall('.//Item'):
                            guia = item.find('.//Summary_declaration').text if item.find('.//Summary_declaration') is not None else ""
                            fob = float(item.find('.//Item_Invoice_Amount_national_currency').text or 0)
                            freight = float(item.find('.//item_external_freight_Amount_national_currency').text or 0)
                            insurance = float(item.find('.//item_insurance_Amount_national_currency').text or 0)
                            cif = float(item.find('.//Total_CIF_itm').text or 0)
                            
                            lista_xml.append({
                                "guia": guia.strip(), "fob": fob, "freight": freight, "insurance": insurance, "cif": cif
                            })
                    except Exception as e:
                        st.error(f"Error leyendo XML {f.name}: {e}")

                df_xml = pd.DataFrame(lista_xml)

                # 2. Leer Excels (StarShip)
                lista_excel = []
                for f in excel_files:
                    df_temp = pd.read_excel(f, skiprows=2) # Se salta 2 filas como en tu JS
                    # Mapeo básico de columnas (Ajustar índices/nombres según StarShip)
                    if len(df_temp.columns) >= 27:
                        df_resumen = df_temp.iloc[:, [1, 2, 26]].copy()
                        df_resumen.columns = ["awb", "tracking", "guia_starship"]
                        lista_excel.append(df_resumen)
                
                if lista_excel:
                    df_starship = pd.concat(lista_excel).dropna(subset=["guia_starship"])
                    df_starship["guia_starship"] = df_starship["guia_starship"].astype(str).str.strip()
                    
                    # 3. Cruce de Datos (Mismo comportamiento que tu JS)
                    df_xml["guia"] = df_xml["guia"].astype(str).str.strip()
                    df_final = pd.merge(df_xml, df_starship, left_on="guia", right_on="guia_starship", how="left")
                    
                    # Calcular totales y diferencias
                    df_final["suma_calc"] = df_final["fob"] + df_final["freight"] + df_final["insurance"]
                    df_final["diferencia"] = df_final["cif"] - df_final["suma_calc"]
                    
                    st.session_state.df_auditoria = df_final
                    st.success("🎉 ¡Cruce de datos completado con éxito! Ve a la pestaña '2. Auditoría y Cuadre'.")
                else:
                    st.error("No se pudieron extraer datos válidos del Excel.")

# --- PASO 2: AUDITORÍA Y GUARDADO ---
with tab2:
    st.header("Auditoría de Guías e Impuestos")
    
    if st.session_state.df_auditoria is not None:
        df = st.session_state.df_auditoria
        
        # Filtro de errores (Diferencia != 0)
        solo_errores = st.checkbox("👁️ Mostrar solo desajustes (Errores de flete)")
        if solo_errores:
            df_mostrar = df[df["diferencia"].round(2) != 0]
        else:
            df_mostrar = df
            
        st.dataframe(df_mostrar, use_container_width=True)
        
        # Botón de Corrección Automática
        if st.button("🔧 Corregir Fletes Automáticamente"):
            df["freight"] = df["cif"] - df["fob"] - df["insurance"]
            df["suma_calc"] = df["fob"] + df["freight"] + df["insurance"]
            df["diferencia"] = df["cif"] - df["suma_calc"]
            st.session_state.df_auditoria = df
            st.rerun()
            
        # Botón para GUARDAR EN TiDB (Reemplaza IndexedDB)
        if st.button("📥 Validar y Guardar en Historial Cloud (TiDB)", type="primary"):
            conn = conectar_tidb()
            if conn:
                cursor = conn.cursor()
                # Recopilamos datos clave para el buscador masivo (Trackings y Guías)
                trackings_texto = ", ".join(df["tracking"].dropna().astype(str).tolist())
                master_ejemplo = str(df["awb"].iloc[0]) if "awb" in df.columns and not df.empty else "Lote_Desconocido"
                
                # Insertamos en la tabla que creaste (Ajusta el nombre si usaste control_ducas)
                sql = """INSERT INTO control_ducas (master_name, search_data) VALUES (%s, %s)"""
                valores = (master_ejemplo, trackings_texto)
                
                cursor.execute(sql, valores)
                conn.commit()
                cursor.close()
                conn.close()
                st.success(f"💾 Lote del Máster '{master_ejemplo}' guardado exitosamente en TiDB Cloud.")
    else:
        st.info("Aún no has procesado datos en la pestaña 1.")

# --- PASO 3: HISTORIAL EN LA NUBE (TiDB) ---
with tab3:
    st.header("Gestor de Archivos y Búsquedas en la Nube")
    busqueda = st.text_input("🔍 Buscar por Máster, Guía o Tracking (Puedes pegar varios separados por comas):")
    
    if st.button("Buscar en Base de Datos"):
        conn = conectar_tidb()
        if conn:
            cursor = conn.cursor(dictionary=True)
            if busqueda:
                # Búsqueda inteligente SQL utilizando LIKE
                sql = "SELECT id, master_name, fecha_procesado FROM control_ducas WHERE search_data LIKE %s OR master_name LIKE %s ORDER BY fecha_procesado DESC"
                param = f"%{busqueda}%"
                cursor.execute(sql, (param, param))
            else:
                sql = "SELECT id, master_name, fecha_procesado FROM control_ducas ORDER BY fecha_procesado DESC LIMIT 20"
                cursor.execute(sql)
                
            resultados = cursor.fetchall()
            cursor.close()
            conn.close()
            
            if resultados:
                st.write(f"Se encontraron {len(resultados)} registros históricos:")
                st.table(pd.DataFrame(resultados))
            else:
                st.warning("No se encontraron registros con esos términos.")
