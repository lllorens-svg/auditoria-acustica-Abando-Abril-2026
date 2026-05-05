mport streamlit as st
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

# --- GENERACIÓN DE GRÁFICOS ---

def generar_grafico_unico(df_sel, nombre_calle, id_sensor, f_ini_dt, f_fin_dt):
    fig, ax = plt.subplots(figsize=(12, 6))
    # Remuestreo para detectar huecos (NaN)
    df_plot = df_sel.set_index('FECHA_DT').resample('15min').mean(numeric_only=True).reset_index()
    df_plot['PERIODO'] = df_plot['FECHA_DT'].apply(clasificar_periodo)

    # Dibujar línea tramo a tramo para cambiar color según periodo
    for i in range(len(df_plot)-1):
        p1, p2 = df_plot.iloc[i], df_plot.iloc[i+1]
        color = '#f39c12' if p1['PERIODO'] == 'DIA' else '#3498db'
        if pd.notna(p1['DECIBELIOS']) and pd.notna(p2['DECIBELIOS']):
            ax.plot([p1['FECHA_DT'], p2['FECHA_DT']], [p1['DECIBELIOS'], p2['DECIBELIOS']], color=color, linewidth=2)

    ax.axhline(65, color='red', linestyle='--', alpha=0.6, label="Límite Día (65dB)")
    ax.axhline(55, color='blue', linestyle='--', alpha=0.6, label="Límite Noche (55dB)")

    f_str = f"{f_ini_dt.strftime('%d/%m/%Y')} - {f_fin_dt.strftime('%d/%m/%Y')}"
    ax.set_title(f"{nombre_calle} ({id_sensor})\nPeriodo de Auditoría: {f_str}", fontsize=11)
    ax.set_ylabel("Decibelios (dB)", fontsize=16)
    ax.set_ylim(40, 95)
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m %H:%M'))
    plt.xticks(rotation=45)
    return fig

def generar_grafico_dual(df_sel, nombre_calle, id_sensor, f_ini_dt, f_fin_dt):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    df_plot = df_sel.set_index('FECHA_DT').resample('15min').mean(numeric_only=True).reset_index()
    df_plot['PERIODO'] = df_plot['FECHA_DT'].apply(clasificar_periodo)

    f_str = f"{f_ini_dt.strftime('%d/%m/%Y')} - {f_fin_dt.strftime('%d/%m/%Y')}"

    # Panel Día
    df_dia = df_plot.copy()
    df_dia.loc[df_dia['PERIODO'] != 'DIA', 'DECIBELIOS'] = np.nan
    ax1.plot(df_dia['FECHA_DT'], df_dia['DECIBELIOS'], color='#f39c12')
    ax1.axhline(65, color='red', linestyle='-', alpha=0.8)
    ax1.set_title(f"Periodo Diurno - {nombre_calle} ({id_sensor}) | {f_str}", fontsize=11)
    ax1.set_ylabel("dB", fontsize=16)
    ax1.set_ylim(40, 95)
    ax1.grid(True, alpha=0.2)

    # Panel Noche
    df_noche = df_plot.copy()
    df_noche.loc[df_noche['PERIODO'] != 'NOCHE', 'DECIBELIOS'] = np.nan
    ax2.plot(df_noche['FECHA_DT'], df_noche['DECIBELIOS'], color='#3498db')
    ax2.axhline(55, color='red', linestyle='-', alpha=0.8)
    ax2.set_title(f"Periodo Nocturno - {nombre_calle} ({id_sensor})", fontsize=11)
    ax2.set_ylabel("dB", fontsize=16)
    ax2.set_ylim(40, 95)
    ax2.grid(True, alpha=0.2)

    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    plt.xticks(rotation=45)
    plt.tight_layout()
    return fig

# --- APLICACIÓN PRINCIPAL ---

def main():
    @st.cache_data(ttl=3600)
    def load_data():
        url = "https://www.bilbao.eus/aytoonline/jsp/opendata/movilidad/od_sonometro_mediciones.jsp?idioma=c&formato=csv"
        r = requests.get(url)
        df = pd.read_csv(StringIO(r.text), sep=';', encoding='utf-8-sig')
        df.columns = [limpiar_texto(c) for c in df.columns]
        c_t = next(c for c in ['FECHA/HORA MEDICION', 'HORA'] if c in df.columns)
        c_v = next(c for c in ['DECIBELIOS MEDIDOS', 'LAEQ'] if c in df.columns)
        c_id = next(c for c in ['CODIGO', 'ID_SONOMETRO'] if c in df.columns)
        
        df['FECHA_DT'] = pd.to_datetime(df[c_t], format='mixed', dayfirst=True)
        df['DECIBELIOS'] = pd.to_numeric(df[c_v].astype(str).str.replace(',', '.'), errors='coerce')
        df['PERIODO'] = df['FECHA_DT'].apply(clasificar_periodo)
        return df, c_id

    try:
        df_raw, c_id = load_data()
        
        st.sidebar.header("⚙️ Configuración")
        f_min, f_max = df_raw['FECHA_DT'].min().date(), df_raw['FECHA_DT'].max().date()
        f_ini = st.sidebar.date_input("Fecha Inicio", f_max - timedelta(days=7), min_value=f_min, max_value=f_max)
        f_fin = st.sidebar.date_input("Fecha Fin", f_max, min_value=f_min, max_value=f_max)
        
        f_ini_dt = datetime.combine(f_ini, datetime.min.time())
        f_fin_dt = datetime.combine(f_fin, datetime.max.time())
        df_f = df_raw[(df_raw['FECHA_DT'] >= f_ini_dt) & (df_raw['FECHA_DT'] <= f_fin_dt)].copy()
        
        dias_totales = (f_fin - f_ini).days + 1
        sel_id = st.sidebar.selectbox(
            "Selecciona Sonómetro", 
            list(SENSORES_ABANDO.keys()), 
            format_func=lambda x: f"{SENSORES_ABANDO[x]} ({x})"
        )

        tabs = st.tabs(["📉 Análisis Temporal", "🛡️ Auditoría de Calidad", "🏆 Rankings"])

        with tabs[0]:
            st.title(f"🔊 {SENSORES_ABANDO[sel_id]} ({sel_id})")
            st.markdown(f"**Periodo de Auditoría:** {f_ini.strftime('%d/%m/%Y')} al {f_fin.strftime('%d/%m/%Y')}")
            sub_s = df_f[df_f[c_id] == sel_id]
            if sub_s.empty:
                st.error("⚠️ ESTE SONÓMETRO NO TIENE DATOS REGISTRADOS EN EL RANGO SELECCIONADO.")
            else:
                if dias_totales <= 3:
                    fig = generar_grafico_unico(sub_s, SENSORES_ABANDO[sel_id], sel_id, f_ini_dt, f_fin_dt)
                else:
                    fig = generar_grafico_dual(sub_s, SENSORES_ABANDO[sel_id], sel_id, f_ini_dt, f_fin_dt)
                st.pyplot(fig)

        with tabs[1]:
            st.header("🛡️ Auditoría de Calidad")
            calidad_info = []
            color_map = {"Bueno": "#2ecc71", "Regular": "#f1c40f", "Sin Datos": "#e74c3c"}
            
            for sid, calle in SENSORES_ABANDO.items():
                data_sensor = df_f[df_f[c_id] == sid]
                # Esperamos 96 registros cada 24h (uno cada 15 min)
                esperado = dias_totales * 96
                porc = min(round((len(data_sensor) / esperado) * 100, 1), 100.0) if esperado > 0 else 0
                est = "Bueno" if porc >= 90 else ("Regular" if porc > 0 else "Sin Datos")
                calidad_info.append({
                    'Calle': calle, 
                    'ID': sid, 
                    'Calidad %': porc, 
                    'Estado': est, 
                    'Color': color_map[est]
                })
            
            # Ordenar estrictamente de mejor a peor para el gráfico y tabla
            df_q = pd.DataFrame(calidad_info).sort_values('Calidad %', ascending=False)
            
            col1, col2 = st.columns([1, 1.2])
            with col1:
                st.subheader("Estado General de la Red")
                counts = df_q['Estado'].value_counts()
                # Asegurar que los colores coinciden con las etiquetas presentes
                colors_pie = [color_map[label] for label in counts.index]
                fig_p, ax_p = plt.subplots()
                ax_p.pie(counts, labels=counts.index, autopct='%1.1f%%', colors=colors_pie, startangle=90)
                ax_p.set_title("Auditoría de Calidad", fontsize=12)
                st.pyplot(fig_p)
            
            with col2:
                st.subheader("Disponibilidad por Sonómetro")
                fig_b, ax_b = plt.subplots(figsize=(7, 12))
                ax_b.barh(df_q['Calle'], df_q['Calidad %'], color=df_q['Color'])
                ax_b.set_title("Auditoría de Calidad (Bueno a Malo)", fontsize=11)
                ax_b.set_xlabel("% de Información Recibida", fontsize=12)
                ax_b.tick_params(axis='y', labelsize=8)
                ax_b.invert_yaxis() # Los mejores arriba
                st.pyplot(fig_b)
            
            st.markdown("**Desglose Detallado**")
            st.dataframe(df_q[['Calle', 'ID', 'Calidad %', 'Estado']], hide_index=True, use_container_width=True)

        with tabs[2]:
            st.header("🏆 Rankings de Ruido (Valores Máximos)")
            metrics = []
            for sid, calle in SENSORES_ABANDO.items():
                ds = df_f[df_f[c_id] == sid]
                if not ds.empty:
                    m_d = ds[ds['PERIODO'] == 'DIA']['DECIBELIOS'].max()
                    m_n = ds[ds['PERIODO'] == 'NOCHE']['DECIBELIOS'].max()
                    metrics.append({'Calle': calle, 'Max Día (dB)': m_d, 'Max Noche (dB)': m_n})
            
            df_m = pd.DataFrame(metrics)
            if not df_m.empty:
                c1, c2 = st.columns(2)
                with c1:
                    st.subheader("☀️ Top 10 - Diurno")
                    df_top_d = df_m.sort_values('Max Día (dB)', ascending=False).head(10)
                    st.dataframe(df_top_d[['Calle', 'Max Día (dB)']], hide_index=True, use_container_width=True)
                with c2:
                    st.subheader("🌙 Top 10 - Nocturno")
                    df_top_n = df_m.sort_values('Max Noche (dB)', ascending=False).head(10)
                    st.dataframe(df_top_n[['Calle', 'Max Noche (dB)']], hide_index=True, use_container_width=True)
            else:
                st.info("No hay mediciones suficientes para generar rankings.")

    except Exception as e:
        st.error(f"Se ha producido un error al cargar los datos: {e}")

if __name__ == "__main__":
    main()
