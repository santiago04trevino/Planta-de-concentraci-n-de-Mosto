import streamlit as st
import biosteam as bst
import thermosteam as tmo
import pandas as pd
import os
import base64
import math
import google.generativeai as genai
import fitz  # PyMuPDF: Necesario para renderizar PDFs evadiendo el bloqueo del navegador
import streamlit.components.v1 as components # <-- IMPORTACIÓN AÑADIDA PARA RENDERIZAR HTML/SVG

# ==========================================
# 0. CONFIGURACIÓN DE LA PÁGINA
# ==========================================
st.set_page_config(
    page_title="Simulador BioSTEAM - Separación de Etanol", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 0.1 INYECCIÓN DE CSS PARA EL DISEÑO DE LA IMAGEN
# ==========================================
st.markdown("""
    <style>
    /* 1. ANIMACIÓN DE ENTRADA Y FUENTES GLOABLES */
    @keyframes fadeIn {
        0% { opacity: 0; transform: translateY(20px); }
        100% { opacity: 1; transform: translateY(0); }
    }
    
    .main .block-container {
        animation: fadeIn 0.8s ease-out;
    }

    /* 2. ESTILO DEL TÍTULO PRINCIPAL Y SUBTÍTULO CON GRADIENTE AZUL-VERDE */
    .title-text {
        font-size: 3.5rem;
        font-weight: 800;
        margin-bottom: 0px;
        padding-bottom: 0px;
        color: white; /* Color de base blanco */
    }
    .title-text span {
        background: linear-gradient(90deg, #00b49c, #86e819); /* Gradiente cian a lima */
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .subtitle-text {
        color: #cbd5e1; /* Gris suave */
        font-size: 1.2rem;
        margin-bottom: 2rem;
    }

    /* 3. ESTILO DE LAS TARJETAS DE MÉTRICAS (Efecto SaaS de Image 1) */
    div[data-testid="stMetric"] {
        background-color: #0a2a41; /* Slightly lighter navy para tarjetas */
        border: 1px solid #1f2937;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        transition: all 0.3s ease;
    }
    
    div[data-testid="stMetric"]:hover {
        transform: translateY(-5px);
        border-color: #00b49c; /* Borde cian al pasar el cursor */
        box-shadow: 0 10px 15px -3px rgba(0, 180, 156, 0.2); /* Brillo cian */
    }

    /* Etiquetas de las métricas */
    div[data-testid="stMetricLabel"] > div > div > p {
        color: #cbd5e1; /* Soft gray-blue para etiquetas */
        font-weight: 600;
        font-size: 1.1rem;
    }

    /* Valores principales de las métricas */
    div[data-testid="stMetricValue"] > div {
        color: #ffffff; /* Valor métrico blanco */
        font-weight: 700;
    }

    /* 4. ESTILO DEL BOTÓN PRINCIPAL CON GRADIENTE */
    /* Target específico del botón en la sidebar */
    [data-testid="stSidebar"] button[kind="primary"] {
        background: linear-gradient(90deg, #00b49c, #86e819);
        color: #ffffff;
        border: none;
        font-weight: 700;
        use_container_width: True;
    }
    [data-testid="stSidebar"] button[kind="primary"]:hover {
        opacity: 0.9;
        transform: scale(1.02);
    }

    /* 5. ESTILO GENERAL DE SUBENCABEZADOS (H2, H3) CON GRADIENTE */
    /* Clases para subheaders en markdown */
    .section-header {
        background: linear-gradient(90deg, #00b49c, #86e819);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 700;
    }

    /* 6. ESTILO DE LOS SLIDERS NATIVOS (Sincronizado con primaryColor) */
    /* Streamlit lo maneja con primaryColor en config.toml, pero para asegurar: */
    div[data-baseweb="slider"] > div > div > div:nth-child(1) {
        background: linear-gradient(90deg, #00b49c, #86e819) !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Reemplazo de títulos y subheaders por markdown con clases CSS para el gradiente
st.markdown('<h1 class="title-text">⚙️ Simulación Interactiva: <span>Separación de Etanol</span></h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle-text">Plataforma web para el análisis termodinámico, balances y evaluación económica del proceso.</p>', unsafe_allow_html=True)

# ==========================================
# 1. SIDEBAR: PARÁMETROS OPERATIVOS Y COSTOS
# ==========================================
# Usamos Markdown para subheaders en sidebar también
st.sidebar.markdown('<h3 class="section-header">⚙️ Ejecución</h3>', unsafe_allow_html=True)
ejecutar_btn = st.sidebar.button("▶ Ejecutar Simulación", type="primary", use_container_width=True)
st.sidebar.divider()

st.sidebar.header("1. Parámetros de Operación")
flujo_agua = st.sidebar.slider("Flujo de Agua en Mosto (kmol/h)", 10.0, 100.0, 43.2, step=0.1)
flujo_etanol = st.sidebar.slider("Flujo de Etanol en Mosto (kmol/h)", 1.0, 20.0, 4.9, step=0.1)

# Temperaturas en °C
temp_mosto_c = st.sidebar.slider("Temp. Alimentación Mosto (°C)", 5.0, 50.0, 20.0, step=1.0)
temp_w220_c = st.sidebar.slider("Temp. Salida W-220 (°C)", 70.0, 110.0, 95.0, step=1.0)

# Presión en bar
presion_v100_bar = st.sidebar.slider("Presión Separador V-100 (bar)", 0.5, 5.0, 1.0, step=0.1)

st.sidebar.divider()
st.sidebar.header("2. Precios y Utilidades (USD)")
precio_mosto = st.sidebar.slider("Precio Mosto ($/ton)", 10.0, 100.0, 30.0)
precio_etanol = st.sidebar.slider("Precio Etanol ($/ton)", 500.0, 2000.0, 900.0)
precio_luz = st.sidebar.slider("Precio Luz ($/kWh)", 0.05, 0.50, 0.12)
precio_vapor = st.sidebar.slider("Precio Vapor ($/ton)", 10.0, 50.0, 20.0)
precio_agua = st.sidebar.slider("Precio Agua Enfriamiento ($/ton)", 0.1, 5.0, 0.5)

# ==========================================
# 2. FUNCIONES AUXILIARES (PDF VIEWER Y SVG)
# ==========================================
def mostrar_pdf(ruta_archivo):
    """Función auxiliar para rasterizar un PDF a imagen usando PyMuPDF y asegurar su visualización"""
    try:
        if os.path.exists(ruta_archivo):
            # Abrir el documento PDF
            doc = fitz.open(ruta_archivo)
            
            # Renderizar cada página del PDF como una imagen
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # Matriz para aplicar zoom y mejorar la resolución
                mat = fitz.Matrix(2, 2) 
                pix = page.get_pixmap(matrix=mat)
                
                # Convertir los datos de la imagen a formato apto para Streamlit
                img_bytes = pix.tobytes("png")
                st.image(img_bytes, caption=f"Página {page_num + 1} - Renderizado desde Plant 3D", use_container_width=True)
            
            # Mantener el botón de descarga nativo como contingencia
            with open(ruta_archivo, "rb") as f:
                pdf_data = f.read()
                
            st.download_button(
                label="⬇️ Descargar archivo original en PDF",
                data=pdf_data,
                file_name=ruta_archivo,
                mime="application/pdf",
                key=f"btn_{ruta_archivo}"
            )
        else:
            st.warning(f"⚠️ No se encontró el archivo: `{ruta_archivo}`. Asegúrate de subirlo a la raíz de tu repositorio.")
    except Exception as e:
        st.error(f"❌ Error interno al renderizar el documento: {e}")

def render_diagrama_interactivo(df_mat):
    """Genera e inyecta el SVG interactivo dinámico mapeado a los resultados de BioSTEAM"""
    
    # Diccionario de búsqueda rápida de las corrientes
    datos_corrientes = {}
    for _, row in df_mat.iterrows():
        id_c = str(row['ID Corriente'])
        info = f"T: {row['Temp (°C)']} °C | P: {row['Presión (bar)']} bar | Flujo: {row['Flujo (kg/h)']} kg/h\nComposición -> Etanol: {row['% Etanol']} / Agua: {row['% Agua']}"
        datos_corrientes[id_c] = info

    def safe_get(key_id, default="Datos no disponibles para esta corriente en la simulación actual"):
        return datos_corrientes.get(key_id, default)

    svg_code = f"""
    <html>
    <head>
      <style>
        body {{ background-color: #0e1117; margin: 0; padding: 0; font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; }}
        svg {{ max-width: 100%; height: auto; }}
        .equipment {{ fill: #1f2937; stroke: #00b49c; stroke-width: 2; transition: all 0.2s ease; cursor: pointer; }}
        .equipment:hover {{ fill: #00b49c; stroke: #86e819; stroke-width: 3; }}
        .stream {{ fill: none; stroke: #86e819; stroke-width: 3; transition: stroke 0.2s ease, stroke-width 0.2s ease; cursor: pointer; }}
        .stream:hover {{ stroke: #00b49c; stroke-width: 5; }}
        .label {{ font-size: 14px; fill: #cbd5e1; font-weight: bold; pointer-events: none; }}
        .stream-label {{ font-size: 12px; fill: white; font-weight: bold; pointer-events: none; background: black; }}
      </style>
    </head>
    <body>
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 600" width="100%" height="100%">
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#86e819" />
          </marker>
        </defs>

        <g id="streams">
          <g class="stream-group">
              <path class="stream" d="M 50 300 L 130 300" marker-end="url(#arrow)"/>
              <title>Corriente 1 (Alimentación Mosto)&#10;{safe_get('1-MOSTO')}</title>
          </g>
          <text x="70" y="290" class="stream-label">1</text>

          <g class="stream-group">
              <path class="stream" d="M 170 300 L 250 300" marker-end="url(#arrow)"/>
              <title>Corriente 2 (Descarga Bomba)&#10;{safe_get('s2', 'Revisar ID salida de bomba en simulación')}</title>
          </g>
          <text x="200" y="290" class="stream-label">2</text>

          <g class="stream-group">
              <path class="stream" d="M 310 300 L 380 300" marker-end="url(#arrow)"/>
              <title>Corriente 3 (Mosto Precalentado)&#10;{safe_get('3-MOSTO-PRE')}</title>
          </g>
          <text x="340" y="290" class="stream-label">3</text>

          <g class="stream-group">
              <path class="stream" d="M 440 300 L 510 300" marker-end="url(#arrow)"/>
              <title>Corriente 5 (Mosto Caliente)&#10;{safe_get('Mezcla')}</title>
          </g>
          <text x="470" y="290" class="stream-label">5</text>

          <g class="stream-group">
              <path class="stream" d="M 550 300 L 630 300" marker-end="url(#arrow)"/>
              <title>Corriente 6 (Mezcla a Flash)&#10;{safe_get('Mezcla-Bifásica')}</title>
          </g>
          <text x="580" y="290" class="stream-label">6</text>

          <g class="stream-group">
              <path class="stream" d="M 660 210 L 660 150 L 730 150" marker-end="url(#arrow)"/>
              <title>Corriente 7 (Vapor Destilado)&#10;{safe_get('Vapor Caliente')}</title>
          </g>
          <text x="670" y="170" class="stream-label">7</text>

          <g class="stream-group">
              <path class="stream" d="M 790 150 L 860 150" marker-end="url(#arrow)"/>
              <title>Corriente 9 (Producto Condensado)&#10;{safe_get('Producto Final')}</title>
          </g>
          <text x="820" y="140" class="stream-label">9</text>

          <g class="stream-group">
              <path class="stream" d="M 660 390 L 660 440" marker-end="url(#arrow)"/>
              <title>Corriente 8 (Vinazas de Flash)&#10;{safe_get('Vinazas')}</title>
          </g>
          <text x="670" y="420" class="stream-label">8</text>

          <g class="stream-group">
              <path class="stream" d="M 680 460 L 760 460 L 760 520 L 360 520 L 360 330" marker-end="url(#arrow)"/>
              <title>Corriente 10 (Vinazas Retorno)&#10;{safe_get('Vinazas-Retorno')}</title>
          </g>
          <text x="710" y="450" class="stream-label">10</text>

          <g class="stream-group">
              <path class="stream" d="M 660 480 L 660 520 L 580 520" marker-end="url(#arrow)"/>
              <title>Corriente 4 (Drenaje de Enfriamiento)&#10;{safe_get('DRENAJE')}</title>
          </g>
          <text x="610" y="510" class="stream-label">4</text>
        </g>

        <g id="P-100">
          <circle cx="150" cy="300" r="20" class="equipment" />
          <polygon points="140,290 140,310 160,300" fill="#0e1117" />
          <text x="135" y="335" class="label">P-100</text>
          <title>Bomba Centrífuga P-100</title>
        </g>

        <g id="W-210">
          <circle cx="280" cy="300" r="30" class="equipment" />
          <path d="M 250 300 L 265 285 L 280 315 L 295 285 L 310 300" stroke="#00b49c" stroke-width="2" fill="none" />
          <text x="260" y="345" class="label">W-210</text>
          <title>Intercambiador de Calor Recuperativo W-210</title>
        </g>

        <g id="W-220">
          <circle cx="410" cy="300" r="30" class="equipment" />
          <path d="M 380 300 L 395 285 L 410 315 L 425 285 L 440 300" stroke="#00b49c" stroke-width="2" fill="none" />
          <text x="390" y="345" class="label">W-220</text>
          <title>Intercambiador de Calor Utilidad W-220</title>
        </g>

        <g id="CV-411">
          <polygon points="510,285 510,315 550,285 550,315" class="equipment" />
          <text x="495" y="335" class="label">400-CV-411</text>
          <title>Válvula Isentálpica 400-CV-411 (V-100)</title>
        </g>

        <g id="V-001">
          <rect x="630" y="210" width="60" height="180" rx="30" class="equipment" />
          <text x="640" y="250" class="label">V-001</text>
          <title>Tanque Flash V-001 (V-1)</title>
        </g>

        <g id="W-310">
          <circle cx="760" cy="150" r="30" class="equipment" />
          <path d="M 730 150 L 745 135 L 760 165 L 775 135 L 790 150" stroke="#00b49c" stroke-width="2" fill="none" />
          <text x="740" y="195" class="label">W-310</text>
          <title>Condensador W-310</title>
        </g>

        <g id="P-200">
          <circle cx="660" cy="460" r="20" class="equipment" />
          <polygon points="650,450 650,470 670,460" fill="#0e1117" />
          <text x="645" y="495" class="label">P-200</text>
          <title>Bomba Centrífuga P-200</title>
        </g>
      </svg>
    </body>
    </html>
    """
    components.html(svg_code, height=650)

# ==========================================
# 3. MOTOR DE SIMULACIÓN Y ECONOMÍA
# ==========================================
def ejecutar_simulacion(f_agua, f_etanol, t_mosto_c, t_w220_c, p_v100_bar):
    bst.main_flowsheet.clear()
    chemicals = tmo.Chemicals(["Water", "Ethanol"])
    bst.settings.set_thermo(chemicals)

    # Corrientes (Conversión de °C a K, y bar a Pa)
    mosto = bst.Stream("1-MOSTO", Water=f_agua, Ethanol=f_etanol, units="kmol/h", T=t_mosto_c+273.15, P=101325)
    vinazas_retorno = bst.Stream("Vinazas-Retorno", Water=43.335, Ethanol=0, units="kmol/h", T=90+273.15, P=300000)

    # Equipos
    P100 = bst.Pump("P-100", ins=mosto, P=4*101325)
    W210 = bst.HXprocess("W-210", ins=(P100-0, vinazas_retorno), outs=("3-MOSTO-PRE","DRENAJE"), phase0="l", phase1="l")
    W210.outs[0].T = 85+273.15
    W220 = bst.HXutility("W-220", ins=W210-0, outs="Mezcla", T=t_w220_c+273.15)
    V100 = bst.IsenthalpicValve("V-100", ins=W220-0, outs="Mezcla-Bifásica", P=p_v100_bar*100000)
    
    V1 = bst.Flash("V-1", ins=V100-0, outs=("Vapor Caliente","Vinazas"), P=p_v100_bar*100000, Q=0)
    
    # Condensador (enfriamiento riguroso a 293 K por requerimiento de transferencia de masa)
    W310 = bst.HXutility("W-310", ins=V1-0, outs="Producto Final", T=293.0)
    
    P200 = bst.Pump("P-200", ins=V1-1, outs=vinazas_retorno, P=3*101325)

    eth_sys = bst.System("planta_etanol", path=(P100,W210,W220,V100,V1,W310,P200))
    eth_sys.simulate()

    # Procesamiento Materia
    datos_mat = []
    prod_data = {}
    for s in eth_sys.streams:
        if s.F_mass > 0:
            pct_etanol = (s.imass['Ethanol']/s.F_mass)*100
            if s.ID == "Producto Final":
                prod_data = {
                    "P": s.P / 100000, # bar
                    "T": s.T - 273.15, # °C
                    "Flujo": s.F_mass, # kg/h
                    "Comp": pct_etanol # %
                }
            datos_mat.append({
                "ID Corriente": s.ID, "Temp (°C)": f"{s.T-273.15:.2f}",
                "Presión (bar)": f"{s.P/100000:.2f}", "Flujo (kg/h)": f"{s.F_mass:.2f}",
                "% Etanol": f"{pct_etanol:.1f}%", "% Agua": f"{(s.imass['Water']/s.F_mass)*100:.1f}%"
            })
    
    # Procesamiento Energía y Utilidades
    datos_en = []
    calor_kw = enfriamiento_kw = potencia_kw = 0.0
    
    for u in eth_sys.units:
        q_kw = (u.duty / 3600) if (hasattr(u, "duty") and u.duty) else 0.0
        p_kw = u.power_utility.rate if (hasattr(u, "power_utility") and u.power_utility) else 0.0
        
        tipo_srv = "-"
        if isinstance(u, bst.HXprocess): tipo_srv = "Recuperación"
        elif isinstance(u, bst.Flash): tipo_srv = "Adiabático"
        elif q_kw > 0.01: 
            tipo_srv = "Vapor"
            calor_kw += q_kw
        elif q_kw < -0.01: 
            tipo_srv = "Agua Enfriamiento"
            enfriamiento_kw += abs(q_kw)
            
        potencia_kw += p_kw

        if abs(q_kw) > 0.01: datos_en.append({"ID Equipo": u.ID, "Función": tipo_srv, "Energía Térmica (kW)": f"{q_kw:.2f}"})
        if p_kw > 0.01: datos_en.append({"ID Equipo": u.ID, "Función": "Motor Eléctrico", "Energía Eléctrica (kW)": f"{p_kw:.2f}"})

    # --- EVALUACIÓN ECONÓMICA BÁSICA (Clase V) ---
    horas_año = 8000
    ton_to_kg = 1000
    
    # OPEX Anual (Materia prima + Servicios)
    costo_mosto_anual = (mosto.F_mass / ton_to_kg) * precio_mosto * horas_año
    costo_vapor_anual = (calor_kw * 3600 / 2257 / ton_to_kg) * precio_vapor * horas_año # Asumiendo dHvap = 2257 kJ/kg
    costo_agua_anual = (enfriamiento_kw * 3600 / 41.8 / ton_to_kg) * precio_agua * horas_año # Asumiendo dT = 10C
    costo_luz_anual = potencia_kw * precio_luz * horas_año
    opex_total = costo_mosto_anual + costo_vapor_anual + costo_agua_anual + costo_luz_anual
    
    costo_real_produccion = opex_total / (prod_data["Flujo"] * horas_año / ton_to_kg) if prod_data["Flujo"] > 0 else 0
    
    # Ingresos y Métricas Financieras
    ingresos = (prod_data["Flujo"] / ton_to_kg) * precio_etanol * horas_año
    flujo_caja = ingresos - opex_total
    
    # Asumimos un CAPEX estimado fijo de $1,500,000 USD para el cálculo de viabilidad
    capex_estimado = 1500000 
    roi = (flujo_caja / capex_estimado) * 100 if capex_estimado > 0 else 0
    payback = capex_estimado / flujo_caja if flujo_caja > 0 else 0
    
    # NPV a 10 años con tasa de descuento del 10%
    tasa = 0.10
    npv = -capex_estimado + sum([flujo_caja / ((1 + tasa)**t) for t in range(1, 11)])

    kpis = {
        "prod": prod_data,
        "costo_prod": costo_real_produccion,
        "precio_venta": precio_etanol,
        "npv": npv,
        "payback": payback,
        "roi": roi
    }

    return pd.DataFrame(datos_mat), pd.DataFrame(datos_en), kpis

# ==========================================
# 4. INTERFAZ Y RENDERIZADO
# ==========================================
if ejecutar_btn:
    with st.spinner("Resolviendo balances termodinámicos y financieros..."):
        st.session_state['simulacion_ejecutada'] = True
        df_materia, df_energia, kpis = ejecutar_simulacion(
            flujo_agua, flujo_etanol, temp_mosto_c, temp_w220_c, presion_v100_bar
        )
        st.session_state['df_mat'] = df_materia
        st.session_state['df_en'] = df_energia
        st.session_state['kpis'] = kpis

if st.session_state.get('simulacion_ejecutada'):
    kpis = st.session_state['kpis']
    
    # --- SECCIÓN A: MÉTRICAS DEL PRODUCTO FINAL ---
    st.markdown('<h3 class="section-header">📦 Propiedades del Producto Final</h3>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Presión", f"{kpis['prod'].get('P', 0):.2f} bar")
    c2.metric("Temperatura", f"{kpis['prod'].get('T', 0):.2f} °C")
    c3.metric("Flujo Másico", f"{kpis['prod'].get('Flujo', 0):.1f} kg/h")
    c4.metric("Composición Etanol", f"{kpis['prod'].get('Comp', 0):.1f} %")

    # --- SECCIÓN B: EVALUACIÓN ECONÓMICA MODIFICADA ---
    st.markdown('<h3 class="section-header">💰 Evaluación Financiera (Base Anual)</h3>', unsafe_allow_html=True)
    
    e1, e2, e3 = st.columns(3)
    e1.metric("Costo Real Prod.", f"$ {kpis['costo_prod']:.2f} /ton")
    e2.metric("Precio Venta Sug.", f"$ {kpis['precio_venta']:.2f} /ton")
    e3.metric("NPV (10 años)", f"$ {kpis['npv']:,.0f}")
    
    e4, e5 = st.columns(2)
    e4.metric("Payback", f"{kpis['payback']:.1f} años" if kpis['payback']>0 else "No viable")
    e5.metric("ROI", f"{kpis['roi']:.1f} %")

    st.divider()

    # --- SECCIÓN C: TABLAS DE BALANCE ---
    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown('<h3 class="section-header">💧 Balance de Materia</h3>', unsafe_allow_html=True)
        st.dataframe(st.session_state['df_mat'], use_container_width=True, hide_index=True)
    with col2:
        st.markdown('<h3 class="section-header">⚡ Balance de Energía</h1>', unsafe_allow_html=True)
        st.dataframe(st.session_state['df_en'], use_container_width=True, hide_index=True)
        
    st.divider()

    # --- SECCIÓN D: VISUALIZACIÓN DE PLANOS ISO ---
    st.markdown('<h3 class="section-header">📐 Diagramas de Ingeniería (Estándar ISO)</h3>', unsafe_allow_html=True)
    
    # SE AÑADE LA PESTAÑA DEL PFD INTERACTIVO
    t1, t2, t3 = st.tabs(["Diagrama de Bloques (BFD)", "Diagrama de Flujo de Proceso (PFD)", "PFD Interactivo en Vivo (SVG)"])
    
    with t1:
        st.info("Renderizando BFD desde AutoCAD Plant 3D")
        mostrar_pdf("diagrama_bfd.pdf")
        
    with t2:
        st.info("Renderizando PFD desde AutoCAD Plant 3D")
        mostrar_pdf("diagrama_pfd.pdf")
        
    with t3:
        st.info("Visualización paramétrica interactiva sobre esquemático SVG. Posicione el cursor sobre los equipos o corrientes.")
        render_diagrama_interactivo(st.session_state['df_mat'])

    st.divider()

    # --- SECCIÓN E: TUTOR IA (GEMINI 2.5 PRO) ---
    st.markdown('<h3 class="section-header">🧠 Tutor de Ingeniería Asistido por IA</h3>', unsafe_allow_html=True)
    modo_tutor = st.toggle("Habilitar Modo Tutor IA", value=False)
    
    if modo_tutor:
        st.markdown("Chatea con el asistente técnico sobre los resultados termodinámicos y financieros de tu simulación.")
        
        if "messages" not in st.session_state:
            st.session_state.messages = []

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt_usuario := st.chat_input("Ej: ¿Por qué el ROI es tan bajo si aumento la presión en V-100?"):
            st.session_state.messages.append({"role": "user", "content": prompt_usuario})
            with st.chat_message("user"):
                st.markdown(prompt_usuario)

            contexto_simulacion = f"""
            Actúa como un tutor de ingeniería química senior. El alumno está simulando una planta de separación de etanol.
            Datos actuales de la simulación:
            - Temperatura W-220: {temp_w220_c} °C
            - Presión V-100: {presion_v100_bar} bar
            - Pureza del producto: {kpis['prod'].get('Comp', 0):.1f} %
            - NPV: ${kpis['npv']:,.2f} USD
            - ROI: {kpis['roi']:.1f} %
            
            Pregunta del alumno: {prompt_usuario}
            
            Responde de manera directa, técnica y basándote en la termodinámica o ingeniería de costos.
            """

            try:
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                modelo = genai.GenerativeModel("gemini-2.5-pro")
                
                with st.chat_message("assistant"):
                    with st.spinner("Analizando balances..."):
                        respuesta = modelo.generate_content(contexto_simulacion)
                        st.markdown(respuesta.text)
                
                st.session_state.messages.append({"role": "assistant", "content": respuesta.text})
                
            except Exception as e:
                st.error("Fallo de conexión con Gemini.")
                st.code(str(e))
else:
    # Mensaje de espera en estado inicial
    st.info("👈 Ajusta los parámetros operativos y de costos en el panel lateral, luego presiona **Ejecutar Simulación** para visualizar los balances y la evaluación económica.")
