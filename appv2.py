import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from io import StringIO
from datetime import datetime, timedelta
import requests

# Configuración de página
st.set_page_config(page_title="Auditoría Real: Sonómetros Bilbao", layout="wide")

# --- CONFIGURACIÓN DE ABANDO (32 SENSORES) ---
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
    'Dia': '#f39c12',     # Naranja
    'Noche': '#3498db',   # Azul
    'Finde': '#f1c40f',   # Amarillo pálido para fondo
    'Viernes': '#e74c3c'  # Rojo suave para inicio de finde
}

def normalizar_datos(df):
    """Estandariza los nombres de columnas del CSV oficial."""
    cols = {col.upper().strip(): col for col in df.columns}
    try:
        c_fecha = next(cols[k] for k in ['FECHA/HORA MEDICION', 'FECHA_HORA', 'HORA'] if k in cols)
        c_valor = next(cols[k] for k in ['DECIBELIOS MEDIDOS', 'LAEQ', 'VALOR'] if k in cols)
        c_id = next(cols[k] for k in ['CODIGO', 'ID_SONOMETRO', 'NOMBRE'] if k in cols)
        
        df = df.rename(columns={c_fecha: 'FECHA_RAW', c_valor: 'VALOR_RAW', c_id: 'SENSOR_ID'})
        df['FECHA_DT'] = pd.to_datetime(df['FECHA_RAW'], format='mixed', dayfirst=True)
        df['DB'] = pd.to_numeric(df['VALOR_RAW'].astype(str).str.replace(',', '.'), errors='coerce')
        df['PERIODO'] = df['FECHA_DT'].dt.hour.apply(lambda h: 'DIA' if 7 <= h < 23 else 'NOCHE')
        return df.dropna(subset=['FECHA_DT', 'DB'])
    except Exception as e:
        st.error(f"Estructura de CSV no reconocida: {e}")
        return None

def sombreado_fines_de_semana(ax, min_date, max_date):
    """Añade sombreado a los días de fin de semana en el eje X."""
    curr = min_date.replace(hour=0, minute=0, second=0)
    while curr <= max_date:
        if curr.weekday() >= 4: # Viernes, Sábado o Domingo
            color = COLORES['Viernes'] if curr.weekday() == 4 else COLORES['Finde']
            ax.axvspan(curr, curr + timedelta(days=1), color=color, alpha=0.1)
        curr += timedelta(days=1)

def main():
    st.title("🛡️ Auditoría Real de Ruido: Abando (Bilbao)")
    
    df_final = None
    
    with st.sidebar:
        st.header("📥 Entrada de Datos")
        metodo = st.radio("Origen:", ["Descarga Automática", "Subir CSV Local"])
        
        if metodo == "Descarga Automática":
            if st.button("🔄 Intentar Descarga Real"):
                try:
                    url = "https://www.bilbao.eus/aytoonline/jsp/opendata/movilidad/od_sonometro_mediciones.jsp?idioma=c&formato=csv"
                    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
                    if r.status_code == 200:
                        df_raw = pd.read_csv(StringIO(r.text), sep=';', encoding='utf-8-sig')
                        df_final = normalizar_datos(df_raw)
                    else:
                        st.error(f"Bloqueo de servidor (Error {r.status_code}).")
                except Exception as e:
                    st.error(f"Error de red: {e}")
        else:
            uploaded = st.file_uploader("Sube el CSV descargado de Open Data Bilbao", type=["csv"])
            if uploaded:
                df_raw = pd.read_csv(uploaded, sep=None, engine='python', encoding='utf-8-sig')
                df_final = normalizar_datos(df_raw)

    if df_final is not None:
        df_abando = df_final[df_final['SENSOR_ID'].isin(SENSORES_ABANDO.keys())].copy()
        
        # Filtro de Calendario
        f_min, f_max = df_abando['FECHA_DT'].min(), df_abando['FECHA_DT'].max()
        rango = st.sidebar.date_input("Periodo de Auditoría", [f_min.date(), f_max.date()])
        
        if len(rango) == 2:
            df_abando = df_abando[(df_abando['FECHA_DT'].dt.date >= rango[0]) & (df_abando['FECHA_DT'].dt.date <= rango[1])]

        tabs = st.tabs(["📉 Análisis por Sensor", "🛡️ Calidad y Auditoría", "🏆 Rankings"])

        with tabs[0]:
            # Selector de sonómetros que SOLO tienen datos
            sensores_activos = df_abando['SENSOR_ID'].unique()
            sel = st.selectbox("Seleccionar ubicación con mediciones:", 
                               sensores_activos, 
                               format_func=lambda x: f"{SENSORES_ABANDO.get(x, x)} ({x})")
            
            df_s = df_abando[df_abando['SENSOR_ID'] == sel].sort_values('FECHA_DT')
            
            if not df_s.empty:
                st.subheader(f"Seguimiento: {SENSORES_ABANDO.get(sel, sel)}")
                
                # Gráfico Evolutivo con distinción Día/Noche
                fig, ax = plt.subplots(figsize=(12, 5))
                
                # Sombreado de fin de semana
                sombreado_fines_de_semana(ax, df_s['FECHA_DT'].min(), df_s['FECHA_DT'].max())
                
                # Dibujamos por tramos para cambiar color según periodo
                df_dia = df_s[df_s['PERIODO'] == 'DIA']
                df_noche = df_s[df_s['PERIODO'] == 'NOCHE']
                
                ax.scatter(df_dia['FECHA_DT'], df_dia['DB'], color=COLORES['Dia'], s=15, label='Día (07h-23h)', alpha=0.7)
                ax.scatter(df_noche['FECHA_DT'], df_noche['DB'], color=COLORES['Noche'], s=15, label='Noche (23h-07h)', alpha=0.7)
                
                ax.axhline(65, color='orange', ls='--', alpha=0.5, label='Umbral Día (65dB)')
                ax.axhline(55, color='blue', ls='--', alpha=0.5, label='Umbral Noche (55dB)')
                
                ax.set_ylabel("Decibelios (dB)")
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m %H:%M'))
                plt.xticks(rotation=45)
                ax.legend(loc='upper right', bbox_to_anchor=(1.15, 1))
                ax.grid(True, alpha=0.2)
                
                st.pyplot(fig)
            else:
                st.warning("No hay datos para este sensor en el periodo elegido.")

        with tabs[1]:
            st.subheader("Estado de Integridad de Datos")
            dias = (df_abando['FECHA_DT'].max() - df_abando['FECHA_DT'].min()).days + 1
            esperados = dias * 96
            
            resumen = []
            for sid, calle in SENSORES_ABANDO.items():
                count = len(df_abando[df_abando['SENSOR_ID'] == sid])
                porc = min((count / esperados) * 100, 100) if esperados > 0 else 0
                resumen.append({'Calle': calle, 'ID': sid, 'Muestras': count, 'Integridad %': round(porc, 1)})
            
            st.table(pd.DataFrame(resumen).sort_values('Integridad %', ascending=False))

        with tabs[2]:
            st.subheader("Calles Críticas")
            rank = df_abando.groupby('SENSOR_ID')['DB'].agg(['mean', 'max']).reset_index()
            rank['Calle'] = rank['SENSOR_ID'].map(SENSORES_ABANDO)
            st.bar_chart(rank.dropna().set_index('Calle')['mean'])

    else:
        st.info("👋 Esperando datos reales para la auditoría de Abando. Usa la barra lateral.")

if __name__ == "__main__":
    main()
