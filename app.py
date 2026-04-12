import streamlit as st
import biosteam as bst
import thermosteam as tmo
import pandas as pd
import os
import base64
import google.generativeai as genai

# ==========================================
# 0. CONFIGURACIÓN DE LA PÁGINA
# ==========================================
st.set_page_config(
    page_title="Simulador BioSTEAM - Separación de Etanol", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("⚙️ Simulación Interactiva: Separación de Etanol")
st.markdown("Plataforma web para el análisis termodinámico, balances y evaluación económica del proceso.")

# ==========================================
# 1. SIDEBAR: PARÁMETROS OPERATIVOS Y COSTOS
# ==========================================
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
# 2. FUNCIONES AUXILIARES (PDF VIEWER)
# ==========================================
def mostrar_pdf(ruta_archivo):
    if os.path.exists(ruta_archivo):
        with open(ruta_archivo, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode('utf-8')
