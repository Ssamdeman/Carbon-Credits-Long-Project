from flask import Flask, request, render_template, jsonify
import ee
import os
import xml.etree.ElementTree as ET

app = Flask(__name__)

# Set upload folder
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/upload', methods=['POST'])
def upload_kml():
    if 'kml_file' not in request.files:
        print("No file part in request")
        return jsonify({"error": "No file part"}), 400

    file = request.files['kml_file']
    if file.filename == '':
        print("No selected file")
        return jsonify({"error": "No selected file"}), 400

    if not file.filename.endswith('.kml'):
        print("Invalid file type")
        return jsonify({"error": "Invalid file type. Only .kml files are allowed."}), 400

    try:
        # Save the file
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        print(f"File saved to {filepath}")

        # Extract coordinates from KML
        coordinates_list = extract_coordinates_from_kml(filepath)
        print(f"Extracted coordinates: {coordinates_list}")
        
        if not coordinates_list:
            print("No coordinates found in KML file")
            return render_template('error.html', 
                error_message='No valid coordinates found in KML file.')

        # Process each set of coordinates
        results = []
        for coord_data in coordinates_list:
            try:
                print(f"Processing coordinates: {coord_data}")
                result = process_coordinates(coord_data["coords"])
                if result:  # Only add successful results
                    results.append(result)
                    print("Successfully processed coordinate set")
                else:
                    print("Failed to process coordinate set (no result returned)")
            except Exception as e:
                print(f"Error processing coordinate set: {str(e)}")
                continue

        if not results:
            print("No results were successfully processed")
            return render_template('error.html', 
                error_message='Could not process any coordinates from the KML file.')

        print(f"Successfully processed {len(results)} coordinate sets")
        return render_template('results.html', results=results)

    except Exception as e:
        print(f"Error processing KML file: {str(e)}")
        return render_template('error.html', 
            error_message=f'Error processing KML file: {str(e)}')

def extract_coordinates_from_kml(filepath):
    """Extract coordinates from KML file."""
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        
        # Define the KML namespace
        ns = {'kml': 'http://www.opengis.net/kml/2.2'}
        
        coordinates_list = []
        processed_coords = set()  # Keep track of processed coordinates
        
        # Look for Polygons in MultiGeometry
        for multigeometry in root.findall('.//kml:MultiGeometry', ns):
            for polygon in multigeometry.findall('.//kml:Polygon', ns):
                coords_elem = polygon.find('.//kml:coordinates', ns)
                if coords_elem is not None:
                    coord_string = coords_elem.text.strip()
                    coords = []
                    for point in coord_string.split():
                        try:
                            parts = point.split(',')
                            if len(parts) >= 2:
                                lon, lat = parts[:2]
                                coords.append([float(lon), float(lat)])
                        except Exception as e:
                            print(f"Error parsing coordinate point {point}: {str(e)}")
                            continue
                    
                    # Create a hash of coordinates to check for duplicates
                    coords_hash = tuple(tuple(coord) for coord in coords)
                    if coords_hash not in processed_coords and len(coords) >= 3:
                        coordinates_list.append({"type": "polygon", "coords": coords})
                        processed_coords.add(coords_hash)
                        print(f"Found polygon with {len(coords)} points")

        # Look for individual Polygons (not in MultiGeometry)
        for polygon in root.findall('.//kml:Polygon', ns):
            coords_elem = polygon.find('.//kml:coordinates', ns)
            if coords_elem is not None:
                coord_string = coords_elem.text.strip()
                coords = []
                for point in coord_string.split():
                    try:
                        parts = point.split(',')
                        if len(parts) >= 2:
                            lon, lat = parts[:2]
                            coords.append([float(lon), float(lat)])
                    except Exception as e:
                        print(f"Error parsing coordinate point {point}: {str(e)}")
                        continue
                
                # Create a hash of coordinates to check for duplicates
                coords_hash = tuple(tuple(coord) for coord in coords)
                if coords_hash not in processed_coords and len(coords) >= 3:
                    coordinates_list.append({"type": "polygon", "coords": coords})
                    processed_coords.add(coords_hash)
                    print(f"Found polygon with {len(coords)} points")

        print(f"Total unique polygons found: {len(coordinates_list)}")
        return coordinates_list

    except Exception as e:
        print(f"Error parsing KML file: {str(e)}")
        raise

def create_square_around_point(lon, lat, size_degrees=0.01):
    """Create a square polygon around a point."""
    # size_degrees=0.01 creates roughly a 1km x 1km square at the equator
    return [
        [lon - size_degrees, lat + size_degrees],  # top left
        [lon + size_degrees, lat + size_degrees],  # top right
        [lon + size_degrees, lat - size_degrees],  # bottom right
        [lon - size_degrees, lat - size_degrees],  # bottom left
        [lon - size_degrees, lat + size_degrees]   # close the polygon
    ]

def process_coordinates(coordinates):
    """Process a single set of coordinates through Google Earth Engine."""
    try:
        # Create the Polygon geometry
        polygon = ee.Geometry.Polygon([coordinates])

        # Fetch and process satellite image
        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30)) \
            .filter(ee.Filter.date('2021-01-01', '2021-12-31')) \
            .filterBounds(polygon)
        
        if s2.size().getInfo() == 0:
            return None  # No imagery available for this location

        composite = s2.median().visualize(bands=['B4', 'B3', 'B2'], min=0, max=3000)
        image_url = composite.getThumbURL({'region': polygon, 'dimensions': 500})

        # Process landcover data
        landcover = ee.Image('ESA/WorldCover/v200/2021')
        landcoverVis = {
            'min': 10,
            'max': 90,
            'palette': [class_info["color"] for class_info in landcover_classes.values()]
        }
        landcover_image = landcover.clip(polygon).visualize(**landcoverVis)
        landcover_image_url = landcover_image.getThumbURL({'region': polygon, 'dimensions': 500})

        # Calculate areas for each landcover class
        areas = {}
        for class_value, class_info in landcover_classes.items():
            class_name = class_info["name"]
            masked_class = landcover.eq(class_value)
            area = masked_class.multiply(ee.Image.pixelArea()).reduceRegion(
                reducer=ee.Reducer.sum(),
                geometry=polygon,
                scale=30,
                maxPixels=1e9
            ).getInfo()
            areas[class_name] = area.get('area', 0) / 10000  # Convert to hectares

        # Calculate carbon stocks and credits
        current_carbon_stocks = calculate_carbon_stocks(areas)
        reforested_areas = reforest(areas)
        reforested_carbon_stocks = calculate_carbon_stocks(reforested_areas)
        additionality = reforested_carbon_stocks - current_carbon_stocks
        carbon_credits = additionality * 3.667

        return {
            'image_url': image_url,
            'landcover_image_url': landcover_image_url,
            'areas': areas,
            'current_carbon_stocks': current_carbon_stocks,
            'reforested_carbon_stocks': reforested_carbon_stocks,
            'additionality': additionality,
            'carbon_credits': carbon_credits
        }

    except Exception as e:
        print(f"Error processing coordinates: {str(e)}")
        return None

# Set up Earth Engine authentication
try:
    credentials = ee.ServiceAccountCredentials(
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

if __name__ == '__main__':
    app.run(debug=True)