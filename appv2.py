import streamlit as st
import pandas as pd
import requests
from io import StringIO
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import unicodedata
import time

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
    df = pd.read_csv(StringIO(csv_content), sep=';', encoding='utf-8-sig')
    df.columns = [limpiar_texto(c) for c in df.columns]
    c_t = next(c for c in ['FECHA/HORA MEDICION', 'HORA'] if c in df.columns)
    c_v = next(c for c in ['DECIBELIOS MEDIDOS', 'LAEQ'] if c in df.columns)
    c_id = next(c for c in ['CODIGO', 'ID_SONOMETRO'] if c in df.columns)
    
    df['FECHA_DT'] = pd.to_datetime(df[c_t], format='mixed', dayfirst=True)
    df['DECIBELIOS'] = pd.to_numeric(df[c_v].astype(str).str.replace(',', '.'), errors='coerce')
    df['PERIODO'] = df['FECHA_DT'].apply(clasificar_periodo)
    return df, c_id

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
    ax.set_title(f"{nombre_calle} ({id_sensor})\nAuditoría: {f_ini_dt.date()} a {f_fin_dt.date()}", fontsize=11)
    ax.set_ylabel("dB", fontsize=14)
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m %H:%M'))
    plt.xticks(rotation=45)
    return fig

def generar_grafico_dual(df_sel, nombre_calle, id_sensor, f_ini_dt, f_fin_dt):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    df_plot = df_sel.set_index('FECHA_DT').resample('15min').mean(numeric_only=True).reset_index()
    df_plot['PERIODO'] = df_plot['FECHA_DT'].apply(clasificar_periodo)
    
    # Panel Diurno
    df_dia = df_plot.copy()
    df_dia.loc[df_dia['PERIODO'] != 'DIA', 'DECIBELIOS'] = np.nan
    ax1.plot(df_dia['FECHA_DT'], df_dia['DECIBELIOS'], color='#f39c12', label="Día")
    ax1.axhline(65, color='red', linestyle='--', alpha=0.8)
    ax1.set_title(f"Periodo Diurno - {nombre_calle}", fontsize=11)
    ax1.set_ylim(40, 95)
    ax1.grid(True, alpha=0.2)

    # Panel Nocturno
    df_noche = df_plot.copy()
    df_noche.loc[df_noche['PERIODO'] != 'NOCHE', 'DECIBELIOS'] = np.nan
    ax2.plot(df_noche['FECHA_DT'], df_noche['DECIBELIOS'], color='#3498db', label="Noche")
    ax2.axhline(55, color='red', linestyle='--', alpha=0.8)
    ax2.set_title(f"Periodo Nocturno - {nombre_calle}", fontsize=11)
    ax2.set_ylim(40, 95)
    ax2.grid(True, alpha=0.2)

    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    plt.xticks(rotation=45)
    plt.tight_layout()
    return fig

# --- APLICACIÓN PRINCIPAL ---

def main():
    st.title("🔊 Auditoría Acústica Bilbao - Distrito Abando")
    
    df_raw, c_id = None, None
    st.sidebar.header("📂 Ingesta de Datos")
    
    metodo = st.sidebar.radio("Origen de la información:", 
                             ["Descarga Automática (Open Data)", "Carga Manual (Archivo CSV)"])

    if metodo == "Descarga Automática (Open Data)":
        url = "https://www.bilbao.eus/aytoonline/jsp/opendata/movilidad/od_sonometro_mediciones.jsp?idioma=c&formato=csv"
        if st.sidebar.button("🚀 Iniciar Descarga"):
            try:
                with st.spinner('Conectando con el servidor municipal...'):
                    # Intento de descarga con timeout corto para no bloquear la UI
                    r = requests.get(url, timeout=12)
                    r.raise_for_status()
                    df_raw, c_id = procesar_csv(r.text)
                    st.success("✅ Datos sincronizados correctamente")
            except:
                st.error("❌ El servidor de Bilbao no responde o bloquea la conexión.")
                st.info("💡 Consejo: Descarga el CSV desde tu navegador y usa la 'Carga Manual'.")
    else:
        file = st.sidebar.file_uploader("Sube el archivo .csv descargado", type=['csv'])
        if file:
            try:
                df_raw, c_id = procesar_csv(file.getvalue().decode("utf-8-sig"))
                st.success("✅ Archivo cargado y procesado")
            except Exception as e:
                st.error(f"Error al procesar el archivo: {e}")

    # Si hay datos, mostramos el dashboard
    if df_raw is not None:
        # Filtros de fecha en sidebar
        f_max = df_raw['FECHA_DT'].max().date()
        f_ini = st.sidebar.date_input("Fecha Inicio Auditoría", f_max - timedelta(days=7))
        f_fin = st.sidebar.date_input("Fecha Fin Auditoría", f_max)
        
        f_ini_dt = datetime.combine(f_ini, datetime.min.time())
        f_fin_dt = datetime.combine(f_fin, datetime.max.time())
        
        # Filtrado de datos por fecha
        df_f = df_raw[(df_raw['FECHA_DT'] >= f_ini_dt) & (df_raw['FECHA_DT'] <= f_fin_dt)].copy()
        dias_totales = (f_fin - f_ini).days + 1

        tabs = st.tabs(["📉 Análisis Temporal", "🛡️ Auditoría de Calidad", "🏆 Rankings de Ruido"])

        # TAB 1: GRÁFICOS
        with tabs[0]:
            sel_id = st.selectbox("Selecciona Ubicación del Sonómetro", 
                                 list(SENSORES_ABANDO.keys()), 
                                 format_func=lambda x: f"{SENSORES_ABANDO[x]} ({x})")
            
            sub_s = df_f[df_f[c_id] == sel_id]
            if sub_s.empty:
                st.warning(f"⚠️ No hay registros para {SENSORES_ABANDO[sel_id]} en las fechas seleccionadas.")
            else:
                st.subheader(f"📊 Evolución en {SENSORES_ABANDO[sel_id]}")
                if dias_totales <= 3:
                    # Gráfico de alta resolución para periodos cortos
                    fig = generar_grafico_unico(sub_s, SENSORES_ABANDO[sel_id], sel_id, f_ini_dt, f_fin_dt)
                else:
                    # Gráfico dual para periodos largos
                    fig = generar_grafico_dual(sub_s, SENSORES_ABANDO[sel_id], sel_id, f_ini_dt, f_fin_dt)
                st.pyplot(fig)

        # TAB 2: CALIDAD DE LA RED
        with tabs[1]:
            st.header("🛡️ Auditoría de Integridad de Datos")
            st.write(f"Evaluación basada en la recepción de 96 muestras diarias (1 cada 15 min) durante {dias_totales} días.")
            
            calidad_data = []
            color_map = {"Bueno": "#2ecc71", "Regular": "#f1c40f", "Sin Datos": "#e74c3c"}
            
            for sid, calle in SENSORES_ABANDO.items():
                count = len(df_f[df_f[c_id] == sid])
                esperado = dias_totales * 96
                porc = min(round((count / esperado) * 100, 1), 100.0) if esperado > 0 else 0
                est = "Bueno" if porc >= 90 else ("Regular" if porc > 0 else "Sin Datos")
                calidad_data.append({'Calle': calle, 'ID': sid, 'Muestras': count, 'Calidad %': porc, 'Estado': est, 'Color': color_map[est]})
            
            df_q = pd.DataFrame(calidad_data).sort_values('Calidad %', ascending=False)
            
            col_q1, col_q2 = st.columns([1, 1.2])
            with col_q1:
                st.markdown("**Salud Global de la Red de Abando**")
                counts = df_q['Estado'].value_counts()
                fig_pie, ax_pie = plt.subplots()
                ax_pie.pie(counts, labels=counts.index, autopct='%1.1f%%', 
                          colors=[color_map[x] for x in counts.index], startangle=90)
                st.pyplot(fig_pie)
            
            with col_q2:
                st.markdown("**Disponibilidad por Punto de Medida**")
                fig_bar, ax_bar = plt.subplots(figsize=(7, 10))
                ax_bar.barh(df_q['Calle'], df_q['Calidad %'], color=df_q['Color'])
                ax_bar.invert_yaxis()
                ax_bar.set_xlabel("% Datos recibidos")
                ax_bar.tick_params(axis='y', labelsize=8)
                st.pyplot(fig_bar)
            
            st.dataframe(df_q[['Calle', 'ID', 'Muestras', 'Calidad %', 'Estado']], 
                         hide_index=True, use_container_width=True)

        # TAB 3: RANKINGS
        with tabs[2]:
            st.header("🏆 Puntos Críticos (Máximos Registrados)")
            
            rank_list = []
            for sid, calle in SENSORES_ABANDO.items():
                ds = df_f[df_f[c_id] == sid]
                if not ds.empty:
                    m_d = ds[ds['PERIODO'] == 'DIA']['DECIBELIOS'].max()
                    m_n = ds[ds['PERIODO'] == 'NOCHE']['DECIBELIOS'].max()
                    rank_list.append({'Calle': calle, 'Máx Día (dB)': m_d, 'Máx Noche (dB)': m_n})
            
            if rank_list:
                df_rank = pd.DataFrame(rank_list)
                c_r1, c_r2 = st.columns(2)
                with c_r1:
                    st.subheader("☀️ Top 10 Ruidosos (Día)")
                    st.dataframe(df_rank.sort_values('Máx Día (dB)', ascending=False).head(10)[['Calle', 'Máx Día (dB)']], 
                                 hide_index=True, use_container_width=True)
                with c_r2:
                    st.subheader("🌙 Top 10 Ruidosos (Noche)")
                    st.dataframe(df_rank.sort_values('Máx Noche (dB)', ascending=False).head(10)[['Calle', 'Máx Noche (dB)']], 
                                 hide_index=True, use_container_width=True)
            else:
                st.info("No hay datos suficientes para calcular rankings.")

    else:
        # Mensaje de bienvenida/instrucciones
        st.info("👈 Selecciona un método de carga en el panel lateral para comenzar el análisis.")
        st.markdown("""
        ### Instrucciones:
        1. **Automático**: La aplicación intentará conectar directamente con el portal Open Data de Bilbao.
        2. **Manual**: Si la descarga automática falla (debido al Firewall del Ayuntamiento), descarga el archivo CSV 
           desde la web oficial y súbelo aquí.
        
        *Nota: Este dashboard está filtrado específicamente para los sensores del distrito de Abando.*
        """)

if __name__ == "__main__":
    main()
