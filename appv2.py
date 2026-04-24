import streamlit as st
import pandas as pd
import requests
from io import StringIO
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import unicodedata
from datetime import datetime, timedelta

# Intentamos importar seaborn para los mapas de calor, con fallback si falla
try:
    import seaborn as sns
    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Auditoría Acústica Bilbao - Abando", 
    page_icon="🔊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CONSTANTES Y DICCIONARIOS ---
# Diccionario maestro de los 32 sonómetros instalados en el distrito de Abando
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

# Paleta de colores corporativa para la auditoría
COLORES = {
    'Bueno': '#22c55e',    # Verde (Cumple normativa)
    'Regular': '#f59e0b',  # Naranja (Alerta)
    'Critico': '#ef4444',  # Rojo (Supera límites)
    'Sin Datos': '#94a3b8', # Gris (Fallo de sensor)
    'Dia': '#f39c12',      # Naranja (07:00 - 23:00)
    'Noche': '#3498db',    # Azul (23:00 - 07:00)
    'Finde': '#e74c3c'     # Rojo suave para fines de semana
}

# --- FUNCIONES DE UTILIDAD Y PROCESAMIENTO ---

def limpiar_texto(texto):
    """Normaliza cadenas de texto para evitar errores de codificación en columnas."""
    if not isinstance(texto, str): return texto
    return "".join(c for c in unicodedata.normalize('NFD', texto) 
                  if unicodedata.category(c) != 'Mn').strip().upper()

def clasificar_periodo(dt):
    """Clasifica una marca de tiempo según la normativa de ruido de Bilbao."""
    if not isinstance(dt, datetime): return "N/A"
    return "DIA" if 7 <= dt.hour < 23 else "NOCHE"

def sombreado_finde(ax, start, end):
    """Añade una capa visual para identificar rápidamente el fin de semana en gráficas."""
    curr = start.replace(hour=0, minute=0, second=0)
    while curr <= end:
        if curr.weekday() in [4, 5, 6]: # Viernes, Sábado, Domingo
            # El viernes se sombrea con menos opacidad (solo tarde/noche)
            alpha = 0.05 if curr.weekday() == 4 else 0.15
            ax.axvspan(curr, curr + timedelta(days=1), color=COLORES['Finde'], alpha=alpha)
        curr += timedelta(days=1)

def procesar_fuente_datos(df):
    """Realiza la limpieza, tipado y feature engineering de los datos crudos."""
    df.columns = [limpiar_texto(c) for c in df.columns]
    
    # Búsqueda dinámica de columnas (la API a veces cambia nombres de cabecera)
    posibles_fechas = ['FECHA/HORA MEDICION', 'HORA', 'FECHA_HORA', 'TIMESTAMP']
    posibles_valores = ['DECIBELIOS MEDIDOS', 'LAEQ', 'VALOR', 'MEDICION', 'DB']
    posibles_id = ['CODIGO', 'ID_SONOMETRO', 'NOMBRE', 'ID', 'SENSOR']
    
    try:
        col_fecha = next(c for c in posibles_fechas if c in df.columns)
        col_valor = next(c for c in posibles_valores if c in df.columns)
        col_id = next(c for c in posibles_id if c in df.columns)
        
        # Conversión segura de tipos
        df['FECHA_DT'] = pd.to_datetime(df[col_fecha], format='mixed', dayfirst=True, errors='coerce')
        df['DECIBELIOS'] = pd.to_numeric(df[col_valor].astype(str).str.replace(',', '.'), errors='coerce')
        
        # Limpieza de nulos críticos
        df = df.dropna(subset=['FECHA_DT', 'DECIBELIOS']).sort_values('FECHA_DT')
        
        # Enriquecimiento de datos para análisis temporal
        df['PERIODO'] = df['FECHA_DT'].apply(clasificar_periodo)
        df['DIA_SEMANA'] = df['FECHA_DT'].dt.day_name()
        df['HORA_INT'] = df['FECHA_DT'].dt.hour
        
        return df, col_id
    except StopIteration:
        st.error("🚨 Error: El archivo no cumple con el esquema de datos de sonometría de Bilbao.")
        return None, None

def calcular_estadisticas_avanzadas(df_sensor):
    """Calcula indicadores acústicos técnicos para el informe detallado."""
    if df_sensor.empty: return {}
    vals = df_sensor['DECIBELIOS']
    return {
        'Lmax': vals.max(),
        'Lmin': vals.min(),
        'Leq': vals.mean(),
        'L90': np.percentile(vals, 10), # Ruido de fondo
        'L10': np.percentile(vals, 90), # Ruido de eventos (picos)
        'Infracciones': len(df_sensor[(df_sensor['PERIODO'] == 'DIA') & (vals > 65)]) + 
                        len(df_sensor[(df_sensor['PERIODO'] == 'NOCHE') & (vals > 55)])
    }

# --- INTERFAZ DE USUARIO (STREAMLIT) ---

def main():
    st.sidebar.image("https://www.bilbao.eus/aytoonline/static/img/logo_bilbao.png", width=160)
    st.sidebar.title("Auditoría Acústica")
    st.sidebar.markdown("Sistema de monitorización de ruido del Distrito de Abando.")
    
    # Gestión de entrada de datos
    fuente = st.sidebar.radio("Fuente de datos:", ["🌐 API Open Data Bilbao", "📂 Archivo CSV Local"])
    
    df_raw, col_id = None, None
    
    if fuente == "🌐 API Open Data Bilbao":
        if st.sidebar.button("🔄 Sincronizar Datos"):
            with st.spinner("Descargando últimas mediciones..."):
                url = "https://www.bilbao.eus/aytoonline/jsp/opendata/movilidad/od_sonometro_mediciones.jsp?idioma=c&formato=csv"
                try:
                    r = requests.get(url, timeout=15)
                    if r.status_code == 200:
                        df_raw, col_id = procesar_fuente_datos(pd.read_csv(StringIO(r.text), sep=';'))
                        st.session_state['cache_data'] = (df_raw, col_id)
                        st.sidebar.success("Conexión exitosa.")
                    else: st.sidebar.error(f"Error API: {r.status_code}")
                except Exception as e: st.sidebar.error(f"Error de red: {e}")
        elif 'cache_data' in st.session_state:
            df_raw, col_id = st.session_state['cache_data']
    else:
        file = st.sidebar.file_uploader("Subir CSV de exportación", type=['csv'])
        if file:
            df_raw, col_id = procesar_fuente_datos(pd.read_csv(file, sep=None, engine='python'))

    if df_raw is not None:
        # Panel de Filtros Temporales
        st.sidebar.markdown("---")
        st.sidebar.subheader("Rango de Auditoría")
        f_min, f_max = df_raw['FECHA_DT'].min().date(), df_raw['FECHA_DT'].max().date()
        date_sel = st.sidebar.date_input("Periodo de análisis:", [f_max - timedelta(days=7), f_max], min_value=f_min, max_value=f_max)
        
        if len(date_sel) == 2:
            mask = (df_raw['FECHA_DT'].dt.date >= date_sel[0]) & (df_raw['FECHA_DT'].dt.date <= date_sel[1])
            df_f = df_raw[mask].copy()
            
            st.title("📊 Informe de Contaminación Acústica")
            st.caption(f"Distrito 6 (Abando) | Periodo: {date_sel[0]} al {date_sel[1]}")

            tab1, tab2, tab3, tab4 = st.tabs(["🛡️ Estado de Red", "📈 Análisis Sensor", "🌓 Impacto Nocturno", "📄 Reporte"])

            # PESTAÑA 1: CALIDAD DE LA RED
            with tab1:
                st.header("Disponibilidad y Calidad de Datos")
                dias_estudio = (date_sel[1] - date_sel[0]).days + 1
                objetivo = dias_estudio * 96 # 15 min intervalos
                
                resumen_calidad = []
                sensores_con_datos = []
                for sid, calle in SENSORES_ABANDO.items():
                    cant = len(df_f[df_f[col_id] == sid])
                    pct = min(100.0, (cant / objetivo) * 100) if objetivo > 0 else 0
                    if cant > 0: sensores_con_datos.append(sid)
                    resumen_calidad.append({
                        'Calle': calle, 'ID': sid, 
                        'Disponibilidad %': round(pct, 1),
                        'Estado': "Bueno" if pct >= 85 else ("Regular" if pct > 0 else "Offline")
                    })
                
                df_q = pd.DataFrame(resumen_calidad)
                col_c1, col_c2 = st.columns([1, 1.5])
                with col_c1:
                    fig_q, ax_q = plt.subplots()
                    v_counts = df_q['Estado'].value_counts()
                    ax_q.pie(v_counts, labels=v_counts.index, autopct='%1.1f%%', 
                            colors=[COLORES['Bueno'], COLORES['Regular'], COLORES['Sin Datos']])
                    st.pyplot(fig_q)
                with col_c2:
                    st.dataframe(df_q.sort_values('Disponibilidad %', ascending=False), hide_index=True)

            # PESTAÑA 2: ANÁLISIS DETALLADO
            with tab2:
                if not sensores_con_datos:
                    st.warning("No se encontraron datos para los sensores de Abando en este rango.")
                else:
                    sel_sid = st.selectbox("Seleccione ubicación a auditar:", sensores_con_datos, 
                                         format_func=lambda x: f"{SENSORES_ABANDO.get(x, x)} ({x})")
                    df_s = df_f[df_f[col_id] == sel_sid].copy()
                    
                    # KPIs
                    stats = calcular_estadisticas_avanzadas(df_s)
                    k1, k2, k3, k4 = st.columns(4)
                    k1.metric("Promedio (Leq)", f"{round(stats['Leq'], 1)} dB")
                    k2.metric("Ruido Fondo (L90)", f"{round(stats['L90'], 1)} dB")
                    k3.metric("Picos (L10)", f"{round(stats['L10'], 1)} dB")
                    k4.metric("Infracciones", stats['Infracciones'], delta_color="inverse")
                    
                    # Gráfico de Serie Temporal
                    st.subheader("Evolución Temporal de Niveles")
                    fig_s, ax_s = plt.subplots(figsize=(12, 5))
                    sombreado_finde(ax_s, datetime.combine(date_sel[0], datetime.min.time()), 
                                   datetime.combine(date_sel[1], datetime.max.time()))
                    
                    # Dibujamos por periodos para colorear
                    df_res = df_s.set_index('FECHA_DT').resample('15min').mean(numeric_only=True).reset_index()
                    df_res['PERIODO'] = df_res['FECHA_DT'].apply(clasificar_periodo)
                    
                    ax_s.plot(df_res['FECHA_DT'], df_res['DECIBELIOS'], color='#cbd5e1', alpha=0.3)
                    for p, color in [('DIA', COLORES['Dia']), ('NOCHE', COLORES['Noche'])]:
                        sub = df_res.copy()
                        sub.loc[sub['PERIODO'] != p, 'DECIBELIOS'] = np.nan
                        ax_s.plot(sub['FECHA_DT'], sub['DECIBELIOS'], color=color, label=f"Nivel {p}", linewidth=1.5)
                    
                    ax_s.axhline(65, color='red', linestyle='--', alpha=0.5, label="Límite 65dB")
                    ax_s.set_ylabel("Decibelios (dB)")
                    ax_s.legend()
                    st.pyplot(fig_s)

                    # Mapa de calor semanal
                    if HAS_SEABORN:
                        st.subheader("Patrón Horario de Emisión (Mapa de Calor)")
                        pivot = df_s.pivot_table(index='DIA_SEMANA', columns='HORA_INT', values='DECIBELIOS', aggfunc='mean')
                        orden = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                        pivot = pivot.reindex(orden)
                        fig_hm, ax_hm = plt.subplots(figsize=(10, 4))
                        sns.heatmap(pivot, cmap='YlOrRd', ax=ax_hm, cbar_kws={'label': 'dB'})
                        ax_hm.set_yticklabels(['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom'])
                        st.pyplot(fig_hm)

            # PESTAÑA 3: COMPARATIVA DÍA/NOCHE
            with tab3:
                st.header("Análisis de Impacto por Franjas")
                comp_data = []
                for sid in sensores_con_datos:
                    d_sub = df_f[df_f[col_id] == sid]
                    comp_data.append({
                        'Calle': SENSORES_ABANDO.get(sid, sid),
                        'Día (dB)': d_sub[d_sub['PERIODO'] == 'DIA']['DECIBELIOS'].mean(),
                        'Noche (dB)': d_sub[d_sub['PERIODO'] == 'NOCHE']['DECIBELIOS'].mean()
                    })
                
                df_comp = pd.DataFrame(comp_data).sort_values('Noche (dB)', ascending=False)
                fig_c, ax_c = plt.subplots(figsize=(10, 8))
                df_comp.plot(x='Calle', kind='barh', ax=ax_c, color=[COLORES['Dia'], COLORES['Noche']])
                ax_c.axvline(55, color='blue', linestyle=':', label="Límite Noche")
                ax_c.set_title("Comparativa de niveles medios por ubicación")
                st.pyplot(fig_c)

            # PESTAÑA 4: EXPORTACIÓN Y RANKINGS
            with tab4:
                st.header("Ranking de Puntos Críticos")
                col_r1, col_r2 = st.columns(2)
                
                with col_r1:
                    st.subheader("Mayor Promedio 24h")
                    ranking = df_f.groupby(col_id)['DECIBELIOS'].mean().sort_values(ascending=False).head(10)
                    ranking.index = ranking.index.map(lambda x: SENSORES_ABANDO.get(x, x))
                    st.table(ranking)
                
                with col_r2:
                    st.subheader("Picos Máximos")
                    picos = df_f.groupby(col_id)['DECIBELIOS'].max().sort_values(ascending=False).head(10)
                    picos.index = picos.index.map(lambda x: SENSORES_ABANDO.get(x, x))
                    st.table(picos)

                st.markdown("---")
                st.subheader("💾 Exportación de Datos")
                csv = df_f.to_csv(index=False).encode('utf-8-sig')
                st.download_button("Descargar Auditoría CSV", csv, "auditoria_abando.csv", "text/csv")
    else:
        # Pantalla de Bienvenida
        st.info("👋 Selecciona una fuente de datos en el panel izquierdo para comenzar el análisis.")
        st.markdown("""
        ### Funcionalidades del Sistema:
        - **Carga Automática**: Conexión directa con la red de sonómetros de Bilbao.
        - **Auditoría Técnica**: Cálculo de niveles L10, L90 y Leq.
        - **Cumplimiento Normativo**: Identificación de infracciones (65dB día / 55dB noche).
        - **Patrones de Ocio**: Sombreado automático de periodos de fin de semana.
        """)
        st.image("https://images.unsplash.com/photo-1449156001931-828332437e72?q=80&w=2070&auto=format&fit=crop", 
                 caption="Monitorización del Ruido Urbano en Bilbao")

if __name__ == "__main__":
    main()
