import streamlit as st
import pandas as pd
import requests
from io import StringIO
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import unicodedata
import sys

# --- MANEJO DE LIBRERÍAS (Seguridad de Importación y Entorno Nube) ---
def check_dependencies():
    """Verifica que las librerías críticas estén presentes para ejecución en nube."""
    required = ["streamlit", "pandas", "requests", "matplotlib", "numpy"]
    missing = []
    for lib in required:
        if lib not in sys.modules and lib not in globals():
            missing.append(lib)
    return missing

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Auditoría Acústica Bilbao - Abando", 
    page_icon="🔊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- DICCIONARIO MAESTRO: 32 SENSORES DE ABANDO (Distrito 6) ---
SENSORES_ABANDO = {
    'BI-RUI-001': 'RODRIGUEZ ARIAS', 'BI-RUI-020': 'POZA 48', 'BI-RUI-021': 'POZA 53',
    'BI-RUI-022': 'POZA 30', 'BI-RUI-025': 'PRINCIPE 1', 'BI-RUI-BR15': 'ALAMEDA URQUIJO',
    'BI-RUI-BR2': 'FRENTE IGLESIA', 'BI-RUI-C001': 'URIBITARTE 1', 'BI-RUI-C002': 'URIBITARTE 6',
    'BI-RUI-C003': 'MUELLE RIPA', 'BI-RUI-C004': 'ESCALINATAS DE URIBITARTE', 'BI-RUI-C008': 'RIPA 5',
    'BI-RUI-C010': 'ARBOLANTXA', 'BI-RUI-C011': 'JARDINES DE ALBIA', 'BI-RUI-C012': 'IBAÑEZ DE BILBAO',
    'BI-RUI-C013': 'COLÓN DE LARREÁTEGUI', 'BI-RUI-C014': 'IPARRAGUIRRE 16', 'BI-RUI-C015': 'JUAN DE AJURIAGUERRA',
    'BI-RUI-C016': 'DIPUTACIÓN 4', 'BI-RUI-C017': 'BERASTEGUI 4', 'BI-RUI-C018': 'LEDESMA 6',
    'BI-RUI-C019': 'LEDESMA 7', 'BI-RUI-C020': 'LEDESMA 10 bis', 'BI-RUI-C021': 'LEDESMA 30',
    'BI-RUI-C022': 'VILLARIAS 2', 'BI-RUI-C025': 'LUIS BRIÑAS', 'BI-RUI-C030': 'EGAÑA KALEA 6',
    'BI-RUI-C031': 'EGAÑA KALEA 22', 'BI-RUI-C032': 'PARTICULAR INDAUTXU', 'BI-RUI-C033': 'MAESTRO GARCÍA RIVERO',
    'BI-RUI-C034': 'ARETXABALETA 6', 'BI-RUI-P009': 'ALAMEDA RECALDE'
}

COLORES = {
    'Bueno': '#22c55e', 'Regular': '#f97316', 'Sin Datos': '#94a3b8',
    'Dia': '#f39c12', 'Noche': '#3498db', 'Finde': '#e74c3c'
}

# --- FUNCIONES DE SOPORTE Y LIMPIEZA ---

def limpiar_texto(texto):
    """Normaliza encabezados para evitar errores de codificación o espacios."""
    if not isinstance(texto, str): return str(texto)
    texto = "".join(c for c in unicodedata.normalize('NFD', texto) 
                  if unicodedata.category(c) != 'Mn')
    return texto.strip().upper()

def clasificar_periodo(dt):
    """Define si una medición es Diurna o Nocturna según normativa."""
    if pd.isna(dt): return "N/A"
    return "DIA" if 7 <= dt.hour < 23 else "NOCHE"

def sombreado_finde(ax, start, end):
    """Resalta visualmente los fines de semana en el eje temporal."""
    curr = datetime.combine(start, datetime.min.time())
    final = datetime.combine(end, datetime.max.time())
    while curr <= final:
        if curr.weekday() in [4, 5, 6]: # Vie (noche), Sáb, Dom
            alpha = 0.05 if curr.weekday() == 4 else 0.08
            ax.axvspan(curr, curr + timedelta(days=1), color=COLORES['Finde'], alpha=alpha)
        curr += timedelta(days=1)

def procesar_dataframe(df_raw):
    """Infiere columnas dinámicamente y limpia tipos de datos."""
    try:
        df_raw.columns = [limpiar_texto(c) for c in df_raw.columns]
        # Búsqueda de columnas clave por coincidencia parcial
        c_t = next(c for c in ['FECHA/HORA MEDICION', 'HORA', 'FECHA_HORA', 'FECHA'] if c in df_raw.columns)
        c_v = next(c for c in ['DECIBELIOS MEDIDOS', 'LAEQ', 'VALOR', 'LAEQ (DB)'] if c in df_raw.columns)
        c_id = next(c for c in ['CODIGO', 'ID_SONOMETRO', 'NOMBRE', 'SONOMETRO'] if c in df_raw.columns)
        
        df_raw['FECHA_DT'] = pd.to_datetime(df_raw[c_t], format='mixed', dayfirst=True, errors='coerce')
        df_raw['DECIBELIOS'] = pd.to_numeric(df_raw[c_v].astype(str).str.replace(',', '.'), errors='coerce')
        
        df = df_raw.dropna(subset=['FECHA_DT', 'DECIBELIOS', c_id]).copy()
        df['PERIODO'] = df['FECHA_DT'].apply(clasificar_periodo)
        return df, c_id
    except Exception as e:
        st.error(f"Fallo en el procesamiento de datos: {e}")
        return pd.DataFrame(), None

@st.cache_data(ttl=600, show_spinner=False)
def download_api_data():
    """Descarga datos desde Open Data Bilbao con reintentos para estabilidad en nube."""
    url = "https://www.bilbao.eus/aytoonline/jsp/opendata/movilidad/od_sonometro_mediciones.jsp?idioma=c&formato=csv"
    for _ in range(3):
        try:
            response = requests.get(url, timeout=12)
            response.raise_for_status()
            return response.text
        except:
            continue
    return None

# --- APLICACIÓN PRINCIPAL ---

def main():
    missing_libs = check_dependencies()
    if missing_libs:
        st.error(f"Error crítico: Faltan librerías: {missing_libs}")
        return

    st.sidebar.title("🛠️ Configuración")
    st.sidebar.markdown("---")
    
    metodo_carga = st.sidebar.radio(
        "Fuente de datos:", 
        ["🌐 API Bilbao (Directo)", "📥 CSV Manual (Respaldo)"],
        help="Si la API falla por restricciones de red, use la carga manual del CSV descargado."
    )
    
    csv_content = None
    if metodo_carga == "🌐 API Bilbao (Directo)":
        with st.sidebar.status("Conectando con Open Data..."):
            csv_content = download_api_data()
        if csv_content:
            st.sidebar.success("Datos actualizados desde la nube.")
        else:
            st.sidebar.error("Error de acceso a la API (Firewall).")
            st.sidebar.info("Use el modo 'CSV Manual' para continuar.")
    
    if metodo_carga == "📥 CSV Manual (Respaldo)":
        uploaded_file = st.sidebar.file_uploader("Subir mediciones.csv", type=["csv"])
        if uploaded_file:
            csv_content = uploaded_file.getvalue().decode('utf-8-sig')

    if not csv_content:
        st.title("🛡️ Auditoría Acústica - Bilbao")
        st.info("Esperando carga de datos para iniciar el análisis del Distrito Abando.")
        return

    try:
        df_raw_initial = pd.read_csv(StringIO(csv_content), sep=';', encoding='utf-8-sig')
        df_f, c_id = procesar_dataframe(df_raw_initial)
    except Exception as e:
        st.error(f"Error de lectura: {e}")
        return

    if df_f.empty:
        st.error("No se detectaron datos válidos en el archivo.")
        return

    # Selección de rango temporal
    st.sidebar.header("🗓️ Rango de Auditoría")
    f_min, f_max = df_f['FECHA_DT'].min().date(), df_f['FECHA_DT'].max().date()
    f_ini = st.sidebar.date_input("Fecha Inicio", f_max - timedelta(days=6), min_value=f_min, max_value=f_max)
    f_fin = st.sidebar.date_input("Fecha Fin", f_max, min_value=f_min, max_value=f_max)
    
    mask = (df_f['FECHA_DT'].dt.date >= f_ini) & (df_f['FECHA_DT'].dt.date <= f_fin)
    df_f = df_f[mask]

    st.title("🛡️ Auditoría Acústica - Distrito Abando")
    st.caption(f"Análisis basado en la red oficial de sonómetros municipales | {f_ini} a {f_fin}")

    tabs = st.tabs(["📊 Salud de Red", "📈 Análisis Temporal", "🏆 Rankings Críticos"])

    # PESTAÑA 1: SALUD DE RED (Auditoría de Calidad)
    with tabs[0]:
        st.subheader("Auditoría de Disponibilidad de Datos")
        dias = (f_fin - f_ini).days + 1
        objetivo_teorico = dias * 96 # Mediciones cada 15 min
        
        calidad_resumen = []
        activos = []
        for sid, calle in SENSORES_ABANDO.items():
            registros_sensor = len(df_f[df_f[c_id] == sid])
            porcentaje = min(round((registros_sensor / objetivo_teorico) * 100, 1), 100.0) if objetivo_teorico > 0 else 0
            # Lógica de semáforo oficial
            if porcentaje >= 85: est, col = "Bueno", COLORES['Bueno']
            elif porcentaje > 0: est, col = "Regular", COLORES['Regular']
            else: est, col = "Sin Datos", COLORES['Sin Datos']
            
            if registros_sensor > 0: activos.append(sid)
            calidad_resumen.append({'Ubicación': calle, 'ID': sid, 'Disp %': porcentaje, 'Estado': est, 'Hex': col})
        
        df_q = pd.DataFrame(calidad_resumen)
        
        c1, c2 = st.columns([1, 1.5])
        with c1:
            stats = df_q['Estado'].value_counts().reindex(['Bueno', 'Regular', 'Sin Datos'], fill_value=0)
            fig_p, ax_p = plt.subplots()
            ax_p.pie(stats, labels=stats.index, autopct='%1.1f%%', colors=[COLORES['Bueno'], COLORES['Regular'], COLORES['Sin Datos']], startangle=140)
            st.pyplot(fig_p)
        with c2:
            df_q_plot = df_q.sort_values('Disp %')
            fig_b, ax_b = plt.subplots(figsize=(8, 10))
            ax_b.barh(df_q_plot['Ubicación'], df_q_plot['Disp %'], color=df_q_plot['Hex'])
            ax_b.set_xlim(0, 100)
            ax_b.set_xlabel("Disponibilidad (%)")
            st.pyplot(fig_b)
        
        st.markdown("---")
        st.subheader("Inventario Detallado de Sensores")
        st.dataframe(df_q[['Ubicación', 'ID', 'Disp %', 'Estado']].sort_values('Estado'), use_container_width=True, hide_index=True)

    # PESTAÑA 2: ANÁLISIS TEMPORAL
    with tabs[1]:
        if not activos:
            st.warning("No hay datos disponibles para el Distrito Abando en estas fechas.")
        else:
            sel_sid = st.selectbox("Seleccione Sensor para detalle:", activos, format_func=lambda x: f"{SENSORES_ABANDO.get(x, x)} ({x})")
            sub_df = df_f[df_f[c_id] == sel_sid].copy()
            # Resample para forzar huecos visuales en el gráfico
            sub_df = sub_df.set_index('FECHA_DT').resample('15min').mean(numeric_only=True).reset_index()
            sub_df['PERIODO'] = sub_df['FECHA_DT'].apply(clasificar_periodo)
            
            fig_t, ax_t = plt.subplots(figsize=(14, 6))
            # Separamos líneas para evitar trazos diagonales entre periodos distintos
            df_d = sub_df.copy(); df_d.loc[df_d['PERIODO'] != 'DIA', 'DECIBELIOS'] = np.nan
            df_n = sub_df.copy(); df_n.loc[df_n['PERIODO'] != 'NOCHE', 'DECIBELIOS'] = np.nan
            
            ax_t.plot(df_d['FECHA_DT'], df_d['DECIBELIOS'], color=COLORES['Dia'], label='Día (07-23h)', lw=1.5)
            ax_t.plot(df_n['FECHA_DT'], df_n['DECIBELIOS'], color=COLORES['Noche'], label='Noche (23-07h)', lw=1.5)
            
            ax_t.axhline(65, color='red', ls='--', alpha=0.5, label='Límite Día (65dB)')
            ax_t.axhline(55, color='blue', ls='--', alpha=0.5, label='Límite Noche (55dB)')
            
            sombreado_finde(ax_t, f_ini, f_fin)
            ax_t.set_ylabel("Nivel Sonoro LAeq (dB)")
            ax_t.xaxis.set_major_formatter(mdates.DateFormatter('%d %b\n%H:%M'))
            ax_t.set_ylim(35, 95)
            ax_t.legend(ncol=2, loc='upper center', bbox_to_anchor=(0.5, -0.15))
            st.pyplot(fig_t)

    # PESTAÑA 3: RANKINGS CRÍTICOS
    with tabs[2]:
        ranking_data = []
        for sid in activos:
            d_s = df_f[df_f[c_id] == sid]
            r_dia = d_s[d_s['PERIODO'] == 'DIA']['DECIBELIOS']
            r_noche = d_s[d_s['PERIODO'] == 'NOCHE']['DECIBELIOS']
            ranking_data.append({
                'Ubicación': SENSORES_ABANDO.get(sid, sid),
                'Máx Día (dB)': r_dia.max() if not r_dia.empty else 0,
                'Prom Noche (dB)': round(r_noche.mean(), 1) if not r_noche.empty else 0
            })
        
        df_rank = pd.DataFrame(ranking_data)
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            st.subheader("☀️ Puntos con Mayor Impacto Diurno")
            st.dataframe(df_rank.sort_values('Máx Día (dB)', ascending=False).head(10), hide_index=True)
        with col_r2:
            st.subheader("🌙 Puntos más Ruidosos (Promedio Noche)")
            st.dataframe(df_rank.sort_values('Prom Noche (dB)', ascending=False).head(10), hide_index=True)

if __name__ == "__main__":
    main()
