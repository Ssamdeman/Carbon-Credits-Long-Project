import ee
import geemap

#ee.Authenticate() #Only need to run once
ee.Initialize(project='longproject-cfinch')

geometry = ee.Geometry.Polygon([[
    [82.60642647743225, 27.16350437805251],
    [82.60984897613525, 27.1618529901377],
    [82.61088967323303, 27.163695288375266],
    [82.60757446289062, 27.16517483230927]
]])

compare_data = ee.ImageCollection("COPERNICUS/S2_HARMONIZED") \
    .filter(ee.Filter.date('2023-01-01', '2023-12-31')) \
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30)) \
    .filter(ee.Filter.bounds(geometry))
