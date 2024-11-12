from flask import Flask, request, render_template
import ee

app = Flask(__name__)

# Set up Earth Engine authentication
try:
    ee.Initialize()
except ee.EEException as e:
    print("Google Earth Engine initialization error:", e)

# Define land cover classes and their corresponding colors
landcover_classes = {
    10: {"name": "Tree Cover", "color": "#006400"},               # Dark Green
    20: {"name": "Shrubland", "color": "#228B22"},                # Forest Green
    30: {"name": "Grassland", "color": "#7CFC00"},                # Lawn Green
    40: {"name": "Cropland", "color": "#FFD700"},                 # Gold
    50: {"name": "Built-up", "color": "#A9A9A9"},                  # Dark Gray
    60: {"name": "Bare / Sparse Vegetation", "color": "#DEB887"}, # Burly Wood
    70: {"name": "Snow and Ice", "color": "#FFFFFF"},              # White
    80: {"name": "Permanent Water Bodies", "color": "#1E90FF"},    # Dodger Blue
    90: {"name": "Herbaceous Wetland", "color": "#00CED1"},       # Dark Turquoise
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit_coordinates', methods=['POST'])
def submit_coordinates():
    data = request.form

    try:
        # Extract coordinates from user input
        top_left_lat = float(data['top_left_latitude'])
        top_left_lon = float(data['top_left_longitude'])
        bottom_right_lat = float(data['bottom_right_latitude'])
        bottom_right_lon = float(data['bottom_right_longitude'])

        # Determine top, bottom, left, and right coordinates for GEE
        top_lat = max(top_left_lat, bottom_right_lat)
        bottom_lat = min(top_left_lat, bottom_right_lat)
        left_lon = min(top_left_lon, bottom_right_lon)
        right_lon = max(top_left_lon, bottom_right_lon)

        # Create the Rectangle geometry
        rectangle = ee.Geometry.Rectangle([left_lon, bottom_lat, right_lon, top_lat])

        # Fetch and process the satellite image using GEE
        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30)) \
            .filter(ee.Filter.date('2021-01-01', '2021-12-31')) \
            .filterBounds(rectangle)
        
        # Take a median composite of the image and visualize it
        composite = s2.median().visualize(bands=['B4', 'B3', 'B2'], min=0, max=3000)
        image_url = composite.getThumbURL({'region': rectangle, 'dimensions': 500})

        # Load and visualize the ESA WorldCover data
        landcover = ee.Image('ESA/WorldCover/v100/2020')
        landcoverVis = {
            'min': 10,
            'max': 90,
            'palette': [class_info["color"] for class_info in landcover_classes.values()]
        }
        landcover_image = landcover.clip(rectangle).visualize(**landcoverVis)
        landcover_image_url = landcover_image.getThumbURL({'region': rectangle, 'dimensions': 500})

        # Calculate the area for each landcover class
        areas = {}
        for class_value, class_info in landcover_classes.items():
            class_name = class_info["name"]

            # Mask the image to isolate the current class
            masked_class = landcover.eq(class_value)

            # Calculate area in square meters
            area = masked_class.multiply(ee.Image.pixelArea()).reduceRegion(
                reducer=ee.Reducer.sum(),
                geometry=rectangle,
                scale=30,
                maxPixels=1e9
            ).getInfo()

            # Convert the area to hectares (1 hectare = 10,000 m²)
            areas[class_name] = area['Map'] / 10000 if area['Map'] else 0

        return render_template('results.html',
                               image_url=image_url,
                               landcover_image_url=landcover_image_url,
                               top_lat=top_lat,
                               left_lon=left_lon,
                               bottom_lat=bottom_lat,
                               right_lon=right_lon,
                               landcover_classes=landcover_classes,
                               landcover_areas=areas)
    except Exception as e:
        print("Error processing coordinates:", e)
        return render_template('error.html', error_message='An error occurred while processing the coordinates.')

if __name__ == '__main__':
    app.run(debug=True)