import streamlit as st
import pandas as pd
import requests
from io import StringIO
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import time

# Configuración de página
st.set_page_config(page_title="Auditoría Acústica Bilbao - Abando", layout="wide")

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

# Paleta de colores solicitada
COLORES = {
    'Bueno': '#22c55e',    # Verde
    'Regular': '#f97316',  # Naranja
    'Sin Datos': '#94a3b8', # Gris
    'Dia': '#f39c12',      # Naranja para gráfico
    'Noche': '#3498db'     # Azul para gráfico
}

def limpiar_texto(texto):
    import unicodedata
    if not isinstance(texto, str): return texto
    texto = unicodedata.normalize('NFD', texto).encode('ascii', 'ignore').decode("utf-8")
    return texto.strip().upper()

def clasificar_periodo(dt):
    if not isinstance(dt, datetime): return "N/A"
    return "DIA" if 7 <= dt.hour < 23 else "NOCHE"

def sombreado_finde(ax, start, end):
    """Añade sombreado a Viernes (noche), Sábados y Domingos."""
    curr = start.replace(hour=0, minute=0, second=0)
    while curr <= end:
        if curr.weekday() in [4, 5, 6]:
            color = '#e74c3c' if curr.weekday() == 4 else '#f1c40f'
            ax.axvspan(curr, curr + timedelta(days=1), color=color, alpha=0.1)
        curr += timedelta(days=1)

def get_fallback_data():
    """Genera datos sintéticos si el servidor de Bilbao no responde."""
    st.warning("⚠️ El servidor de Bilbao no responde. Cargando datos de emergencia para demostración.")
    dates = pd.date_range(end=datetime.now(), periods=500, freq='15min')
    data = {
        'FECHA/HORA MEDICION': [d.strftime('%d/%m/%Y %H:%M:%S') for d in dates],
        'DECIBELIOS MEDIDOS': np.random.uniform(50, 75, size=500),
        'CODIGO': [np.random.choice(list(SENSORES_ABANDO.keys())) for _ in range(500)]
    }
    df = pd.DataFrame(data)
    return df, 'CODIGO'

@st.cache_data(ttl=600)
def load_data():
    """Descarga datos con User-Agent y sistema de reintentos."""
    url = "https://www.bilbao.eus/aytoonline/jsp/opendata/movilidad/od_sonometro_mediciones.jsp?idioma=c&formato=csv"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    retries = 3
    for i in range(retries):
        try:
            r = requests.get(url, headers=headers, timeout=15)
            r.raise_for_status()
            df = pd.read_csv(StringIO(r.text), sep=';', encoding='utf-8-sig')
            df.columns = [limpiar_texto(c) for c in df.columns]
            
            c_t = next(c for c in ['FECHA/HORA MEDICION', 'HORA', 'FECHA_HORA'] if c in df.columns)
            c_v = next(c for c in ['DECIBELIOS MEDIDOS', 'LAEQ', 'VALOR'] if c in df.columns)
            c_id = next(c for c in ['CODIGO', 'ID_SONOMETRO', 'NOMBRE'] if c in df.columns)
            
            df['FECHA_DT'] = pd.to_datetime(df[c_t], format='mixed', dayfirst=True)
            df['DECIBELIOS'] = pd.to_numeric(df[c_v].astype(str).str.replace(',', '.'), errors='coerce')
            df['PERIODO'] = df['FECHA_DT'].apply(clasificar_periodo)
            return df, c_id
        except Exception as e:
            if i < retries - 1:
                time.sleep(2 ** i) # Espera 1s, luego 2s...
                continue
            else:
                return get_fallback_data()

def main():
    st.sidebar.header("⚙️ Configuración Auditoría")
    df_raw, c_id = load_data()
    
    # Procesar fechas tras carga (por si es fallback)
    if 'FECHA_DT' not in df_raw.columns:
        c_t = next(c for c in ['FECHA/HORA MEDICION', 'HORA', 'FECHA_HORA'] if c in df_raw.columns)
        df_raw['FECHA_DT'] = pd.to_datetime(df_raw[c_t], format='mixed', dayfirst=True)
    if 'DECIBELIOS' not in df_raw.columns:
        c_v = next(c for c in ['DECIBELIOS MEDIDOS', 'LAEQ', 'VALOR'] if c in df_raw.columns)
        df_raw['DECIBELIOS'] = pd.to_numeric(df_raw[c_v].astype(str).str.replace(',', '.'), errors='coerce')
    if 'PERIODO' not in df_raw.columns:
        df_raw['PERIODO'] = df_raw['FECHA_DT'].apply(clasificar_periodo)

    f_min, f_max = df_raw['FECHA_DT'].min().date(), df_raw['FECHA_DT'].max().date()
    f_ini = st.sidebar.date_input("Fecha Inicio", f_max - timedelta(days=7), min_value=f_min, max_value=f_max)
    f_fin = st.sidebar.date_input("Fecha Fin", f_max, min_value=f_min, max_value=f_max)
    
    f_ini_dt = datetime.combine(f_ini, datetime.min.time())
    f_fin_dt = datetime.combine(f_fin, datetime.max.time())
    df_f = df_raw[(df_raw['FECHA_DT'] >= f_ini_dt) & (df_raw['FECHA_DT'] <= f_fin_dt)].copy()
    
    dias_totales = (f_fin - f_ini).days + 1
    objetivo_lecturas = dias_totales * 96

    tabs = st.tabs(["🛡️ Control de Calidad", "📉 Análisis Temporal", "🏆 Rankings"])

    # PESTAÑA 1: CONTROL DE CALIDAD
    with tabs[0]:
        st.header("🛡️ Control de Calidad Acústica - Abando")
        calidad_info = []
        sensores_con_datos = []
        
        for sid, calle in SENSORES_ABANDO.items():
            data_sensor = df_f[df_f[c_id] == sid]
            registros = len(data_sensor)
            porc = min(round((registros / objetivo_lecturas) * 100, 1), 100.0) if objetivo_lecturas > 0 else 0
            estado = "Bueno" if porc >= 90 else ("Regular" if porc > 0 else "Sin Datos")
            
            if registros > 0:
                sensores_con_datos.append(sid)
            
            calidad_info.append({'Calle': calle, 'ID': sid, 'Calidad %': porc, 'Estado': estado})
        
        df_q = pd.DataFrame(calidad_info)
        col1, col2 = st.columns([1, 1.5])
        
        with col1:
            st.subheader("Estado Global")
            counts = df_q['Estado'].value_counts().reindex(['Bueno', 'Regular', 'Sin Datos'], fill_value=0)
            fig_pie, ax_pie = plt.subplots()
            ax_pie.pie(counts, labels=counts.index, autopct='%1.1f%%', 
                      colors=[COLORES['Bueno'], COLORES['Regular'], COLORES['Sin Datos']], 
                      startangle=140, wedgeprops={'edgecolor': 'white'})
            st.pyplot(fig_pie)
        
        with col2:
            st.subheader("Calidad por Sonómetro")
            df_q_sorted = df_q.sort_values('Calidad %', ascending=True)
            fig_bar, ax_bar = plt.subplots(figsize=(8, 10))
            bar_colors = [COLORES[e] for e in df_q_sorted['Estado']]
            ax_bar.barh(df_q_sorted['Calle'], df_q_sorted['Calidad %'], color=bar_colors)
            ax_bar.set_xlim(0, 100)
            ax_bar.set_xlabel("% de Disponibilidad")
            st.pyplot(fig_bar)

        st.markdown("---")
        st.subheader("Detalle del Inventario de Abando")
        st.dataframe(df_q, use_container_width=True, hide_index=True)

    # PESTAÑA 2: ANÁLISIS TEMPORAL
    with tabs[1]:
        st.header("📉 Evolución de Niveles")
        opciones_sonometros = [sid for sid in SENSORES_ABANDO.keys() if sid in sensores_con_datos]
        
        if not opciones_sonometros:
            st.warning("No hay sonómetros con datos en este periodo.")
        else:
            sel_id = st.selectbox("Sonómetro (Solo con datos):", 
                                opciones_sonometros, 
                                format_func=lambda x: f"{SENSORES_ABANDO[x]} ({x})")
            
            sub_s = df_f[df_f[c_id] == sel_id].set_index('FECHA_DT').resample('15min').mean(numeric_only=True).reset_index()
            sub_s['PERIODO'] = sub_s['FECHA_DT'].apply(clasificar_periodo)
            
            fig_t, ax_t = plt.subplots(figsize=(12, 6))
            df_d = sub_s.copy(); df_d.loc[df_d['PERIODO'] != 'DIA', 'DECIBELIOS'] = np.nan
            df_n = sub_s.copy(); df_n.loc[df_n['PERIODO'] != 'NOCHE', 'DECIBELIOS'] = np.nan
            
            ax_t.plot(df_d['FECHA_DT'], df_d['DECIBELIOS'], color=COLORES['Dia'], label='Día', linewidth=2)
            ax_t.plot(df_n['FECHA_DT'], df_n['DECIBELIOS'], color=COLORES['Noche'], label='Noche', linewidth=2)
            
            ax_t.axhline(65, color='red', linestyle='--', alpha=0.7, label='Límite Día (65dB)')
            ax_t.axhline(55, color='blue', linestyle='--', alpha=0.7, label='Límite Noche (55dB)')
            ax_t.set_ylim(40, 95)
            ax_t.set_ylabel("Decibelios (dB)")
            sombreado_finde(ax_t, f_ini_dt, f_fin_dt)
            plt.xticks(rotation=45)
            ax_t.legend()
            st.pyplot(fig_t)

    # PESTAÑA 3: RANKINGS
    with tabs[2]:
        st.header("🏆 Rankings de Ruido Crítico")
        metrics_dia, metrics_noche = [], []
        
        for sid, calle in SENSORES_ABANDO.items():
            ds = df_f[df_f[c_id] == sid]
            if not ds.empty:
                for p, m_list in [('DIA', metrics_dia), ('NOCHE', metrics_noche)]:
                    sub = ds[ds['PERIODO'] == p]
                    if not sub.empty:
                        idx_max = sub['DECIBELIOS'].idxmax()
                        m_list.append({
                            'Localización': calle,
                            'Código': sid,
                            'Máximo (dB)': sub.loc[idx_max, 'DECIBELIOS'],
                            'Fecha y Hora': sub.loc[idx_max, 'FECHA_DT'].strftime('%d/%m/%Y %H:%M')
                        })
        
        col_d, col_n = st.columns(2)
        with col_d:
            st.subheader("☀️ Máximos Periodo Diurno")
            if metrics_dia:
                st.dataframe(pd.DataFrame(metrics_dia).sort_values('Máximo (dB)', ascending=False).head(10), hide_index=True)
        with col_n:
            st.subheader("🌙 Máximos Periodo Nocturno")
            if metrics_noche:
                st.dataframe(pd.DataFrame(metrics_noche).sort_values('Máximo (dB)', ascending=False).head(10), hide_index=True)

if __name__ == "__main__":
    main()
