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

FESTIVOS_BILBAO = [
    '2026-01-01', '2026-01-06', '2026-03-19', '2026-04-02', '2026-04-03', 
    '2026-04-06', '2026-05-01', '2026-07-25', '2026-08-15', '2026-10-12', 
    '2026-11-01', '2026-12-06', '2026-12-08', '2026-12-25'
]

COLORES_ESTADO = {
    'Óptimos': '#2ecc71', 
    'Regulares': '#f1c40f', 
    'Malos': '#e67e22', 
    'Sin Datos': '#95a5a6'
}

# --- UTILIDADES DE PROCESAMIENTO ---

def limpiar_texto(texto):
    if not isinstance(texto, str): return texto
    texto = unicodedata.normalize('NFD', texto).encode('ascii', 'ignore').decode("utf-8")
    return texto.strip().upper()

def clasificar_periodo(dt):
    if not isinstance(dt, datetime): return "N/A"
    return "DIA" if 7 <= dt.hour < 23 else "NOCHE"

def es_dia_especial(dt):
    # Fines de semana (Viernes, Sábado, Domingo)
    if dt.weekday() in [4, 5, 6]: return True 
    # Festivos
    fecha_str = dt.strftime('%Y-%m-%d')
    if fecha_str in FESTIVOS_BILBAO: return True
    # Vísperas de festivos (si el día siguiente es festivo)
    mañana_str = (dt + timedelta(days=1)).strftime('%Y-%m-%d')
    if mañana_str in FESTIVOS_BILBAO: return True
    return False

@st.cache_data(show_spinner=False)
def procesar_datos_cache(csv_content):
    try:
        df = pd.read_csv(StringIO(csv_content), sep=';', encoding='utf-8-sig')
        if len(df.columns) < 2:
            df = pd.read_csv(StringIO(csv_content), sep=',', encoding='utf-8-sig')
    except:
        df = pd.read_csv(StringIO(csv_content), sep=None, engine='python', encoding='utf-8-sig')
        
    df.columns = [limpiar_texto(c) for c in df.columns]
    
    c_t = next(c for c in ['FECHA/HORA MEDICION', 'HORA', 'FECHA'] if c in df.columns)
    c_v = next(c for c in ['DECIBELIOS MEDIDOS', 'LAEQ', 'DECIBELIOS'] if c in df.columns)
    c_id = next(c for c in ['CODIGO', 'ID_SONOMETRO', 'ID'] if c in df.columns)
    
    df['FECHA_DT'] = pd.to_datetime(df[c_t], errors='coerce')
    df['DECIBELIOS'] = pd.to_numeric(df[c_v].astype(str).str.replace(',', '.'), errors='coerce')
    
    df = df[df[c_id].isin(SENSORES_ABANDO.keys())]
    df = df.dropna(subset=['FECHA_DT', 'DECIBELIOS'])
    df['PERIODO'] = df['FECHA_DT'].apply(clasificar_periodo)
    
    return df.sort_values('FECHA_DT'), c_id

# --- MOTOR GRÁFICO ---

def aplicar_estetica_ejes(ax, titulo, f_ini, f_fin, ylabel="dB(A)"):
    ax.set_title(titulo, fontsize=10, fontweight='bold', pad=10)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.set_ylim(30, 95)
    # Eje X constante basado en la selección del usuario
    ax.set_xlim(f_ini, f_fin)
    ax.grid(True, alpha=0.2, linestyle='--')
    ax.tick_params(labelsize=8)

def sombrear_especiales(ax, f_ini, f_fin):
    """Aplica sombreado gris a fines de semana y vísperas de festivos"""
    curr = f_ini.replace(hour=0, minute=0, second=0, microsecond=0)
    while curr <= f_fin:
        if es_dia_especial(curr):
            ax.axvspan(curr, curr + timedelta(days=1), color='gray', alpha=0.1)
        curr += timedelta(days=1)

def generar_grafico_unificado(df_sel, f_ini, f_fin):
    """Genera un gráfico continuo coloreando por periodo (Día naranja, Noche azul)"""
    fig, ax = plt.subplots(figsize=(12, 5))
    df_p = df_sel.sort_values('FECHA_DT')
    
    # Sombreado de días especiales
    sombrear_especiales(ax, f_ini, f_fin)

    if not df_p.empty:
        tiempos = df_p['FECHA_DT'].values
        valores = df_p['DECIBELIOS'].values
        periodos = df_p['PERIODO'].values

        # Dibujamos segmentos para mantener el color naranja/azul
        for i in range(len(tiempos) - 1):
            t1, t2 = tiempos[i], tiempos[i+1]
            v1, v2 = valores[i], valores[i+1]
            p1 = periodos[i]
            
            # Ignorar saltos mayores a 20 min para no unir puntos lejanos
            diff = (t2 - t1).astype('timedelta64[m]').astype(int)
            if diff <= 20:
                color = '#e67e22' if p1 == "DIA" else '#2980b9'
                ax.plot([t1, t2], [v1, v2], color=color, linewidth=1.2, alpha=0.8)

    # Proxy para leyenda
    ax.plot([], [], color='#e67e22', label="Nivel Día")
    ax.plot([], [], color='#2980b9', label="Nivel Noche")
    
    # Límites de referencia
    ax.axhline(65, color='red', linestyle='--', linewidth=0.8, alpha=0.5, label="Límite Día (65dB)")
    ax.axhline(55, color='darkblue', linestyle='--', linewidth=0.8, alpha=0.5, label="Límite Noche (55dB)")
    
    aplicar_estetica_ejes(ax, "Evolución Acústica 24h (Día: Naranja | Noche: Azul)", f_ini, f_fin)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m %H:%M'))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=12))
    ax.legend(fontsize=8, loc='upper right', ncol=2)
    plt.tight_layout()
    return fig

def generar_grafico_periodo(df_sel, periodo, color, limite, f_ini, f_fin):
    """Genera gráfico filtrado por periodo para rangos largos"""
    fig, ax = plt.subplots(figsize=(12, 4))
    
    # Sombreado de días especiales
    sombrear_especiales(ax, f_ini, f_fin)
    
    df_p = df_sel[df_sel['PERIODO'] == periodo].copy().sort_values('FECHA_DT')
    
    if not df_p.empty:
        tiempos = df_p['FECHA_DT'].values
        valores = df_p['DECIBELIOS'].values
        new_tiempos, new_valores = [tiempos[0]], [valores[0]]
        
        for i in range(1, len(tiempos)):
            diff = (tiempos[i] - tiempos[i-1]).astype('timedelta64[m]').astype(int)
            if diff > 20:
                new_tiempos.append(tiempos[i-1] + (tiempos[i] - tiempos[i-1]) / 2)
                new_valores.append(np.nan)
            new_tiempos.append(tiempos[i])
            new_valores.append(valores[i])

        ax.plot(new_tiempos, new_valores, color=color, linewidth=1.5, alpha=0.8, label=f"Nivel {periodo}")
    
    ax.axhline(limite, color='red', linestyle='--', linewidth=1, alpha=0.7, label=f"Límite {limite}dB")
    
    aplicar_estetica_ejes(ax, f"Análisis Temporal: Periodo {periodo}", f_ini, f_fin)
    delta_dias = (f_fin - f_ini).days
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, delta_dias // 10)))
    ax.legend(fontsize=8, loc='upper right')
    plt.tight_layout()
    return fig

# --- APP PRINCIPAL ---

def main():
    st.title("🔊 Auditoría Acústica Bilbao - Distrito Abando")
    
    if 'df_master' not in st.session_state:
        st.session_state.df_master = None
        st.session_state.col_id = None

    st.sidebar.header("📂 Gestión de Datos")
    metodo = st.sidebar.radio("Origen:", ["Sincronización Open Data", "Carga Manual (.csv)"])

    csv_to_load = None
    if metodo == "Sincronización Open Data":
        if st.sidebar.button("🚀 Sincronizar con Bilbao Cloud"):
            url_target = "https://www.bilbao.eus/aytoonline/jsp/opendata/movilidad/od_sonometro_mediciones.jsp?idioma=c&formato=csv"
            proxies = [f"https://api.allorigins.win/raw?url={url_target}", f"https://corsproxy.io/?{url_target}"]
            success = False
            for url in proxies:
                try:
                    r = requests.get(url, timeout=20)
                    if r.status_code == 200 and len(r.text) > 500:
                        csv_to_load = r.text
                        success = True
                        break
                except: continue
            if not success: st.sidebar.error("Error de conexión.")
    else:
        file = st.sidebar.file_uploader("Subir CSV", type=['csv'])
        if file: csv_to_load = file.getvalue().decode("utf-8-sig")

    if csv_to_load:
        with st.spinner('Procesando integridad...'):
            df_proc, cid = procesar_datos_cache(csv_to_load)
            st.session_state.df_master = df_proc
            st.session_state.col_id = cid

    if st.session_state.df_master is not None:
        df_all = st.session_state.df_master
        c_id = st.session_state.col_id
        
        st.sidebar.subheader("🗓️ Filtro Temporal")
        f_min, f_max = df_all['FECHA_DT'].min().date(), df_all['FECHA_DT'].max().date()
        f_ini = st.sidebar.date_input("Desde", f_min)
        f_fin = st.sidebar.date_input("Hasta", f_max)
        
        f_ini_dt = datetime.combine(f_ini, datetime.min.time())
        f_fin_dt = datetime.combine(f_fin, datetime.max.time())
        df_f = df_all[(df_all['FECHA_DT'] >= f_ini_dt) & (df_all['FECHA_DT'] <= f_fin_dt)]

        tabs = st.tabs(["📊 Integridad de la Red", "📈 Series Temporales", "🚩 Impactos Máximos"])

        with tabs[0]:
            col1, col2 = st.columns([1, 2])
            dias_total = max((f_fin - f_ini).days + 1, 1)
            esperados = dias_total * 96 
            salud_stats = {'Óptimos': 0, 'Regulares': 0, 'Malos': 0, 'Sin Datos': 0}
            cobertura_data = []
            
            for sid, calle in SENSORES_ABANDO.items():
                actual = len(df_f[df_f[c_id] == sid])
                pct = min((actual / esperados) * 100, 100.0)
                
                if pct > 90: 
                    estado = 'Óptimos'
                elif pct > 50: 
                    estado = 'Regulares'
                elif pct > 0: 
                    estado = 'Malos'
                else: 
                    estado = 'Sin Datos'
                
                salud_stats[estado] += 1
                cobertura_data.append({
                    'Calle': calle, 
                    'Cobertura %': pct, 
                    'Color': COLORES_ESTADO[estado]
                })

            with col1:
                st.subheader("Estado de Integridad")
                fig_pie, ax_pie = plt.subplots()
                labels = [k for k, v in salud_stats.items() if v > 0]
                values = [v for k, v in salud_stats.items() if v > 0]
                ax_pie.pie(values, labels=labels, autopct='%1.1f%%', colors=[COLORES_ESTADO[l] for l in labels], startangle=90)
                st.pyplot(fig_pie)

            with col2:
                st.subheader("Continuidad por Sensor")
                df_cob = pd.DataFrame(cobertura_data).sort_values('Cobertura %', ascending=True)
                fig_bar, ax_bar = plt.subplots(figsize=(10, 8))
                ax_bar.barh(df_cob['Calle'], df_cob['Cobertura %'], color=df_cob['Color'])
                ax_bar.set_xlim(0, 105)
                ax_bar.set_xlabel("Cobertura (%)", fontsize=9)
                st.pyplot(fig_bar)

        with tabs[1]:
            sensores_con_datos = df_f[c_id].unique()
            opciones_sensor = [sid for sid in SENSORES_ABANDO.keys() if sid in sensores_con_datos]
            
            if opciones_sensor:
                sel_id = st.selectbox("Seleccionar Sensor:", opciones_sensor, format_func=lambda x: f"{SENSORES_ABANDO[x]} ({x})")
                df_s = df_f[df_f[c_id] == sel_id]
                st.markdown(f"### Ubicación: {SENSORES_ABANDO[sel_id]}")
                
                delta_dias = (f_fin - f_ini).days
                if delta_dias < 7:
                    st.info("Visualización Unificada: Serie temporal continua (Día: Naranja, Noche: Azul). Eje X constante según filtro.")
                    fig_uni = generar_grafico_unificado(df_s, f_ini_dt, f_fin_dt)
                    if fig_uni: st.pyplot(fig_uni)
                else:
                    st.info("Visualización por Periodos: Niveles Diurnos y Nocturnos en gráficas separadas. Eje X constante según filtro.")
                    fig_day = generar_grafico_periodo(df_s, "DIA", "#e67e22", 65, f_ini_dt, f_fin_dt)
                    if fig_day: st.pyplot(fig_day)
                    fig_night = generar_grafico_periodo(df_s, "NOCHE", "#2980b9", 55, f_ini_dt, f_fin_dt)
                    if fig_night: st.pyplot(fig_night)
            else:
                st.warning("No hay datos para el rango seleccionado.")

        with tabs[2]:
            st.subheader("Top 5 Impactos Críticos")
            df_rank = df_f.copy()
            df_rank['Ubicación'] = df_rank[c_id].map(SENSORES_ABANDO)
            df_rank['Instante'] = df_rank['FECHA_DT'].dt.strftime('%d/%m %H:%M')
            
            def get_top_5_unique(data):
                if data.empty: return pd.DataFrame()
                # Obtenemos los valores máximos únicos por sensor para evitar duplicar calles si tienen varios picos
                return data.sort_values('DECIBELIOS', ascending=False).drop_duplicates(subset=[c_id]).head(5)[['Ubicación', 'DECIBELIOS', 'Instante']]
            
            col_d, col_n = st.columns(2)
            with col_d:
                st.markdown("☀️ **Día (Lmax registrados)**")
                st.dataframe(
                    get_top_5_unique(df_rank[df_rank['PERIODO'] == 'DIA']), 
                    use_container_width=True, 
                    hide_index=True
                )
            with col_n:
                st.markdown("🌙 **Noche (Lmax registrados)**")
                st.dataframe(
                    get_top_5_unique(df_rank[df_rank['PERIODO'] == 'NOCHE']), 
                    use_container_width=True, 
                    hide_index=True
                )
    else:
        st.info("Dashboard listo. Cargue datos para comenzar.")

if __name__ == "__main__":
    main()
