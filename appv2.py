import streamlit as st
import pandas as pd
import requests
from io import StringIO
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import unicodedata

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Auditoría Acústica Bilbao - Abando", 
    page_icon="🔊",
    layout="wide"
)

# --- DICCIONARIO MAESTRO: 32 SENSORES DE ABANDO ---
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

# --- FUNCIONES DE UTILIDAD ---

def limpiar_texto(texto):
    if not isinstance(texto, str): return texto
    texto = unicodedata.normalize('NFD', texto).encode('ascii', 'ignore').decode("utf-8")
    return texto.strip().upper()

def clasificar_periodo(dt):
    if not isinstance(dt, datetime): return "N/A"
    return "DIA" if 7 <= dt.hour < 23 else "NOCHE"

def procesar_csv(csv_content):
    # Detección flexible de separador para archivos locales o remotos
    try:
        df = pd.read_csv(StringIO(csv_content), sep=';', encoding='utf-8-sig')
        if len(df.columns) < 2: # Re-intento si el separador es coma
            df = pd.read_csv(StringIO(csv_content), sep=',', encoding='utf-8-sig')
    except:
        df = pd.read_csv(StringIO(csv_content), sep=None, engine='python', encoding='utf-8-sig')
        
    df.columns = [limpiar_texto(c) for c in df.columns]
    
    # Identificación dinámica de columnas basada en el CSV de Bilbao
    c_t = next(c for c in ['FECHA/HORA MEDICION', 'HORA', 'FECHA'] if c in df.columns)
    c_v = next(c for c in ['DECIBELIOS MEDIDOS', 'LAEQ', 'DECIBELIOS'] if c in df.columns)
    c_id = next(c for c in ['CODIGO', 'ID_SONOMETRO', 'ID'] if c in df.columns)
    
    # El formato ISO (2026-04-01 00:00:00.71) se lee mejor con dayfirst=False o automático
    df['FECHA_DT'] = pd.to_datetime(df[c_t], errors='coerce')
    
    # Limpieza de valores numéricos
    df['DECIBELIOS'] = pd.to_numeric(df[c_v].astype(str).str.replace(',', '.'), errors='coerce')
    
    # Filtrado por distrito (Solo sensores en el diccionario de Abando)
    df = df[df[c_id].isin(SENSORES_ABANDO.keys())]
    
    df = df.dropna(subset=['FECHA_DT', 'DECIBELIOS'])
    df['PERIODO'] = df['FECHA_DT'].apply(clasificar_periodo)
    return df.sort_values('FECHA_DT'), c_id

# --- GENERACIÓN DE GRÁFICOS ---

def generar_grafico_unico(df_sel, nombre_calle, id_sensor, f_ini_dt, f_fin_dt):
    fig, ax = plt.subplots(figsize=(12, 6))
    df_plot = df_sel.set_index('FECHA_DT').resample('15min').mean(numeric_only=True).reset_index()
    df_plot['PERIODO'] = df_plot['FECHA_DT'].apply(clasificar_periodo)

    for i in range(len(df_plot)-1):
        p1, p2 = df_plot.iloc[i], df_plot.iloc[i+1]
        color = '#f39c12' if p1['PERIODO'] == 'DIA' else '#3498db'
        if pd.notna(p1['DECIBELIOS']) and pd.notna(p2['DECIBELIOS']):
            ax.plot([p1['FECHA_DT'], p2['FECHA_DT']], [p1['DECIBELIOS'], p2['DECIBELIOS']], color=color, linewidth=2)

    ax.axhline(65, color='red', linestyle='--', alpha=0.6, label="Límite Día (65dB)")
    ax.axhline(55, color='blue', linestyle='--', alpha=0.6, label="Límite Noche (55dB)")
    ax.set_title(f"{nombre_calle} ({id_sensor})\nPeriodo: {f_ini_dt.date()} a {f_fin_dt.date()}", fontsize=11)
    ax.set_ylabel("Nivel de presión sonora dB(A)", fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m %H:%M'))
    plt.xticks(rotation=45)
    return fig

# --- APLICACIÓN PRINCIPAL ---

def main():
    st.title("🔊 Auditoría Acústica Bilbao - Distrito Abando")
    st.markdown("---")
    
    df_raw, c_id = None, None
    
    # --- PANEL DE CONTROL LATERAL ---
    st.sidebar.header("📂 Gestión de Datos")
    
    # Detección de entorno (Simulación para el usuario)
    entorno = "Nube (Streamlit Cloud)" if "streamlit" in str(st.sidebar) else "Local (Mac)"
    st.sidebar.caption(f"Ejecutando en: {entorno}")
    
    metodo = st.sidebar.radio("Selecciona método de ingesta:", 
                             ["Carga Manual (.csv)", "Descarga Automática"])

    if metodo == "Descarga Automática":
        url = "https://www.bilbao.eus/aytoonline/jsp/opendata/movilidad/od_sonometro_mediciones.jsp?idioma=c&formato=csv"
        if st.sidebar.button("🚀 Sincronizar con Bilbao"):
            try:
                with st.spinner('Intentando conectar con Open Data Bilbao...'):
                    # Timeout generoso para el servidor municipal
                    r = requests.get(url, timeout=20)
                    r.raise_for_status()
                    df_raw, c_id = procesar_csv(r.text)
                    st.success("✅ Sincronización automática exitosa")
            except Exception as e:
                st.error("❌ Error de conexión.")
                st.warning("El Firewall del ayuntamiento suele bloquear accesos desde la nube. Por favor, descarga el CSV y usa la 'Carga Manual'.")
    else:
        file = st.sidebar.file_uploader("Sube el archivo CSV oficial", type=['csv'])
        if file:
            try:
                content = file.getvalue().decode("utf-8-sig")
                df_raw, c_id = procesar_csv(content)
                st.success(f"✅ Archivo local cargado: {len(df_raw)} registros de Abando.")
            except Exception as e:
                st.error(f"Error al leer el archivo: {e}")

    # --- CUERPO DEL DASHBOARD ---
    if df_raw is not None:
        # Filtros temporales
        f_min_data = df_raw['FECHA_DT'].min().date()
        f_max_data = df_raw['FECHA_DT'].max().date()
        
        st.sidebar.subheader("🗓️ Rango de Análisis")
        f_ini = st.sidebar.date_input("Fecha Inicio", f_min_data)
        f_fin = st.sidebar.date_input("Fecha Fin", f_max_data)
        
        f_ini_dt = datetime.combine(f_ini, datetime.min.time())
        f_fin_dt = datetime.combine(f_fin, datetime.max.time())
        
        df_f = df_raw[(df_raw['FECHA_DT'] >= f_ini_dt) & (df_raw['FECHA_DT'] <= f_fin_dt)].copy()
        dias_calculados = max((f_fin - f_ini).days + 1, 1)

        # Tabs en el orden solicitado: Calidad -> Gráficos -> Rankings
        tabs = st.tabs(["🛡️ Auditoría de Calidad", "📉 Análisis Temporal", "🏆 Rankings y Picos"])

        # TAB 1: CALIDAD
        with tabs[0]:
            st.header("🛡️ Integridad de la Red de Sensores")
            st.write(f"Evaluación del cumplimiento de muestras (96 diarias esperadas) para el distrito de Abando.")
            
            calidad_list = []
            color_map = {"Bueno": "#2ecc71", "Regular": "#f39c12", "Crítico": "#e74c3c", "Sin Datos": "#95a5a6"}
            
            for sid, calle in SENSORES_ABANDO.items():
                muestras = len(df_f[df_f[c_id] == sid])
                esperado = dias_calculados * 96
                porcentaje = min(round((muestras / esperado) * 100, 1), 100.0) if esperado > 0 else 0
                
                if porcentaje >= 90: est = "Bueno"
                elif porcentaje > 30: est = "Regular"
                elif porcentaje > 0: est = "Crítico"
                else: est = "Sin Datos"
                
                calidad_list.append({'Calle': calle, 'ID': sid, 'Muestras': muestras, '% Calidad': porcentaje, 'Estado': est, 'Color': color_map[est]})
            
            df_q = pd.DataFrame(calidad_list).sort_values('% Calidad', ascending=False)
            
            cq1, cq2 = st.columns([1, 1.3])
            with cq1:
                counts = df_q['Estado'].value_counts()
                fig_pie, ax_pie = plt.subplots()
                ax_pie.pie(counts, labels=counts.index, autopct='%1.1f%%', 
                          colors=[color_map.get(x, "#95a5a6") for x in counts.index], startangle=90)
                st.pyplot(fig_pie)
            
            with cq2:
                fig_bar, ax_bar = plt.subplots(figsize=(7, 10))
                ax_bar.barh(df_q['Calle'], df_q['% Calidad'], color=df_q['Color'])
                ax_bar.invert_yaxis()
                ax_bar.set_xlabel("% de datos recibidos vs esperado")
                st.pyplot(fig_bar)
            
            st.dataframe(df_q[['Calle', 'ID', 'Muestras', '% Calidad', 'Estado']], 
                         hide_index=True, use_container_width=True)

        # TAB 2: GRÁFICOS
        with tabs[1]:
            st.header("📉 Evolución de Niveles Sonoros")
            sel_id = st.selectbox("Selecciona punto de medida", 
                                 list(SENSORES_ABANDO.keys()), 
                                 format_func=lambda x: f"{SENSORES_ABANDO[x]} ({x})")
            
            df_sensor = df_f[df_f[c_id] == sel_id]
            if not df_sensor.empty:
                st.pyplot(generar_grafico_unico(df_sensor, SENSORES_ABANDO[sel_id], sel_id, f_ini_dt, f_fin_dt))
            else:
                st.warning("No hay datos para este sensor en las fechas elegidas.")

        # TAB 3: RANKINGS
        with tabs[2]:
            st.header("🏆 Picos de Ruido Registrados")
            
            rankings = []
            for sid, calle in SENSORES_ABANDO.items():
                ds = df_f[df_f[c_id] == sid]
                if not ds.empty:
                    # Pico día
                    df_d = ds[ds['PERIODO'] == 'DIA']
                    pico_d = df_d.loc[df_d['DECIBELIOS'].idxmax()] if not df_d.empty else None
                    # Pico noche
                    df_n = ds[ds['PERIODO'] == 'NOCHE']
                    pico_n = df_n.loc[df_n['DECIBELIOS'].idxmax()] if not df_n.empty else None
                    
                    rankings.append({
                        'Calle': calle,
                        'dB Máx Día': pico_d['DECIBELIOS'] if pico_d is not None else 0,
                        'Fecha/Hora Día': pico_d['FECHA_DT'].strftime('%d/%m %H:%M') if pico_d is not None else "-",
                        'dB Máx Noche': pico_n['DECIBELIOS'] if pico_n is not None else 0,
                        'Fecha/Hora Noche': pico_n['FECHA_DT'].strftime('%d/%m %H:%M') if pico_n is not None else "-"
                    })
            
            if rankings:
                df_r = pd.DataFrame(rankings)
                cr1, cr2 = st.columns(2)
                with cr1:
                    st.subheader("☀️ Top 10 Ruidosos (Diurno)")
                    st.dataframe(df_r.sort_values('dB Máx Día', ascending=False).head(10)[['Calle', 'dB Máx Día', 'Fecha/Hora Día']], 
                                 hide_index=True, use_container_width=True)
                with cr2:
                    st.subheader("🌙 Top 10 Ruidosos (Nocturno)")
                    st.dataframe(df_r.sort_values('dB Máx Noche', ascending=False).head(10)[['Calle', 'dB Máx Noche', 'Fecha/Hora Noche']], 
                                 hide_index=True, use_container_width=True)
            else:
                st.info("Sin datos para generar rankings.")
    else:
        st.info("👈 Por favor, carga un archivo CSV o intenta la descarga automática desde el panel lateral.")

if __name__ == "__main__":
    main()
