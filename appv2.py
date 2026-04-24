import streamlit as st
import pandas as pd
import requests
from io import StringIO
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from datetime import datetime, timedelta
import unicodedata

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Auditoría Acústica Bilbao - Abando", layout="wide")

# --- CONSTANTES Y DICCIONARIOS ---
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
    'Bueno': '#22c55e',    'Regular': '#f97316', 
    'Sin Datos': '#94a3b8', 'Dia': '#f39c12', 
    'Noche': '#3498db',    'Finde': '#e74c3c'
}

# --- FUNCIONES DE UTILIDAD ---
def limpiar_nombre_columna(texto):
    if not isinstance(texto, str): return texto
    texto = unicodedata.normalize('NFD', texto).encode('ascii', 'ignore').decode("utf-8")
    return texto.strip().upper()

def clasificar_periodo(dt):
    if not isinstance(dt, datetime): return "N/A"
    return "DIA" if 7 <= dt.hour < 23 else "NOCHE"

def sombreado_finde(ax, start, end):
    """Resalta visualmente los periodos de fin de semana en el eje X."""
    curr = start.replace(hour=0, minute=0, second=0)
    while curr <= end:
        if curr.weekday() in [4, 5, 6]: # Viernes, Sábado, Domingo
            alpha = 0.05 if curr.weekday() == 4 else 0.1
            ax.axvspan(curr, curr + timedelta(days=1), color=COLORES['Finde'], alpha=alpha)
        curr += timedelta(days=1)

def procesar_df(df):
    """Normaliza columnas y tipos de datos del DataFrame cargado."""
    df.columns = [limpiar_nombre_columna(c) for c in df.columns]
    
    # Identificación dinámica de columnas clave
    try:
        col_fecha = next(c for c in ['FECHA/HORA MEDICION', 'HORA', 'FECHA_HORA', 'FECHA'] if c in df.columns)
        col_valor = next(c for c in ['DECIBELIOS MEDIDOS', 'LAEQ', 'VALOR', 'MEDICION'] if c in df.columns)
        col_id = next(c for c in ['CODIGO', 'ID_SONOMETRO', 'NOMBRE', 'ID'] if c in df.columns)
        
        df['FECHA_DT'] = pd.to_datetime(df[col_fecha], format='mixed', dayfirst=True, errors='coerce')
        df['DECIBELIOS'] = pd.to_numeric(df[col_valor].astype(str).str.replace(',', '.'), errors='coerce')
        df['PERIODO'] = df['FECHA_DT'].apply(clasificar_periodo)
        
        df = df.dropna(subset=['FECHA_DT', 'DECIBELIOS'])
        return df.sort_values('FECHA_DT'), col_id
    except StopIteration:
        st.error("No se han encontrado las columnas esperadas en el archivo.")
        return None, None

# --- LÓGICA DE CARGA DE DATOS ---
def get_data_from_api():
    url = "https://www.bilbao.eus/aytoonline/jsp/opendata/movilidad/od_sonometro_mediciones.jsp?idioma=c&formato=csv"
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            return pd.read_csv(StringIO(response.text), sep=';', encoding='utf-8-sig')
        else:
            st.sidebar.error(f"Error API: {response.status_code}")
            return None
    except Exception as e:
        st.sidebar.error(f"Error de conexión: {e}")
        return None

# --- APLICACIÓN PRINCIPAL ---
def main():
    st.sidebar.title("🛠️ Panel de Control")
    st.sidebar.markdown("---")
    
    # Selector de origen
    origen = st.sidebar.radio("Fuente de Datos:", ["📡 API Bilbao (Nube)", "📁 Carga Local (CSV)"])
    
    df_raw = None
    id_col = None
    
    if origen == "📡 API Bilbao (Nube)":
        if st.sidebar.button("Actualizar desde la Nube"):
            with st.spinner("Descargando datos oficiales..."):
                data = get_data_from_api()
                if data is not None:
                    df_raw, id_col = procesar_df(data)
                    st.session_state['df_cache'] = (df_raw, id_col)
        elif 'df_cache' in st.session_state:
            df_raw, id_col = st.session_state['df_cache']
            
    else:
        file = st.sidebar.file_uploader("Subir CSV de Mediciones", type=['csv'])
        if file:
            data = pd.read_csv(file, sep=None, engine='python', encoding='utf-8-sig')
            df_raw, id_col = procesar_df(data)

    if df_raw is not None:
        # Filtros de fecha
        f_min, f_max = df_raw['FECHA_DT'].min().date(), df_raw['FECHA_DT'].max().date()
        st.sidebar.subheader("📅 Rango Temporal")
        f_ini = st.sidebar.date_input("Desde:", f_max - timedelta(days=7), min_value=f_min, max_value=f_max)
        f_fin = st.sidebar.date_input("Hasta:", f_max, min_value=f_min, max_value=f_max)
        
        # Filtrado
        mask = (df_raw['FECHA_DT'].dt.date >= f_ini) & (df_raw['FECHA_DT'].dt.date <= f_fin)
        df_f = df_raw[mask].copy()
        
        # Dashboard Principal
        st.title("📊 Auditoría de Contaminación Acústica")
        st.caption(f"Distrito de Abando, Bilbao | Datos del {f_ini} al {f_fin}")

        tabs = st.tabs(["🛡️ Calidad de Red", "📈 Análisis de Sensor", "🔥 Mapas de Calor", "🏆 Rankings y Exportación"])

        # PESTAÑA 1: CALIDAD
        with tabs[0]:
            st.header("Disponibilidad de Datos")
            dias = (f_fin - f_ini).days + 1
            objetivo = dias * 96 # 4 lecturas/hora * 24h
            
            resumen_calidad = []
            sensores_activos = []
            
            for sid, calle in SENSORES_ABANDO.items():
                count = len(df_f[df_f[id_col] == sid])
                pct = min(100.0, (count / objetivo) * 100) if objetivo > 0 else 0
                estado = "Bueno" if pct >= 85 else ("Regular" if pct > 0 else "Sin Datos")
                if count > 0: sensores_activos.append(sid)
                resumen_calidad.append({'Calle': calle, 'ID': sid, 'Disponibilidad': pct, 'Estado': estado})
            
            df_q = pd.DataFrame(resumen_calidad)
            c1, c2 = st.columns([1, 1.5])
            
            with c1:
                fig_p, ax_p = plt.subplots()
                v_counts = df_q['Estado'].value_counts().reindex(['Bueno', 'Regular', 'Sin Datos'], fill_value=0)
                ax_p.pie(v_counts, labels=v_counts.index, autopct='%1.1f%%', colors=[COLORES['Bueno'], COLORES['Regular'], COLORES['Sin Datos']])
                st.pyplot(fig_p)
            
            with c2:
                st.dataframe(df_q.sort_values('Disponibilidad', ascending=False), use_container_width=True, hide_index=True)

        # PESTAÑA 2: ANÁLISIS POR SENSOR
        with tabs[1]:
            if not sensores_activos:
                st.warning("No hay datos para los sensores seleccionados en este rango.")
            else:
                sel_sid = st.selectbox("Seleccionar Ubicación:", sensores_activos, format_func=lambda x: f"{SENSORES_ABANDO[x]} ({x})")
                df_s = df_f[df_f[id_col] == sel_sid].copy()
                
                # Estadísticas rápidas
                m1, m2, m3 = st.columns(3)
                m1.metric("Máximo Registrado", f"{df_s['DECIBELIOS'].max()} dB")
                m2.metric("Promedio Diurno", f"{round(df_s[df_s['PERIODO']=='DIA']['DECIBELIOS'].mean(), 1)} dB")
                m3.metric("Promedio Nocturno", f"{round(df_s[df_s['PERIODO']=='NOCHE']['DECIBELIOS'].mean(), 1)} dB")
                
                # Gráfico Evolutivo
                fig_e, ax_e = plt.subplots(figsize=(12, 5))
                sombreado_finde(ax_e, datetime.combine(f_ini, datetime.min.time()), datetime.combine(f_fin, datetime.max.time()))
                
                # Separar series para coloreado
                df_res = df_s.set_index('FECHA_DT').resample('15min').mean(numeric_only=True).reset_index()
                df_res['PERIODO'] = df_res['FECHA_DT'].apply(clasificar_periodo)
                
                for p, color in [('DIA', COLORES['Dia']), ('NOCHE', COLORES['Noche'])]:
                    subset = df_res.copy()
                    subset.loc[subset['PERIODO'] != p, 'DECIBELIOS'] = np.nan
                    ax_e.plot(subset['FECHA_DT'], subset['DECIBELIOS'], color=color, label=p, linewidth=1.5)
                
                ax_e.axhline(65, color='red', linestyle='--', alpha=0.5, label="Límite Día")
                ax_e.axhline(55, color='blue', linestyle='--', alpha=0.5, label="Límite Noche")
                ax_e.set_ylabel("Decibelios (dB)")
                ax_e.legend()
                st.pyplot(fig_e)

        # PESTAÑA 3: MAPAS DE CALOR
        with tabs[2]:
            st.header("Intensidad Horaria")
            if 'sel_sid' in locals():
                df_h = df_s.copy()
                df_h['Hora'] = df_h['FECHA_DT'].dt.hour
                df_h['DiaSemana'] = df_h['FECHA_DT'].dt.day_name()
                
                pivot = df_h.pivot_table(index='DiaSemana', columns='Hora', values='DECIBELIOS', aggfunc='mean')
                orden_dias = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                pivot = pivot.reindex(orden_dias)
                
                fig_hm, ax_hm = plt.subplots(figsize=(10, 4))
                sns.heatmap(pivot, cmap='YlOrRd', ax=ax_hm, cbar_kws={'label': 'dB'})
                ax_hm.set_title(f"Patrón de Ruido Semanal: {SENSORES_ABANDO[sel_sid]}")
                st.pyplot(fig_hm)
            else:
                st.info("Selecciona un sensor en la pestaña anterior para ver su mapa de calor.")

        # PESTAÑA 4: RANKINGS Y EXPORTACIÓN
        with tabs[3]:
            st.header("Top Sonómetros por Impacto")
            col_r1, col_r2 = st.columns(2)
            
            rank_data = []
            for sid in sensores_activos:
                d_sub = df_f[df_f[id_col] == sid]
                rank_data.append({
                    'Ubicación': SENSORES_ABANDO[sid],
                    'Promedio Total': round(d_sub['DECIBELIOS'].mean(), 1),
                    'Pico Máximo': d_sub['DECIBELIOS'].max(),
                    'Superaciones Límite': len(d_sub[(d_sub['PERIODO']=='DIA') & (d_sub['DECIBELIOS'] > 65)]) + 
                                          len(d_sub[(d_sub['PERIODO']=='NOCHE') & (d_sub['DECIBELIOS'] > 55)])
                })
            
            df_ranks = pd.DataFrame(rank_data)
            with col_r1:
                st.subheader("Más ruidosos (Promedio)")
                st.dataframe(df_ranks.sort_values('Promedio Total', ascending=False).head(10), hide_index=True)
            with col_r2:
                st.subheader("Más infracciones de nivel")
                st.dataframe(df_ranks.sort_values('Superaciones Límite', ascending=False).head(10), hide_index=True)
            
            st.markdown("---")
            st.subheader("💾 Exportar Datos")
            csv = df_f.to_csv(index=False).encode('utf-8-sig')
            st.download_button("Descargar Auditoría Filtrada (CSV)", csv, "auditoria_bilbao_filtrada.csv", "text/csv")

    else:
        st.info("👋 Bienvenido. Para comenzar, selecciona una fuente de datos en la barra lateral.")
        st.image("https://www.bilbao.eus/aytoonline/static/img/logo_bilbao.png", width=200)
        st.markdown("""
        ### Instrucciones:
        1. **API Bilbao**: Intenta conectar directamente con los servidores del Ayuntamiento.
        2. **Carga Local**: Si la API falla o tienes un archivo propio, súbelo en formato CSV.
        3. **Filtros**: Usa la barra lateral para ajustar las fechas del estudio.
        """)

if __name__ == "__main__":
    main()
