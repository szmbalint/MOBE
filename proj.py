import pandas as pd
import geopandas as gpd
import plotly.express as px
import dash
from dash import dcc, html, ctx
from dash.dependencies import Input, Output, State

# --- 0. SEGÉDFÜGGVÉNYEK ---
def clearJSONfromCities(gdf_geo):
    gdf_geo['name'] = gdf_geo['name'].str.strip()
    city_to_county_map = {
        'Szeged': 'Csongrád', 'Hódmezővásárhely': 'Csongrád', 'Pécs': 'Baranya',
        'Győr': 'Győr-Moson-Sopron', 'Sopron': 'Győr-Moson-Sopron', 'Debrecen': 'Hajdú-Bihar',
        'Eger': 'Heves', 'Szolnok': 'Jász-Nagykun-Szolnok', 'Tatabánya': 'Komárom-Esztergom',
        'Salgótarján': 'Nógrád', 'Érd': 'Pest', 'Budapest': 'Pest', 'Kaposvár': 'Somogy',
        'Nyíregyháza': 'Szabolcs-Szatmár-Bereg', 'Szekszárd': 'Tolna', 'Szombathely': 'Vas',
        'Veszprém': 'Veszprém', 'Zalaegerszeg': 'Zala', 'Nagykanizsa': 'Zala',
        'Székesfehérvár': 'Fejér', 'Dunaújváros': 'Fejér', 'Kecskemét': 'Bács-Kiskun',
        'Békéscsaba': 'Békés', 'Miskolc': 'Borsod-Abaúj-Zemplén'
    }
    
    gdf_geo['Dissolve_Name'] = gdf_geo['name']
    gdf_geo['Dissolve_Name'] = gdf_geo['name'].replace(city_to_county_map)
    gdf_geo['Dissolve_Name'] = gdf_geo['Dissolve_Name'].replace('Csongrád-Csanád', 'Csongrád')

    gdf_geo_fixed = gdf_geo.dissolve(by='Dissolve_Name', as_index=False)
    if 'name' in gdf_geo_fixed.columns:
        gdf_geo_fixed = gdf_geo_fixed.drop(columns=['name'])

    gdf_geo_fixed = gdf_geo_fixed.rename(columns={'Dissolve_Name': 'name'})
    return gdf_geo_fixed

# --- 1. ADATOK BETÖLTÉSE ---
try:
    gdf_geo = gpd.read_file("hungaryJSON.json")
except FileNotFoundError:
    print("HIBA: A 'hungaryJSON.json' fájl nem található.")
    exit()

gdf_geo = clearJSONfromCities(gdf_geo)

try:
    # 1. Fő adatbázis (Összesített számok + Népesség)
    df_data = pd.read_csv("buncs_nep_adatb.csv") 
    
    # 2. Országos típusok (Opcionális, de a biztonság kedvéért bent hagyjuk)
    df_kategoriak = pd.read_csv("adatbazis_2_osszesitett_kategoriak.csv")
    
    # 3. ÚJ: Részletes megyei típus adatbázis
    df_tipusok_reszletes = pd.read_csv("adatbazis_3_megyei_tipusok.csv")

except FileNotFoundError:
    print("HIBA: Valamelyik CSV fájl nem található (ellenőrizd az adatbazis_3... fájlt is!).")
    exit()

# Adatok tisztítása
df_data['Megye_Neve'] = df_data['Megye_Neve'].str.strip()
df_tipusok_reszletes['Megye_Neve'] = df_tipusok_reszletes['Megye_Neve'].str.strip()

# Biztonsági Index számítása
df_data['Biztonsagi_Index'] = (
    df_data['Regisztrált Bűncselekmények Száma'] / df_data['Népesség száma'].replace(0, pd.NA)
) * 1000

# Térkép és Adat egyesítése
master_gdf = gdf_geo.merge(
    df_data,
    left_on='name',           
    right_on='Megye_Neve'       
)

# --- 2. DASH APP LAYOUT ---
app = dash.Dash(__name__)
server = app.server

app.layout = html.Div([
    html.H1("Magyarország Bűnügyi Elemző (2009-2024)", 
            style={'textAlign': 'center', 'fontFamily': 'Arial', 'color': '#333'}),

    # --- VEZÉRLŐPULT (RANGE SLIDER) ---
    html.Div([
        html.Label("Vizsgált Időszak (Intervallum):", style={'fontSize': '18px', 'fontWeight': 'bold'}),
        
        dcc.RangeSlider(
            id='year-slider',
            min=master_gdf['Év'].min(),
            max=master_gdf['Év'].max(),
            value=[2015, 2024],
            marks={str(year): str(year) for year in master_gdf['Év'].unique() if year % 3 == 0 or year == master_gdf['Év'].min() or year == master_gdf['Év'].max()},
            step=1,
            tooltip={"placement": "bottom", "always_visible": True}
        ),
    ], style={'padding': '20px', 'backgroundColor': '#f1f1f1', 'borderRadius': '10px', 'marginBottom': '20px'}),

    # --- FELSŐ SZEKCIÓ ---
    html.Div([
        
        # BAL OLDAL: TÉRKÉP
        html.Div([
            html.H3("Biztonsági Térkép (Átlag)", style={'textAlign': 'center'}),
            dcc.Graph(id='choropleth-map', style={'height': '65vh'})
        ], style={'width': '49%', 'display': 'inline-block', 'verticalAlign': 'top'}),

        # JOBB OLDAL: MULTI-SELECT TRENDEK
        html.Div([
            html.H3("Megyei Összesített Trendek", style={'textAlign': 'center'}),
            
            html.Label("Válassz megyéket (vagy kattints a térképre):"),
            dcc.Dropdown(
                id='county-dropdown',
                options=[{'label': i, 'value': i} for i in sorted(df_data['Megye_Neve'].unique())],
                value=['Budapest'], 
                multi=True, 
                placeholder="Válassz megyéket..."
            ),
            
            dcc.Graph(id='trend-chart', style={'height': '60vh'})
        ], style={'width': '49%', 'display': 'inline-block', 'verticalAlign': 'top', 'paddingLeft': '10px'})

    ], style={'display': 'flex', 'flexDirection': 'row', 'marginBottom': '30px'}),

    # --- ALSÓ SZEKCIÓ  ---
    html.Div([
        html.H3("Bűncselekmény Típusok Trendje (A kiválasztott megyékben)", style={'textAlign': 'center'}),
        
        dcc.Graph(id='detailed-type-trend-chart', style={'height': '600px'})
    ], style={'width': '95%', 'margin': 'auto', 'paddingTop': '20px', 'borderTop': '1px solid #ccc'})
])


# --- 3. CALLBACKS (LOGIKA) ---

# A. TÉRKÉP FRISSÍTÉSE
@app.callback(
    Output('choropleth-map', 'figure'),
    [Input('year-slider', 'value')]
)
def update_map(year_range):
    start_year, end_year = year_range
    filtered_gdf = master_gdf[(master_gdf['Év'] >= start_year) & (master_gdf['Év'] <= end_year)].copy()
    
    cols_to_keep = ['name', 'geometry', 'Biztonsagi_Index', 'Regisztrált Bűncselekmények Száma', 'Népesség száma']
    filtered_gdf = filtered_gdf[cols_to_keep]

    aggregated_gdf = filtered_gdf.dissolve(by='name', aggfunc='mean')
    aggregated_gdf['Megye_Neve'] = aggregated_gdf.index 
    
    fig = px.choropleth(
        aggregated_gdf,
        geojson=aggregated_gdf.geometry,
        locations=aggregated_gdf.index,
        color='Biztonsagi_Index',         
        color_continuous_scale="Reds",   
        range_color=(master_gdf['Biztonsagi_Index'].min(), master_gdf['Biztonsagi_Index'].max()), 
        hover_name='Megye_Neve',         
        hover_data={
            'Regisztrált Bűncselekmények Száma': ':.0f',
            'Népesség száma': ':.0f',
            'Biztonsagi_Index': ':.2f'
        },
        title=f"Átlagos Biztonsági Index ({start_year} - {end_year})",
        projection="mercator"
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(margin={"r":0,"t":40,"l":0,"b":0}, dragmode='pan')
    return fig


# B. DROPDOWN FRISSÍTÉSE (Kattintásra)
@app.callback(
    Output('county-dropdown', 'value'),
    [Input('choropleth-map', 'clickData')],
    [State('county-dropdown', 'value')] 
)
def update_dropdown_on_click(clickData, current_selection):
    if clickData is None:
        return current_selection if current_selection else ['Budapest']
    
    clicked_county = clickData['points'][0]['hovertext']
    
    if current_selection is None:
        current_selection = []
    
    if clicked_county not in current_selection:
        updated_selection = current_selection + [clicked_county]
        return updated_selection
    
    return current_selection


# C.  (Felső grafikon - Összesített)
@app.callback(
    Output('trend-chart', 'figure'),
    [Input('county-dropdown', 'value'),
     Input('year-slider', 'value')]
)
def update_trend_chart(selected_counties, year_range):
    start_year, end_year = year_range
    if not selected_counties:
        selected_counties = ["Budapest"]

    trend_data = df_data[df_data['Megye_Neve'].isin(selected_counties)].sort_values('Év')
    
    fig = px.line(
        trend_data,
        x='Év',
        y='Regisztrált Bűncselekmények Száma',
        color='Megye_Neve', 
        title=f"Összesített bűnözés alakulása",
        markers=True
    )
    
    fig.add_vrect(
        x0=start_year, x1=end_year,
        fillcolor="LightSalmon", opacity=0.3,
        layer="below", line_width=0,
    )
    fig.update_layout(xaxis_title="Év", yaxis_title="Esetek száma", hovermode="x unified")
    return fig


# D. VÉGLEGES MEGOLDÁS: EGYETLEN GRAFIKON (Vonalstílus használata a megyékhez)
@app.callback(
    Output('detailed-type-trend-chart', 'figure'),
    [Input('county-dropdown', 'value'), 
     Input('year-slider', 'value')]
)
def update_detailed_type_chart(selected_counties, year_range):
    start_year, end_year = year_range
    
    # 1. Alapértelmezett beállítás
    if not selected_counties:
        selected_counties = ["Budapest"] 
    
    # Mivel a vonalstílusok száma korlátozott (kb. 5-6 féle), 
    # érdemes korlátozni a megjeleníthető megyék számát, különben ismétlődnek.
    display_counties = selected_counties[:5] 

    # 2. Adat szűrése
    df_filtered = df_tipusok_reszletes[df_tipusok_reszletes['Megye_Neve'].isin(display_counties)]
    
    # 3. "Összesen" sor kivétele (hogy ne nyomja el a többi adatot)
    df_filtered = df_filtered[~df_filtered['Bűncselekmény_Típus'].str.contains("összesen", case=False)]

    # 4. Rendezés az időrendhez
    df_filtered = df_filtered.sort_values(by='Év') 
    
    # 5. GRAFIKON RAJZOLÁSA (EGYETLEN CHART)
    fig = px.line(
        df_filtered,
        x='Év',
        y='Esetszám',
        color='Bűncselekmény_Típus', # A szín továbbra is a TÍPUST jelöli
        line_dash='Megye_Neve',      # A vonal stílusa (szaggatott, pontozott) a MEGYÉT jelöli
        title=f"Bűncselekmény Típusok és Megyék Összehasonlítása ({', '.join(display_counties)})",
        markers=True,
        symbol='Megye_Neve'          # Bónusz: A pontok alakja is segíti a megkülönböztetést
    )

    # 6. Időszak jelölése
    fig.add_vrect(
        x0=start_year, x1=end_year,
        fillcolor="LightSalmon", opacity=0.3,
        layer="below", line_width=0,
    )

    fig.update_layout(
        xaxis_title="Év", 
        yaxis_title="Esetek száma", 
        hovermode="x unified", # Közös buborék minden vonalhoz
        legend_title="Jelmagyarázat (Szín=Típus, Vonal=Megye)",
        height=600 # Magasabb grafikon a jobb láthatóságért
    )
    
    return fig

# --- INDÍTÁS ---
if __name__ == '__main__':
    print("indítás...")
    app.run(debug=True, host='127.0.0.1', port=8050)