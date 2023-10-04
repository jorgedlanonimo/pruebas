import pandas as pd
import re
import plotly.graph_objects as go
import streamlit as st
import plotly.express as px
import os


def filter_data(df):
    df = df[df["Team Name"] == 'Villarreal B']
    return df

def extract_match_day_value(df):
    def extract_number(cadena):
        resultado = re.search(r'([-+]?\d+)\s+MD', cadena)
        if resultado:
            return int(resultado.group(1))
        return None
    
    df["Match Day"] = df["Match Day"].astype(str)
    df["Match Day Value"] = df["Match Day"].apply(extract_number)
    df.loc[~df["Match Day Value"].isin([-5, -4, -3, -2, -1, 1, 2, 3, 4, 5]), "Match Day Value"] = 0
    df = df.replace('None', 0)
    df['Date - Session Date'] = pd.to_datetime(df['Date - Session Date'], dayfirst=True)
    return df

def quedarnos_con_drills(df):
    
    indices_a_eliminar = df.groupby([ 'Date - Session Date', 'Player Full Name (P)'])['Distance - Distance (m)'].idxmax()
    df = df.drop(indices_a_eliminar)
    indices_maximos = df.groupby(['Date - Session Date', 'Player Full Name (P)'])['Distance - Distance (m)'].idxmax()
    df= df.loc[indices_maximos]
    return df

def cargar_columnas(df):
    columnas = df.select_dtypes(include=['float64']).columns.tolist()
    columnas = [columna for columna in columnas if not columna.startswith('Week') and columna != 'Match Day Value']
    return columnas

def parametros_funciones_agregacion():
    return ["min", "max", "mean","std", "quantile"]

def sacar_estadisticas(df):
    columnas = cargar_columnas(df)
    # Definir las funciones de agregación
    funciones_agregacion = parametros_funciones_agregacion()

    # Aplicar las transformaciones por grupo
    for columna in columnas:
        for funcion in funciones_agregacion:
            nombre_columna_nueva = f"{columna}_{funcion}"
            if funcion == "quantile":
                df[nombre_columna_nueva] = df.groupby(["Match Day Value", "Player Full Name (P)"])[columna].transform(lambda x: x.quantile(0.15))
            else:
                df[nombre_columna_nueva] = df.groupby(["Match Day Value", "Player Full Name (P)"])[columna].transform(funcion)

    
        col_indicador = columna + '_indicador'
        #df[col_indicador] = 0  # Inicializa todas las columnas a 0 por defecto
        print(columna)

        for index, row in df.iterrows():
            valor = row[columna] 
            maximo = row[f'{columna}_max']
            minimo = row[f'{columna}_min']
            percentil_15 = row[f'{columna}_quantile']
            media = row[f'{columna}_mean']
            desviacion_tipica = row[f'{columna}_std']

            if(desviacion_tipica):

                if valor > maximo:
                    df.at[index, col_indicador] = 3
                elif maximo >= valor > (media + 2 * desviacion_tipica):
                    df.at[index, col_indicador] = 2
                elif (media +  2 * desviacion_tipica) >= valor > percentil_15:
                    df.at[index, col_indicador] = 1
                elif valor <= percentil_15:
                    df.at[index, col_indicador] = -1

    columnas_indicadores = [columna + '_indicador' for columna in columnas]
    df['sum_fatiga'] = df[columnas_indicadores].sum(axis=1)

    for funcion in funciones_agregacion:
        nombre_columna_nueva = f"sum_fatiga_{funcion}"
        if funcion == "quantile":
            df[nombre_columna_nueva] = df.groupby(["Match Day Value", "Player Full Name (P)"])['sum_fatiga'].transform(lambda x: x.quantile(0.15))
        else:
            df[nombre_columna_nueva] = df.groupby(["Match Day Value", "Player Full Name (P)"])['sum_fatiga'].transform(funcion)
    df = df.sort_values('Date - Session Date', ascending=False)

    return df

def uploaded_file():

    # Si no se pudo abrir el archivo por defecto, mostrar el widget de subida de archivos
    file = st.file_uploader("Elige un archivo Excel", type=["xlsx", "xls"])
    if file is not None:
        return file

def cargar_file(file):
    return pd.read_excel(file)

@st.cache_resource
def cargar_datos(file):
    df = cargar_file(file)
    df = filter_data(df)
    df = extract_match_day_value(df)
    df = quedarnos_con_drills(df)
    df = sacar_estadisticas(df)
    return df

@st.cache_resource
def cargar_nombres_jugador(df):
    nombres_jugadores = df['Player Full Name (P)'].unique()
    return nombres_jugadores

def grafico_fatiga_individual(df, nombre_jugador_seleccionado,num_dias):
    df_filtrado = df[df['Player Full Name (P)'] == nombre_jugador_seleccionado].head(num_dias)
    fig = go.Figure()
    valores_mas=[]
    valores_menos=[]
    for i in df_filtrado['Match Day Value']:
        valores_mas.append(df_filtrado[(df_filtrado['Match Day Value'] == i) & (df_filtrado['Player Full Name (P)'] == 'Íker Álvarez')]['sum_fatiga_mean'].iloc[0] +
                        df_filtrado[(df_filtrado['Match Day Value'] == i) & (df_filtrado['Player Full Name (P)'] == 'Íker Álvarez')]['sum_fatiga_std'].iloc[0])
        valores_menos.append(df_filtrado[(df_filtrado['Match Day Value'] == i) & (df_filtrado['Player Full Name (P)'] == 'Íker Álvarez')]['sum_fatiga_mean'].iloc[0] -
                        df_filtrado[(df_filtrado['Match Day Value'] == i) & (df_filtrado['Player Full Name (P)'] == 'Íker Álvarez')]['sum_fatiga_std'].iloc[0])


        # Identificamos los puntos que se salgan del rango sombreado
    outside_upper = df_filtrado['sum_fatiga'] > valores_mas
    outside_lower = df_filtrado['sum_fatiga'] < valores_menos

    # Añadimos la línea principal (sum_fatiga)
    fig.add_trace(go.Scatter(x=df_filtrado['Date - Session Date'], y=df_filtrado['sum_fatiga'], mode='lines', name='Nivel de Fatiga'))

    # Añadimos las áreas sombreadas para la desviación estándar
    fig.add_trace(go.Scatter(x=df_filtrado['Date - Session Date'], y=valores_mas, fill=None, mode='lines', line=dict(color='gray'), name='Media + Desviación Estándar'))
    fig.add_trace(go.Scatter(x=df_filtrado['Date - Session Date'], y=valores_menos, fill='tonexty', mode='lines', line=dict(color='gray'), name='Media - Desviación Estándar'))

    # Añadimos marcadores para los puntos que se salen del rango
    fig.add_trace(go.Scatter(x=df_filtrado[outside_upper | outside_lower]['Date - Session Date'], y=df_filtrado[outside_upper | outside_lower]['sum_fatiga'], mode='markers', marker=dict(color='red', size=8), name='Fuera de Rango'))

    # Configuración adicional del gráfico
    fig.update_layout(xaxis_title='Fecha', yaxis_title='Nivel de Fatiga', legend_title='Jugador', hovermode='x unified', title='Nivel de Fatiga de los Jugadores')

    return fig

def main():
    st.title('Control de la Carga')
    
    file = uploaded_file()
    
    if file is not None:
        df = cargar_datos(file)
        nombres_jugadores = cargar_nombres_jugador(df)
        nombre_jugador_seleccionado = st.selectbox("Selecciona un jugador:", nombres_jugadores)
        selected_number = st.slider('Selecciona un número:', min_value=0, max_value=90, value=8)
        
        st.plotly_chart(grafico_fatiga_individual(df, nombre_jugador_seleccionado,selected_number))
    else:
        st.text('No se han cargado los datos')

if __name__ == '__main__':
    main()
