import streamlit as st

import json
import pandas as pd
import pydeck as pdk
from geopy.distance import geodesic
from datetime import datetime
import pytz
from timezonefinder import TimezoneFinder

from io import BytesIO
from fpdf import FPDF
import os


def get_zoom(min_lat, min_lon, max_lat, max_lon):
    corner1 = (min_lat, min_lon)
    corner2 = (max_lat, max_lon)
    extent_km = geodesic(corner1, corner2).km
    
    if extent_km < 1:
        zoom = 16
    elif extent_km < 5:
        zoom = 15
    elif extent_km < 10:
        zoom = 14
    elif extent_km < 20:
        zoom = 13
    elif extent_km < 50:
        zoom = 12
    elif extent_km < 100:
        zoom = 11
    else:
        zoom = 10
    
    return zoom

def generate_pdf(json_data, mission_name):
    img = []
    utc = []
    local = []

    lat = float(json_data['flights'][0]['geotag'][0]['coordinate'][0])
    lon = float(json_data['flights'][0]['geotag'][0]['coordinate'][1])
    tf = TimezoneFinder()
    tz_str = tf.timezone_at(lat=lat, lng=lon)

    idx = 2
    for entry in json_data['flights'][0]['geotag']:
        zeros = '0' * (5 - len(str(idx)))
        img.append(mission_name + '_' + zeros + str(idx) + '.JPG')

        stmp = int(entry['timestamp'].split('.')[0]) / 1000
        utc_time = datetime.utcfromtimestamp(stmp).replace(tzinfo=pytz.utc)
        local_time = utc_time.astimezone(pytz.timezone(tz_str))

        utc.append(utc_time.strftime('%Y-%m-%d %H:%M'))
        local.append(local_time.strftime('%Y-%m-%d %H:%M'))
        idx += 1

    # Create PDF
    buffer = BytesIO()
    pdf = FPDF()
    pdf.add_page()
    
    # Logo (centered)
    if os.path.exists("logo.png"):
        logo_width = 100
        logo_height = 24
        x_center = (pdf.w - logo_width) / 2
        pdf.image("logo.png", x=x_center, w=logo_width, h=logo_height)
        pdf.ln(8)
    else:
        pdf.ln(10)
        
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Data Collection Report", ln=True, align='C')

    pdf.set_font("Arial", "", 12)
    pdf.multi_cell(0, 6, "This report documents the images collected for a Wingtra flight. The corresponding capture time of each image is indicated in both UTC and local time zones.")
    pdf.ln(10)

    # Table column dimensions
    col_widths = [80, 55, 55]
    col_titles = ["IMAGE NAME", "UTC TIME", "LOCAL TIME"]

    # Draw colored background for header
    pdf.set_fill_color(232, 76, 10)  # Hex #e84c0a
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 10)
    for i, title in enumerate(col_titles):
        pdf.cell(col_widths[i], 8, title, border=1, align='C', fill=True)
    pdf.ln()

    # Reset text color for body
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", "", 9)
    for i, u, l in zip(img, utc, local):
        pdf.cell(col_widths[0], 8, i, border=1, align='C')
        pdf.cell(col_widths[1], 8, u, border=1, align='C')
        pdf.cell(col_widths[2], 8, l, border=1, align='C')
        pdf.ln()

    # Finalize PDF
    pdf_bytes = pdf.output(dest='S').encode('latin1')
    buffer.write(pdf_bytes)
    buffer.seek(0)
    return buffer


# Streamlit UI
st.set_page_config(page_title="Wingtra Timestamp Report", layout="wide")
st.title('Wingtra Data Collection Report Generator')

st.sidebar.image('./logo.png', width = 260)
st.sidebar.markdown('#')
st.sidebar.write('The application takes the JSON file in the Wingtra flight mission DATA folder as input.')
st.sidebar.write('It then extracts data from the file and generates a PDF report with image capture time information .')
st.sidebar.write('If you have any questions regarding the application, please contact us at support@wingtra.com.')
st.sidebar.markdown('#')

uploaded_file = st.file_uploader("Upload your Wingtra JSON flight file", type="json")

if uploaded_file:
    try:
        json_data = json.load(uploaded_file)
        st.success('JSON file successfully loaded.')
        
        # Generate mission name from uploaded file name
        filename = uploaded_file.name.replace('.json', '')
        parts = filename.split(" Flight ")
        mission_name = f"{parts[0]}_Flight_{parts[1]}" if len(parts) == 2 else parts[0]

        # Generate map preview of the mission
        lat = []
        lon = []
        
        for entry in json_data['flights'][0]['geotag']:
            la = float(entry['coordinate'][0])
            lo = float(entry['coordinate'][1])
            lat.append(la)
            lon.append(lo)
        
        st.text('The mission collected '+ str(len(lat)) +' images.')
        
        points = list(zip(lat,lon))
        points_df = pd.DataFrame(points, columns=['lat','lon'])
        
        # Compute spatial extent
        min_lat, max_lat = points_df['lat'].min(), points_df['lat'].max()
        min_lon, max_lon = points_df['lon'].min(), points_df['lon'].max()
        center_lat = (min_lat + max_lat) / 2
        center_lon = (min_lon + max_lon) / 2

        z = get_zoom(min_lat, min_lon, max_lat, max_lon)
        
        st.pydeck_chart(pdk.Deck(
        map_style='mapbox://styles/mapbox/satellite-streets-v11',
        initial_view_state=pdk.ViewState(
            latitude=center_lat,
            longitude=center_lon,
            zoom=z,
            pitch=0,
         ),
         layers=[
             pdk.Layer(
                 'ScatterplotLayer',
                 data=points_df,
                 get_position='[lon, lat]',
                 get_color='[70, 130, 180, 200]',
                 get_radius=20,
             ),
             ],
         ))

        # Generate PDF
        pdf_buffer = generate_pdf(json_data, mission_name)

        st.success("✅ PDF report generated successfully!")
        st.download_button(
            label="📄 Download PDF Report",
            data=pdf_buffer,
            file_name=f"{mission_name} Data Collection Report.pdf",
            mime="application/pdf"
        )

    except Exception as e:
        st.error(f"❌ Failed to process file: {e}")


