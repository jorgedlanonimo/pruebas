import pandas as pd
import re
import plotly.graph_objects as go
import streamlit as st
import plotly.express as px


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
                df[nombre_columna_nueva] = df.groupby(["Match Day Value", "Position (P)"])[columna].transform(lambda x: x.quantile(0.15))
            else:
                df[nombre_columna_nueva] = df.groupby(["Match Day Value", "Position (P)"])[columna].transform(funcion)

    
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
            df[nombre_columna_nueva] = df.groupby(["Match Day Value", "Position (P)"])['sum_fatiga'].transform(lambda x: x.quantile(0.15))
        else:
            df[nombre_columna_nueva] = df.groupby(["Match Day Value", "Position (P)"])['sum_fatiga'].transform(funcion)
    df = df.sort_values('Date - Session Date', ascending=False)

    return df



@st.cache_resource()
def cargar_datos(file_path):
    df = pd.read_excel(file_path)
    df = filter_data(df)
    df = extract_match_day_value(df)
    df = quedarnos_con_drills(df)
    df = sacar_estadisticas(df)
    
    return df

# Función para obtener los nombres de los jugadores
@st.cache_resource
def cargar_nombres_jugador(df):
    nombres_jugadores = df['Player Full Name (P)'].unique()
    return nombres_jugadores

def grafico_fatiga_individual(df,nombre_jugador_seleccionado):
    df_filtrado = df[df['Player Full Name (P)'] == nombre_jugador_seleccionado].head(10)
    fig = px.line(df_filtrado, x='Date - Session Date', y='sum_fatiga', labels={'sum_fatiga': 'Nivel de Fatiga'}, title='Nivel de Fatiga de los Jugadores')
    fig.update_layout(xaxis_title='Fecha', yaxis_title='Nivel de Fatiga', legend_title='Jugador', hovermode='x unified')
    return fig
def main():
    st.title('Control de la Carga')

   
    file_path = r"C:\Users\jorge\Desktop\Villarreal CF\Control de la carga\excel-0.xlsx"
    df = cargar_datos(file_path)

    if df is not None:
        nombres_jugadores = cargar_nombres_jugador(df)
        nombre_jugador_seleccionado = st.selectbox("Selecciona un jugador:", nombres_jugadores)
        
        st.plotly_chart(grafico_fatiga_individual(df,nombre_jugador_seleccionado))
        st.plotly_chart(grafico_fatiga_individual(df,nombre_jugador_seleccionado))
    else:
        st.text('No se han cargado los datos')


if __name__ == '__main__':
    main()
