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
    page_title="Auditoría Acústica Bilbao - Panel Unificado", 
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

COLORES = {
    'Bueno': '#22c55e',    
    'Regular': '#f97316',  
    'Sin Datos': '#94a3b8', 
    'Dia': '#f39c12',      
    'Noche': '#3498db'     
}

# --- FUNCIONES DE SOPORTE ---
def limpiar_texto(texto):
    if not isinstance(texto, str): return str(texto)
    return "".join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').strip().upper()

def clasificar_periodo(dt):
    return "DIA" if 7 <= dt.hour < 23 else "NOCHE"

def sombreado_finde(ax, start, end):
    """Sombreado para Viernes noche y fines de semana."""
    curr = start.replace(hour=0, minute=0, second=0)
    while curr <= end:
        if curr.weekday() in [4, 5, 6]: # Vie, Sab, Dom
            color = '#e74c3c' if curr.weekday() == 4 else '#f1c40f'
            ax.axvspan(curr, curr + timedelta(days=1), color=color, alpha=0.08)
        curr += timedelta(days=1)

@st.cache_data(ttl=600)
def download_api_data():
    url = "https://www.bilbao.eus/aytoonline/jsp/opendata/movilidad/od_sonometro_mediciones.jsp?idioma=c&formato=csv"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.text
    except:
        pass
    return None

def procesar_datos(csv_txt):
    try:
        df = pd.read_csv(StringIO(csv_txt), sep=';', encoding='utf-8-sig')
        df.columns = [limpiar_texto(c) for c in df.columns]
        
        # Mapeo flexible de nombres de columnas
        c_id = next(c for c in df.columns if any(x in c for x in ['CODIGO', 'ID', 'NOMBRE']))
        c_val = next(c for c in df.columns if any(x in c for x in ['DECIBELIOS', 'VALOR', 'LAEQ']))
        c_time = next(c for c in df.columns if any(x in c for x in ['FECHA', 'HORA', 'MEDICION']))

        df['DB'] = pd.to_numeric(df[c_val].astype(str).str.replace(',', '.'), errors='coerce')
        df['FECHA_DT'] = pd.to_datetime(df[c_time], errors='coerce', dayfirst=True)
        
        df = df.dropna(subset=['FECHA_DT', 'DB', c_id])
        df['PERIODO'] = df['FECHA_DT'].apply(clasificar_periodo)
        return df, c_id
    except Exception as e:
        st.error(f"Error procesando el formato del archivo: {e}")
        return None, None

def main():
    st.sidebar.title("📁 Gestión de Datos")
    opcion = st.sidebar.radio("Fuente de entrada:", ["Descarga Online (API)", "Subida Manual (CSV)"])
    
    raw_data = None
    if opcion == "Descarga Online (API)":
        raw_data = download_api_data()
        if not raw_data: st.sidebar.warning("API no disponible en este momento.")
    else:
        file = st.sidebar.file_uploader("Subir archivo CSV", type=['csv'])
        if file: raw_data = file.getvalue().decode('utf-8-sig', errors='ignore')

    if not raw_data:
        st.title("🔊 Auditoría Acústica Bilbao")
        st.info("Carga datos para comenzar el análisis del Distrito de Abando.")
        return

    df_full, col_id = procesar_datos(raw_data)
    if df_full is None: return

    # Filtrado por zona Abando (diccionario maestro)
    df_abando = df_full[df_full[col_id].isin(SENSORES_ABANDO.keys())].copy()
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("🎯 Panel de Control")
    
    # Filtros de Fecha
    f_min, f_max = df_abando['FECHA_DT'].min().date(), df_abando['FECHA_DT'].max().date()
    rango = st.sidebar.date_input("Rango de fechas de auditoría:", [f_min, f_max])
    
    # Selector de Sonómetro individual
    sonometros_activos = sorted(df_abando[col_id].unique())
    if not sonometros_activos:
        st.error("No se han detectado sensores de Abando en el archivo cargado.")
        return
        
    sel_nombre = st.sidebar.selectbox("Foco en Calle:", 
                                    [f"{SENSORES_ABANDO[s]} ({s})" for s in sonometros_activos])
    sel_id = sel_nombre.split('(')[-1].strip(')')

    # Aplicar filtros al DataFrame de trabajo
    mask = (df_abando[col_id] == sel_id)
    if isinstance(rango, (list, tuple)) and len(rango) == 2:
        mask &= (df_abando['FECHA_DT'].dt.date >= rango[0]) & (df_abando['FECHA_DT'].dt.date <= rango[1])
    
    df_sel = df_abando[mask].sort_values('FECHA_DT')
    
    # --- INTERFAZ DE PESTAÑAS ---
    tab_cal, tab_ana, tab_rank = st.tabs(["🛡️ Control de Calidad", "📉 Análisis Temporal", "🏆 Rankings"])

    # 1. PESTAÑA: CONTROL DE CALIDAD (AUDITORÍA DE INTEGRIDAD)
    with tab_cal:
        st.header("🛡️ Auditoría de Integridad de la Red (Abando)")
        dias_auditoria = (rango[1] - rango[0]).days + 1 if isinstance(rango, (list, tuple)) and len(rango) == 2 else 1
        objetivo_lecturas = dias_auditoria * 96 # Mediciones cada 15 min
        
        calidad_stats = []
        for sid, name in SENSORES_ABANDO.items():
            ds_sensor = df_abando[df_abando[col_id] == sid]
            count = len(ds_sensor)
            perc = min(100.0, (count / objetivo_lecturas) * 100) if objetivo_lecturas > 0 else 0
            
            if perc >= 85: estado = "Bueno"
            elif perc > 5: estado = "Regular"
            else: estado = "Sin Datos"
            
            calidad_stats.append({
                'Calle': name, 
                'ID': sid, 
                'Disponibilidad %': round(perc, 1), 
                'Registros': count,
                'Estado': estado
            })
        
        df_q = pd.DataFrame(calidad_stats)
        
        # Visualización de la Auditoría
        c1, c2 = st.columns([1, 1.5])
        
        with c1:
            st.subheader("Estado General de la Red")
            # Forzamos orden para que los colores coincidan
            df_pie = df_q['Estado'].value_counts().reindex(['Bueno', 'Regular', 'Sin Datos'], fill_value=0)
            fig_p, ax_p = plt.subplots(figsize=(6,6))
            ax_p.pie(df_pie, labels=df_pie.index, autopct='%1.1f%%', 
                    colors=[COLORES['Bueno'], COLORES['Regular'], COLORES['Sin Datos']],
                    startangle=140, wedgeprops={'edgecolor': 'white'})
            st.pyplot(fig_p)
            
        with c2:
            st.subheader("% Disponibilidad por Sensor")
            df_q_sorted = df_q.sort_values('Disponibilidad %', ascending=True)
            fig_b, ax_b = plt.subplots(figsize=(8, 11))
            colors_list = [COLORES.get(s, '#7f8c8d') for s in df_q_sorted['Estado']]
            ax_b.barh(df_q_sorted['Calle'], df_q_sorted['Disponibilidad %'], color=colors_list)
            ax_b.set_xlim(0, 100)
            ax_b.grid(axis='x', linestyle='--', alpha=0.6)
            st.pyplot(fig_b)

        st.markdown("---")
        st.subheader("Detalle del Inventario")
        st.dataframe(df_q, use_container_width=True, hide_index=True)

    # 2. PESTAÑA: ANÁLISIS TEMPORAL
    with tab_ana:
        st.header(f"Evolución: {SENSORES_ABANDO[sel_id]}")
        if df_sel.empty:
            st.warning("Sin registros para los filtros seleccionados.")
        else:
            # Re-muestreo para suavizar y manejar huecos
            df_plot = df_sel.set_index('FECHA_DT').resample('15min').mean(numeric_only=True).reset_index()
            df_plot['PERIODO'] = df_plot['FECHA_DT'].apply(clasificar_periodo)
            
            fig_t, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
            
            # Panel Día
            df_dia = df_plot.copy(); df_dia.loc[df_dia['PERIODO'] != 'DIA', 'DB'] = np.nan
            ax1.plot(df_dia['FECHA_DT'], df_dia['DB'], color=COLORES['Dia'], label='Nivel Día', linewidth=1.8)
            ax1.axhline(65, color='red', linestyle='--', alpha=0.8, label='Límite 65dB')
            ax1.set_title("Periodo Diurno (07:00 - 23:00)")
            ax1.set_ylim(40, 90)
            ax1.set_ylabel("Decibelios (dB)")
            sombreado_finde(ax1, df_plot['FECHA_DT'].min(), df_plot['FECHA_DT'].max())
            ax1.legend(loc='upper right')
            
            # Panel Noche
            df_noc = df_plot.copy(); df_noc.loc[df_noc['PERIODO'] != 'NOCHE', 'DB'] = np.nan
            ax2.plot(df_noc['FECHA_DT'], df_noc['DB'], color=COLORES['Noche'], label='Nivel Noche', linewidth=1.8)
            ax2.axhline(55, color='blue', linestyle='--', alpha=0.8, label='Límite 55dB')
            ax2.set_title("Periodo Nocturno (23:00 - 07:00)")
            ax2.set_ylim(40, 90)
            ax2.set_ylabel("Decibelios (dB)")
            sombreado_finde(ax2, df_plot['FECHA_DT'].min(), df_plot['FECHA_DT'].max())
            ax2.legend(loc='upper right')
            
            ax2.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
            plt.xticks(rotation=45)
            st.pyplot(fig_t)

    # 3. PESTAÑA: RANKINGS (PUNTOS CRÍTICOS)
    with tab_rank:
        st.header("🏆 Puntos Críticos (Máximos por Periodo)")
        
        resumen_picos = []
        for sid, calle in SENSORES_ABANDO.items():
            ds = df_abando[df_abando[col_id] == sid]
            if not ds.empty:
                for p in ['DIA', 'NOCHE']:
                    sub = ds[ds['PERIODO'] == p]
                    if not sub.empty:
                        idx_max = sub['DB'].idxmax()
                        resumen_picos.append({
                            'Ubicación': calle,
                            'Código': sid,
                            'Periodo': p,
                            'Pico dB': round(sub.loc[idx_max, 'DB'], 1),
                            'Momento del Pico': sub.loc[idx_max, 'FECHA_DT'].strftime('%d/%m %H:%M')
                        })
        
        if not resumen_picos:
            st.info("Carga datos para generar los rankings.")
        else:
            df_picos = pd.DataFrame(resumen_picos)
            col_r1, col_r2 = st.columns(2)
            
            with col_r1:
                st.subheader("☀️ Top 10 Ruidosos (Día)")
                top_d = df_picos[df_picos['Periodo'] == 'DIA'].sort_values('Pico dB', ascending=False).head(10)
                st.dataframe(top_d[['Ubicación', 'Pico dB', 'Momento del Pico']], hide_index=True, use_container_width=True)
                
            with col_r2:
                st.subheader("🌙 Top 10 Ruidosos (Noche)")
                top_n = df_picos[df_picos['Periodo'] == 'NOCHE'].sort_values('Pico dB', ascending=False).head(10)
                st.dataframe(top_n[['Ubicación', 'Pico dB', 'Momento del Pico']], hide_index=True, use_container_width=True)

if __name__ == "__main__":
    main()
