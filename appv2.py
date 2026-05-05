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
# Establecemos el título de la pestaña y el layout ancho para mejor visualización de gráficos
st.set_page_config(
    page_title="Auditoría Acústica Bilbao - Abando", 
    page_icon="🔊",
    layout="wide"
)

# --- DICCIONARIO MAESTRO: 32 SENSORES DE ABANDO ---
# Este diccionario actúa como filtro principal para asegurar que solo analizamos el Distrito Abando
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

# --- LISTA DE FESTIVOS BILBAO 2026 ---
# Se utiliza para el sombreado de días especiales en los gráficos
FESTIVOS_BILBAO = [
    '2026-01-01', '2026-01-06', '2026-03-19', '2026-04-02', '2026-04-03', 
    '2026-04-06', '2026-05-01', '2026-07-25', '2026-08-15', '2026-10-12', 
    '2026-11-01', '2026-12-06', '2026-12-08', '2026-12-25'
]

# --- FUNCIONES DE UTILIDAD Y PROCESAMIENTO ---

def limpiar_texto(texto):
    """Normaliza encabezados para evitar errores por tildes o mayúsculas."""
    if not isinstance(texto, str): return texto
    texto = unicodedata.normalize('NFD', texto).encode('ascii', 'ignore').decode("utf-8")
    return texto.strip().upper()

def clasificar_periodo(dt):
    """Clasifica una fecha en periodo DIA (07:00-23:00) o NOCHE."""
    if not isinstance(dt, datetime): return "N/A"
    return "DIA" if 7 <= dt.hour < 23 else "NOCHE"

def es_dia_especial(dt):
    """Detecta si es fin de semana, festivo o víspera para el sombreado."""
    # Viernes(4), Sábado(5), Domingo(6)
    if dt.weekday() in [4, 5, 6]:
        return True
    fecha_str = dt.strftime('%Y-%m-%d')
    if fecha_str in FESTIVOS_BILBAO:
        return True
    # Comprobar si mañana es festivo (víspera)
    vispera_de = (dt + timedelta(days=1)).strftime('%Y-%m-%d')
    if vispera_de in FESTIVOS_BILBAO:
        return True
    return False

def procesar_csv(csv_content):
    """Carga y limpia el CSV detectando columnas de forma flexible."""
    try:
        # Intento 1: Separador punto y coma (Estándar Bilbao)
        df = pd.read_csv(StringIO(csv_content), sep=';', encoding='utf-8-sig')
        if len(df.columns) < 2:
            # Intento 2: Separador coma
            df = pd.read_csv(StringIO(csv_content), sep=',', encoding='utf-8-sig')
    except:
        # Intento 3: Detección automática de motor Python
        df = pd.read_csv(StringIO(csv_content), sep=None, engine='python', encoding='utf-8-sig')
        
    df.columns = [limpiar_texto(c) for c in df.columns]
    
    # Identificación de columnas clave por nombre parcial
    c_t = next(c for c in ['FECHA/HORA MEDICION', 'HORA', 'FECHA'] if c in df.columns)
    c_v = next(c for c in ['DECIBELIOS MEDIDOS', 'LAEQ', 'DECIBELIOS'] if c in df.columns)
    c_id = next(c for c in ['CODIGO', 'ID_SONOMETRO', 'ID'] if c in df.columns)
    
    # Convertir a tipos de datos correctos
    df['FECHA_DT'] = pd.to_datetime(df[c_t], errors='coerce')
    df['DECIBELIOS'] = pd.to_numeric(df[c_v].astype(str).str.replace(',', '.'), errors='coerce')
    
    # Filtrar solo sensores pertenecientes a Abando
    df = df[df[c_id].isin(SENSORES_ABANDO.keys())]
    df = df.dropna(subset=['FECHA_DT', 'DECIBELIOS'])
    
    # Clasificar por tramo horario
    df['PERIODO'] = df['FECHA_DT'].apply(clasificar_periodo)
    
    return df.sort_values('FECHA_DT'), c_id

# --- GENERACIÓN DE GRÁFICOS ---

def aplicar_sombreado_especial(ax, f_ini_dt, f_fin_dt):
    """Dibuja bandas grises en los días de mayor ocio (viernes a domingo y festivos)."""
    current = f_ini_dt.replace(hour=0, minute=0, second=0)
    while current <= f_fin_dt:
        if es_dia_especial(current):
            ax.axvspan(current, current + timedelta(days=1), color='gray', alpha=0.15, zorder=0)
        current += timedelta(days=1)

def generar_grafico_unico(df_sel, nombre_calle, id_sensor, f_ini_dt, f_fin_dt):
    """Gráfico para periodos cortos (< 7 días) con líneas de colores intercaladas."""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Remuestreo para suavizar líneas si hay huecos
    df_plot = df_sel.set_index('FECHA_DT').resample('15min').mean(numeric_only=True).reset_index()
    df_plot['PERIODO'] = df_plot['FECHA_DT'].apply(clasificar_periodo)

    aplicar_sombreado_especial(ax, f_ini_dt, f_fin_dt)

    # Dibujamos segmento a segmento para cambiar el color según el periodo
    for i in range(len(df_plot)-1):
        p1, p2 = df_plot.iloc[i], df_plot.iloc[i+1]
        color = '#f39c12' if p1['PERIODO'] == 'DIA' else '#3498db'
        if pd.notna(p1['DECIBELIOS']) and pd.notna(p2['DECIBELIOS']):
            ax.plot([p1['FECHA_DT'], p2['FECHA_DT']], [p1['DECIBELIOS'], p2['DECIBELIOS']], color=color, linewidth=2)

    # Líneas de referencia legal
    ax.axhline(65, color='red', linestyle='--', alpha=0.6, label="Límite Día (65dB)")
    ax.axhline(55, color='blue', linestyle='--', alpha=0.6, label="Límite Noche (55dB)")
    
    # Configuración de ejes y escala comparable
    ax.set_title(f"{nombre_calle} ({id_sensor})\nAnalizado: {f_ini_dt.strftime('%d/%m/%Y')} al {f_fin_dt.strftime('%d/%m/%Y')}", fontsize=11)
    ax.set_ylabel("Nivel de presión sonora dB(A)", fontsize=11)
    ax.set_ylim(30, 100) 
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m %H:%M'))
    plt.xticks(rotation=45)
    
    return fig

def generar_grafico_dual(df_sel, nombre_calle, id_sensor, f_ini_dt, f_fin_dt):
    """Gráfico para periodos largos (> 7 días) separando Día y Noche en subplots."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    
    df_plot = df_sel.set_index('FECHA_DT').resample('15min').mean(numeric_only=True).reset_index()
    df_plot['PERIODO'] = df_plot['FECHA_DT'].apply(clasificar_periodo)
    
    aplicar_sombreado_especial(ax1, f_ini_dt, f_fin_dt)
    aplicar_sombreado_especial(ax2, f_ini_dt, f_fin_dt)

    # Subplot Diurno
    df_dia = df_plot.copy()
    df_dia.loc[df_dia['PERIODO'] != 'DIA', 'DECIBELIOS'] = np.nan
    ax1.plot(df_dia['FECHA_DT'], df_dia['DECIBELIOS'], color='#f39c12', linewidth=1.5)
    ax1.axhline(65, color='red', linestyle='--', alpha=0.8)
    ax1.set_title(f"Evolución Diurna - {nombre_calle} ({f_ini_dt.strftime('%d/%m/%Y')} - {f_fin_dt.strftime('%d/%m/%Y')})", fontsize=10)
    ax1.set_ylim(30, 100) 
    ax1.grid(True, alpha=0.2)

    # Subplot Nocturno
    df_noche = df_plot.copy()
    df_noche.loc[df_noche['PERIODO'] != 'NOCHE', 'DECIBELIOS'] = np.nan
    ax2.plot(df_noche['FECHA_DT'], df_noche['DECIBELIOS'], color='#3498db', linewidth=1.5)
    ax2.axhline(55, color='red', linestyle='--', alpha=0.8)
    ax2.set_title(f"Evolución Nocturna - {nombre_calle} ({f_ini_dt.strftime('%d/%m/%Y')} - {f_fin_dt.strftime('%d/%m/%Y')})", fontsize=10)
    ax2.set_ylim(30, 100) 
    ax2.grid(True, alpha=0.2)

    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    return fig

# --- LÓGICA DE LA APLICACIÓN (STREAMLIT) ---

def main():
    st.title("🔊 Auditoría Acústica Bilbao - Distrito Abando")
    st.markdown("Herramienta técnica para la inspección de niveles sonoros en zonas residenciales y de ocio.")
    
    df_raw, c_id = None, None
    
    # PANEL LATERAL: INGESTA DE DATOS
    st.sidebar.header("📂 Gestión de Datos")
    
    entorno = "Nube (Streamlit Cloud)" if "streamlit" in str(st.sidebar) else "Local (Mac)"
    st.sidebar.caption(f"Entorno detectado: {entorno}")
    
    metodo = st.sidebar.radio(
        "Seleccione origen de datos:", 
        ["Carga Manual (.csv)", "Descarga Automática Open Data"]
    )

    if metodo == "Descarga Automática Open Data":
        url = "https://www.bilbao.eus/aytoonline/jsp/opendata/movilidad/od_sonometro_mediciones.jsp?idioma=c&formato=csv"
        st.sidebar.info("La descarga directa puede fallar en la nube por restricciones de seguridad del Ayuntamiento.")
        if st.sidebar.button("🚀 Iniciar Sincronización"):
            try:
                with st.spinner('Conectando con el servidor municipal...'):
                    r = requests.get(url, timeout=20)
                    r.raise_for_status()
                    df_raw, c_id = procesar_csv(r.text)
                    st.success(f"✅ Conexión exitosa. {len(df_raw)} registros de Abando obtenidos.")
            except Exception as e:
                st.error("❌ Error de conexión remota.")
                st.warning("Se recomienda descargar el CSV desde la web de Bilbao y usar 'Carga Manual'.")
    else:
        file = st.sidebar.file_uploader("Subir archivo CSV (Formato Bilbao Open Data)", type=['csv'])
        if file:
            try:
                content = file.getvalue().decode("utf-8-sig")
                df_raw, c_id = procesar_csv(content)
                st.success(f"✅ Archivo procesado correctamente. {len(df_raw)} muestras encontradas.")
            except Exception as e:
                st.error(f"Error de formato: {e}")

    # CUERPO DEL DASHBOARD
    if df_raw is not None:
        # Configuración de fechas
        f_min_data = df_raw['FECHA_DT'].min().date()
        f_max_data = df_raw['FECHA_DT'].max().date()
        
        st.sidebar.subheader("🗓️ Ventana de Análisis")
        f_ini = st.sidebar.date_input("Fecha Inicio", f_min_data)
        f_fin = st.sidebar.date_input("Fecha Fin", f_max_data)
        
        f_ini_dt = datetime.combine(f_ini, datetime.min.time())
        f_fin_dt = datetime.combine(f_fin, datetime.max.time())
        
        # Filtrado temporal
        df_f = df_raw[(df_raw['FECHA_DT'] >= f_ini_dt) & (df_raw['FECHA_DT'] <= f_fin_dt)].copy()
        dias_calculados = max((f_fin - f_ini).days + 1, 1)

        # Organización en Pestañas
        tabs = st.tabs(["🛡️ Auditoría de Calidad", "📉 Análisis Temporal", "🏆 Rankings y Picos"])

        # PESTAÑA 1: CALIDAD DE DATOS
        with tabs[0]:
            st.header("🛡️ Integridad de la Red de Sensores")
            st.write("Verificación de la continuidad del servicio (Objetivo: 96 muestras diarias por sensor).")
            
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
                
                calidad_list.append({'Calle': calle, 'ID': sid, 'Muestras': muestras, '%': porcentaje, 'Estado': est, 'Color': color_map[est]})
            
            df_q = pd.DataFrame(calidad_list).sort_values('%', ascending=False)
            
            col_q1, col_q2 = st.columns([1, 1.3])
            with col_q1:
                st.subheader("Distribución de Salud")
                counts = df_q['Estado'].value_counts()
                fig_p, ax_p = plt.subplots()
                ax_p.pie(counts, labels=counts.index, autopct='%1.1f%%', 
                        colors=[color_map.get(x) for x in counts.index], startangle=90)
                st.pyplot(fig_p)
            
            with col_q2:
                st.subheader("Rendimiento por Calle")
                fig_b, ax_b = plt.subplots(figsize=(7, 10))
                ax_b.barh(df_q['Calle'], df_q['%'], color=df_q['Color'])
                ax_b.invert_yaxis()
                ax_b.set_xlabel("% de Transmisión")
                st.pyplot(fig_b)
            
            st.dataframe(df_q[['Calle', 'ID', 'Muestras', '%', 'Estado']], hide_index=True, use_container_width=True)

        # PESTAÑA 2: GRÁFICOS TEMPORALES
        with tabs[1]:
            st.header("📉 Evolución por Punto de Medida")
            sel_id = st.selectbox(
                "Seleccione sensor para visualizar:", 
                list(SENSORES_ABANDO.keys()), 
                format_func=lambda x: f"{SENSORES_ABANDO[x]} ({x})"
            )
            
            df_sensor = df_f[df_f[c_id] == sel_id]
            
            if not df_sensor.empty:
                # Lógica de separación si el periodo es largo
                if dias_calculados > 7:
                    st.info("💡 Periodo largo detectado (>7 días): Visualización separada por tramos.")
                    st.pyplot(generar_grafico_dual(df_sensor, SENSORES_ABANDO[sel_id], sel_id, f_ini_dt, f_fin_dt))
                else:
                    st.pyplot(generar_grafico_unico(df_sensor, SENSORES_ABANDO[sel_id], sel_id, f_ini_dt, f_fin_dt))
            else:
                st.warning("No se encontraron registros para este sensor en las fechas seleccionadas.")

        # PESTAÑA 3: RANKINGS Y PICOS
        with tabs[2]:
            st.header("🏆 Picos de Ruido Registrados")
            st.write("Identificación de los puntos con mayor presión sonora durante el periodo.")
            
            rankings = []
            for sid, calle in SENSORES_ABANDO.items():
                ds = df_f[df_f[c_id] == sid]
                if not ds.empty:
                    # Cálculo pico Diurno
                    df_d = ds[ds['PERIODO'] == 'DIA']
                    pico_d = df_d.loc[df_d['DECIBELIOS'].idxmax()] if not df_d.empty else None
                    # Cálculo pico Nocturno
                    df_n = ds[ds['PERIODO'] == 'NOCHE']
                    pico_n = df_n.loc[df_n['DECIBELIOS'].idxmax()] if not df_n.empty else None
                    
                    rankings.append({
                        'Calle': calle, 
                        'dB Día': pico_d['DECIBELIOS'] if pico_d is not None else 0, 
                        'Hora Día': pico_d['FECHA_DT'].strftime('%d/%m %H:%M') if pico_d is not None else "-", 
                        'dB Noche': pico_n['DECIBELIOS'] if pico_n is not None else 0, 
                        'Hora Noche': pico_n['FECHA_DT'].strftime('%d/%m %H:%M') if pico_n is not None else "-"
                    })
            
            if rankings:
                df_r = pd.DataFrame(rankings)
                cr1, cr2 = st.columns(2)
                with cr1:
                    st.subheader("☀️ Top 10 Ruidosos (Diurno)")
                    st.dataframe(df_r.sort_values('dB Día', ascending=False).head(10)[['Calle', 'dB Día', 'Hora Día']], 
                                 hide_index=True, use_container_width=True)
                with cr2:
                    st.subheader("🌙 Top 10 Ruidosos (Nocturno)")
                    st.dataframe(df_r.sort_values('dB Noche', ascending=False).head(10)[['Calle', 'dB Noche', 'Hora Noche']], 
                                 hide_index=True, use_container_width=True)
            else:
                st.info("No hay datos suficientes para generar rankings.")
    else:
        # Estado inicial
        st.info("👈 Cargue un archivo CSV o use la sincronización automática para comenzar el análisis.")

if __name__ == "__main__":
    main()
