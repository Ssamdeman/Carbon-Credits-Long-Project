from flask import Flask, request, render_template, jsonify
import ee
import os
import xml.etree.ElementTree as ET

app = Flask(__name__)

# Set upload folder
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/results.html', methods=['POST'])
def upload_kml():
    # Check if a file was uploaded
    if 'kml_file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['kml_file']

    # Check if the file has a valid name
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file and file.filename.endswith('.kml'):
        # Save the file
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)

        # Process the KML file (parse it)
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()

            # Extract some data from the KML file (example: placemarks)
            placemarks = []
            for placemark in root.findall('.//{http://www.opengis.net/kml/2.2}Placemark'):
                name = placemark.find('{http://www.opengis.net/kml/2.2}name')
                if name is not None:
                    placemarks.append(name.text)

            return jsonify({
                "message": "File uploaded and processed successfully",
                "placemarks": placemarks
            }), 200
        except ET.ParseError:
            return jsonify({"error": "Failed to parse KML file"}), 400

    return jsonify({"error": "Invalid file type. Only .kml files are allowed."}), 400



def calculate_carbon_stocks(areas):
# Calculates carbon stocks of project area using averages for each land feature
    total_carbon_stocks = 0
    for class_value, class_info in landcover_classes.items():
        class_name = class_info["name"]
        total_carbon_stocks += class_info["avg_carbon_stocks"] * areas[class_name]
    return total_carbon_stocks
        
def reforest(areas):
# Convert areas of shrubland, grassland, and cropland to tree cover
    reforested_areas = areas.copy()
    reforested_areas["Tree Cover"] += \
        reforested_areas["Shrubland"] + reforested_areas["Grassland"] + reforested_areas["Cropland"]
    reforested_areas["Shrubland"] = 0
    reforested_areas["Grassland"] = 0
    reforested_areas["Cropland"] = 0
    return reforested_areas

app = Flask(__name__)

# Set up Earth Engine authentication
try:
    credentials = ee.ServiceAccountCredentials(
        #'ding-22@ordinal-reason-440501-p5.iam.gserviceaccount.com',
        #'/Users/williamding/Documents/GitHub/Carbon-Credits-Long-Project/keys/ordinal-reason-440501-p5-7fd661e0c0ad.json'
    )
    ee.Initialize(credentials)
except ee.EEException as e:
    print("Google Earth Engine initialization error:", e)

# Define land cover classes with their corresponding colors and average carbon stocks per hectare (tC/ha)
landcover_classes = {
    10: {"name": "Tree Cover", "color": "#006400", "avg_carbon_stocks": 350},               # Dark Green
    20: {"name": "Shrubland", "color": "#228B22", "avg_carbon_stocks": 110},                # Forest Green
    30: {"name": "Grassland", "color": "#7CFC00", "avg_carbon_stocks": 65},                 # Lawn Green
    40: {"name": "Cropland", "color": "#FFD700", "avg_carbon_stocks": 58},                  # Gold
    50: {"name": "Built-up", "color": "#A9A9A9", "avg_carbon_stocks": 20},                  # Dark Gray
    60: {"name": "Bare / Sparse Vegetation", "color": "#DEB887", "avg_carbon_stocks": 11},  # Burly Wood
    70: {"name": "Snow and Ice", "color": "#FFFFFF", "avg_carbon_stocks": 0},               # White
    80: {"name": "Permanent Water Bodies", "color": "#1E90FF", "avg_carbon_stocks": 0},     # Dodger Blue
    90: {"name": "Herbaceous Wetland", "color": "#00CED1", "avg_carbon_stocks": 260},       # Dark Turquoise
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit_coordinates', methods=['POST'])
def submit_coordinates():
    data = request.form

    try:
        # Extract list of coordinates
        coordinates = data.get('coordinates')

        # Extract coordinates from user input
        # top_left_lat = float(data['top_left_latitude'])
        # top_left_lon = float(data['top_left_longitude'])
        # bottom_right_lat = float(data['bottom_right_latitude'])
        # bottom_right_lon = float(data['bottom_right_longitude'])

        # Determine top, bottom, left, and right coordinates for GEE
        # top_lat = max(top_left_lat, bottom_right_lat)
        # bottom_lat = min(top_left_lat, bottom_right_lat)
        # left_lon = min(top_left_lon, bottom_right_lon)
        # right_lon = max(top_left_lon, bottom_right_lon)

        # Create the Rectangle geometry
        # rectangle = ee.Geometry.Rectangle([left_lon, bottom_lat, right_lon, top_lat])

        # Create the Polygon geometry using the user-provided coordinates
        polygon = ee.Geometry.Polygon([coordinates])

        # Fetch and process the satellite image using GEE
        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30)) \
            .filter(ee.Filter.date('2021-01-01', '2021-12-31')) \
            .filterBounds(polygon)
        
        # Take a median composite of the image and visualize it
        composite = s2.median().visualize(bands=['B4', 'B3', 'B2'], min=0, max=3000)
        image_url = composite.getThumbURL({'region': polygon, 'dimensions': 500})

        # Load and visualize the ESA WorldCover data
        landcover = ee.Image('ESA/WorldCover/v200/2021')
        landcoverVis = {
            'min': 10,
            'max': 90,
            'palette': [class_info["color"] for class_info in landcover_classes.values()]
        }
        landcover_image = landcover.clip(polygon).visualize(**landcoverVis)
        landcover_image_url = landcover_image.getThumbURL({'region': polygon, 'dimensions': 500})

        # Calculate the area for each landcover class
        areas = {}
        for class_value, class_info in landcover_classes.items():
            class_name = class_info["name"]

            # Mask the image to isolate the current class
            masked_class = landcover.eq(class_value)

            # Calculate area in square meters
            area = masked_class.multiply(ee.Image.pixelArea()).reduceRegion(
                reducer=ee.Reducer.sum(),
                geometry=polygon,
                scale=30,
                maxPixels=1e9
            ).getInfo()

            # Convert the area to hectares (1 hectare = 10,000 m²)
            areas[class_name] = area('Map', 0) / 10000 if area.get('Map') else 0

        # Calculate carbon stocks (tC) of current project area
        current_carbon_stocks = calculate_carbon_stocks(areas)

        # Calculate potential carbon stocks (tC) of reforested project area
        reforested_areas = reforest(areas)
        reforested_carbon_stocks = calculate_carbon_stocks(reforested_areas)

        # Calculate additionality (tC) and from reforestation project
        additionality = reforested_carbon_stocks - current_carbon_stocks 

        # Calculate number of carbon credits earned from reforestation project
        # 1 tonne of carbon (tC) corresponds to 3.667 carbon credits in terms of CO2 equivalent
        carbon_credits = additionality * 3.667
        print(carbon_credits)

        # return render_template('results.html',
        #                       image_url=image_url,
        #                       landcover_image_url=landcover_image_url,
        #                       top_lat=top_lat,
        #                       left_lon=left_lon,
        #                       bottom_lat=bottom_lat,
        #                       right_lon=right_lon,
        #                       landcover_classes=landcover_classes,
        #                       landcover_areas=areas,
        #                       current_carbon_stocks=current_carbon_stocks,
        #                       reforested_carbon_stocks=reforested_carbon_stocks,
        #                       additionality=additionality,
        #                       carbon_credits=carbon_credits
        #                       )
    except Exception as e:
        print("Error processing coordinates:", e)
        return render_template('error.html', error_message='An error occurred while processing the coordinates.')

if __name__ == '__main__':
    app.run(debug=True)
    