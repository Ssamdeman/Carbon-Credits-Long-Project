from flask import Flask, request, render_template,jsonify
import ee, math


def carbon_stock_change(t, max_biomass, growth_rate, mortality_rate, root_to_shoot, areas, baseline):
    # Calculates the change in carbon stocks at year t compared to year t=0

    # Calculate the average carbon stock (tC/ha) in aboveground woody biomass in the project scenario in year t
    aboveground_woody_biomass = calculate_aboveground_woody_biomass(t, max_biomass, growth_rate, mortality_rate)
    aboveground_woody_biomass_carbon_stock_avg = aboveground_woody_biomass * 0.47 # Carbon makes up approximately 47% of the dry biomass for most tree species

    # Calculate the average carbon stock (tC/ha) in woody biomass in the project scenario in year t
    woody_biomass_carbon_stock_avg = aboveground_woody_biomass_carbon_stock_avg * (1 + root_to_shoot)

    # Calculate the total carbon stocks (tC) of the reforested areas in year t
    converted_area = areas["Shrubland"] + areas["Grassland"] + areas["Cropland"]
    total_carbon_stocks = woody_biomass_carbon_stock_avg * converted_area

    # Calculate and return change in carbon stocks
    change_in_carbon_stocks = total_carbon_stocks - baseline
    return change_in_carbon_stocks


def calculate_aboveground_woody_biomass(t, max_biomass, growth_rate, mortality_rate=0.1):
    # Caculates the aboveground woody biomass (t/ha) in the project scenario at year t

    # Logistic growth model to estimate biomass accumulation
    biomass = max_biomass * (1 - math.exp(-growth_rate * t))

    # Adjust biomass for mortality rate
    adjusted_biomass = biomass * (1 - mortality_rate)

    return adjusted_biomass

def calculate_baseline(areas):
    # Calculates the baseline carbon stocks (tC) of the area to be converted to tree cover by getting
    # the sum of the products of the areas of each land feature to be converted and their respective average carbon stocks (tC/ha)
    shrubland_carbon_stocks = landcover_classes[20]["avg_carbon_stocks"] * areas["Shrubland"]
    grassland_carbon_stocks = landcover_classes[30]["avg_carbon_stocks"] * areas["Grassland"]
    cropland_carbon_stocks = landcover_classes[40]["avg_carbon_stocks"] * areas["Cropland"]
    baseline = shrubland_carbon_stocks + grassland_carbon_stocks + cropland_carbon_stocks
    return baseline


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
    ee.Initialize()
except ee.EEException as e:
    print("Google Earth Engine initialization error:", e)

# Define land cover classes with their corresponding colors and average carbon stocks per hectare (tC/ha)
landcover_classes = {
    10: {"name": "Tree Cover", "color": "#006400", "avg_carbon_stocks": 25},               # Dark Green
    20: {"name": "Shrubland", "color": "#228B22", "avg_carbon_stocks": 10},                # Forest Green
    30: {"name": "Grassland", "color": "#7CFC00", "avg_carbon_stocks": 4},                 # Lawn Green
    40: {"name": "Cropland", "color": "#FFD700", "avg_carbon_stocks": 5},                  # Gold
    50: {"name": "Built-up", "color": "#A9A9A9", "avg_carbon_stocks": 0.1},                  # Dark Gray
    60: {"name": "Bare / Sparse Vegetation", "color": "#DEB887", "avg_carbon_stocks": 0.5},  # Burly Wood
    70: {"name": "Snow and Ice", "color": "#FFFFFF", "avg_carbon_stocks": 0},               # White
    80: {"name": "Permanent Water Bodies", "color": "#1E90FF", "avg_carbon_stocks": 0},     # Dodger Blue
    90: {"name": "Herbaceous Wetland", "color": "#00CED1", "avg_carbon_stocks": 25},       # Dark Turquoise
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

        ## Adding validation of gride size for 
        area_in_hectares = abs((top_lat - bottom_lat) * (right_lon - left_lon)) * 111.32 * 111.32 * 100

        if area_in_hectares < 10:  # 1 hectare minimum
            raise ValueError("Selected area too small. Minimum 1 hectare required.")
        if area_in_hectares > 10000:  # 10,000 hectare maximum 
            raise ValueError("Selected area too large. Maximum 10,000 hectares allowed.")

        # Calculate center point of original area
        center_lat = (top_lat + bottom_lat) / 2
        center_lon = (left_lon + right_lon) / 2

        # Calculate original dimensions
        original_height = top_lat - bottom_lat
        original_width = right_lon - left_lon

        # Calculate expanded coordinates (2x bigger)
        expanded_top_lat = center_lat + (original_height)  # Double the distance from center
        expanded_bottom_lat = center_lat - (original_height)
        expanded_left_lon = center_lon - (original_width)
        expanded_right_lon = center_lon + (original_width)
        
        # Create expanded rectangle geometry
        expanded_rectangle = ee.Geometry.Rectangle([
        expanded_left_lon, expanded_bottom_lat, 
        expanded_right_lon, expanded_top_lat
        ])

        # Calculate grid for expanded area (3x3)
        expanded_width = abs(expanded_right_lon - expanded_left_lon)
        expanded_height = abs(expanded_top_lat - expanded_bottom_lat)
        expanded_cell_width = expanded_width / 3
        expanded_cell_height = expanded_height / 3

       
        # Create the Rectangle geometry
        rectangle = ee.Geometry.Rectangle([left_lon, bottom_lat, right_lon, top_lat])

        # Add grid calculation here
        total_width = abs(right_lon - left_lon) 
        total_height = abs(top_lat - bottom_lat)
        cell_width = total_width / 3  # For 3x3 grid
        cell_height = total_height / 3 # For 3x3 grid 
       

        # Before grid cells creation, create dictionary to store cell info
        grid_info = {}

        # Modify grid cells creation loop
        grid_cells = []
        for i in range(3):  # rows
            for j in range(3):  # columns
                cell_left = left_lon + (j * cell_width)
                cell_right = cell_left + cell_width
                cell_top = top_lat - (i * cell_height)
                cell_bottom = cell_top - cell_height
                
                # Create cell identifier (A1, A2, etc)
                cell_id = f"{chr(65+i)}{j+1}"  # A1, A2, A3, B1, B2...
                
                # Calculate cell area in hectares
                cell_area = abs((cell_top - cell_bottom) * (cell_right - cell_left)) * 111.32 * 111.32 * 100
                
                cell = ee.Geometry.Rectangle([cell_left, cell_bottom, cell_right, cell_top])
                grid_cells.append(cell)
                
                # Store cell info
                grid_info[cell_id] = {
                    "geometry": cell,
                    "area": cell_area,
                    "coordinates": {
                        "top": cell_top,
                        "bottom": cell_bottom,
                        "left": cell_left,
                        "right": cell_right
                    }
                }


        # Create grid cells for expanded area
        expanded_grid_cells = []
        expanded_grid_info = {} 
        # Create expanded grid cells with area calculations
        for i in range(3):  # rows
            for j in range(3):  # columns
                cell_left = expanded_left_lon + (j * expanded_cell_width)
                cell_right = cell_left + expanded_cell_width
                cell_top = expanded_top_lat - (i * expanded_cell_height)
                cell_bottom = cell_top - expanded_cell_height
                
                # Create cell identifier
                cell_id = f"E{chr(65+i)}{j+1}"  # EA1, EA2, EA3, EB1... ('E' for expanded)
                
                # Calculate cell area
                cell_area = abs((cell_top - cell_bottom) * (cell_right - cell_left)) * 111.32 * 111.32 * 100
                
                cell = ee.Geometry.Rectangle([cell_left, cell_bottom, cell_right, cell_top])
                expanded_grid_cells.append(cell)
                
                # Store expanded cell info
                expanded_grid_info[cell_id] = {
                    "geometry": cell,
                    "area": cell_area,
                    "coordinates": {
                        "top": cell_top,
                        "bottom": cell_bottom,
                        "left": cell_left,
                        "right": cell_right
                    }
                }





        # Fetch and process the satellite image using GEE
        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30)) \
            .filter(ee.Filter.date('2021-01-01', '2021-12-31')) \
            .filterBounds(rectangle)
        
        # Take a median composite of the image and visualize it
        composite = s2.median().visualize(bands=['B4', 'B3', 'B2'], min=0, max=3000)
        image_url = composite.getThumbURL({'region': rectangle, 'dimensions': 500})

        # Load and visualize the ESA WorldCover data
        landcover = ee.Image('ESA/WorldCover/v200/2021')
        landcoverVis = {
            'min': 10,
            'max': 90,
            'palette': [class_info["color"] for class_info in landcover_classes.values()]
        }

        # Enhanced satellite image
        grid_s2 = s2.median().visualize(bands=['B4', 'B3', 'B2'], min=0, max=3000)
        grid_image_url = grid_s2.getThumbURL({
            'region': rectangle, 
            'dimensions': 500,
        })

        # Add grid overlay
        grid_overlay = ee.FeatureCollection(grid_cells)
        grid_vis = grid_overlay.style(**{'color': 'red', 'fillColor': '00000000'})

        # Add grid overlay to the image
        satellite_with_grid = ee.ImageCollection([
            grid_s2,  # Use the already visualized image
            grid_vis.visualize()
        ]).mosaic()

        grid_image_url = satellite_with_grid.getThumbURL({
            'region': rectangle,
            'dimensions': 500,
        })
        # print("Grid image URL:", grid_image_url) -->> ## for testing
        # for cell_id, info in grid_info.items(): ### for testing
        #     print(f"Grid {cell_id} area: {info['area']:.2f} hectares")



        # Get satellite image for expanded area
        expanded_s2 = s2.median().visualize(bands=['B4', 'B3', 'B2'], min=0, max=3000)
        expanded_image_url = expanded_s2.getThumbURL({
            'region': expanded_rectangle, 
            'dimensions': 500,
        })

        # Add grid overlay to expanded image
        expanded_grid_overlay = ee.FeatureCollection(expanded_grid_cells)
        expanded_grid_vis = expanded_grid_overlay.style(**{'color': 'red', 'fillColor': '00000000'})

        # Combine expanded satellite image with grid
        expanded_satellite_with_grid = ee.ImageCollection([
            expanded_s2,
            expanded_grid_vis.visualize()
        ]).mosaic()

        expanded_grid_image_url = expanded_satellite_with_grid.getThumbURL({
            'region': expanded_rectangle,
            'dimensions': 500,
        })

        # Print expanded grid areas
        print(expanded_grid_image_url)
        for cell_id, info in expanded_grid_info.items():
            print(f"Expanded Grid {cell_id} area: {info['area']:.2f} hectares")






        ##orginal code witout grid.
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

        baseline = calculate_baseline(areas)


        # Calculate carbon stock changes (tC) in years 1-10
        carbon_stock_changes = []
        for year in range(1, 11):
            carbon_stock_changes.append(carbon_stock_change(year, 150, 0.1, 0.1, 0.25, areas, baseline))
        

        # Calculate carbon credits earned in years 1-10
        carbon_credits_earned = []
        for year in range(10):
            carbon_credits_earned.append(carbon_stock_changes[year] * (44/12))




        ## display the results in the results.html template
        return render_template('results.html',
                               image_url=image_url,
                               landcover_image_url=landcover_image_url,
                               top_lat=top_lat,
                               left_lon=left_lon,
                               bottom_lat=bottom_lat,
                               right_lon=right_lon,
                               landcover_classes=landcover_classes,
                               landcover_areas=areas,
                               carbon_stock_changes=carbon_stock_changes,
                               carbon_credits_earned=carbon_credits_earned
                               )
    except Exception as e:
        # print("Error processing coordinates:", e)
        # return render_template('error.html', error_message='An error occurred while processing the coordinates.')
        import traceback
        print("Error processing coordinates:", str(e))
        print("Full traceback:", traceback.format_exc())
        return render_template('error.html', error_message=str(e))

if __name__ == '__main__':
    app.run(debug=True)