#!/usr/bin/env python3
"""
Generate realistic vehicle tracking data for the REVERSE route
from 405 Belsize Dr to 450 Markham St in Toronto
Using the same timestamps as the forward route for synchronized animation
"""

import json
import csv
import math
from datetime import datetime, timedelta
from typing import List, Tuple, Dict

# Route coordinates from Mapbox - REVERSED
ROUTE_COORDS = [[-79.376835,43.704725],[-79.377107,43.70467],[-79.377133,43.704665],[-79.377215,43.704648],[-79.377293,43.704633],[-79.378276,43.704425],[-79.378359,43.704407],[-79.378334,43.704342],[-79.378057,43.703631],[-79.378033,43.703568],[-79.378011,43.703513],[-79.377886,43.703192],[-79.37786,43.703099],[-79.377855,43.703021],[-79.377859,43.70296],[-79.377874,43.702899],[-79.37789,43.702848],[-79.377923,43.702786],[-79.377975,43.70271],[-79.37801,43.702654],[-79.378041,43.702588],[-79.378072,43.702447],[-79.378071,43.702366],[-79.378052,43.702261],[-79.378045,43.702241],[-79.378024,43.702177],[-79.378125,43.702156],[-79.378489,43.702084],[-79.378734,43.702036],[-79.37895,43.701992],[-79.379666,43.701845],[-79.380545,43.701664],[-79.380621,43.701648],[-79.381731,43.701414],[-79.382197,43.701317],[-79.382651,43.701224],[-79.383179,43.701114],[-79.383259,43.701098],[-79.383337,43.701082],[-79.385313,43.700663],[-79.385936,43.700533],[-79.386212,43.700469],[-79.386711,43.700367],[-79.386808,43.70035],[-79.386947,43.700333],[-79.386922,43.700229],[-79.386843,43.699926],[-79.386828,43.699866],[-79.386714,43.699313],[-79.386686,43.699171],[-79.386602,43.698757],[-79.386583,43.69867],[-79.386534,43.698462],[-79.386475,43.698262],[-79.386451,43.698181],[-79.386445,43.698164],[-79.386419,43.698098],[-79.38626,43.697679],[-79.386222,43.697574],[-79.386209,43.69754],[-79.386131,43.697339],[-79.38583,43.696585],[-79.385339,43.695356],[-79.384832,43.694111],[-79.384636,43.69363],[-79.384611,43.693568],[-79.384582,43.693505],[-79.384396,43.693054],[-79.384067,43.692248],[-79.383692,43.691311],[-79.383337,43.690452],[-79.383305,43.690375],[-79.383272,43.6903],[-79.383043,43.689726],[-79.383019,43.689559],[-79.383019,43.68948],[-79.383134,43.68923],[-79.383261,43.688955],[-79.383499,43.688419],[-79.38354,43.688344],[-79.383636,43.688156],[-79.383702,43.688015],[-79.383706,43.688006],[-79.383927,43.68756],[-79.383971,43.687468],[-79.384202,43.687006],[-79.384204,43.687003],[-79.384311,43.686758],[-79.384367,43.686428],[-79.384352,43.6863],[-79.384327,43.686085],[-79.384175,43.685664],[-79.384117,43.685513],[-79.383892,43.684963],[-79.383831,43.684815],[-79.383753,43.684634],[-79.383687,43.684567],[-79.383622,43.684411],[-79.383621,43.684277],[-79.383534,43.68406],[-79.383405,43.683865],[-79.383347,43.683606],[-79.383223,43.68265],[-79.383215,43.68262],[-79.383136,43.682316],[-79.382928,43.681877],[-79.38267,43.681334],[-79.38252,43.680938],[-79.382472,43.680859],[-79.382385,43.680739],[-79.382354,43.680695],[-79.382347,43.680686],[-79.382248,43.680588],[-79.382117,43.680463],[-79.381894,43.680214],[-79.381513,43.679858],[-79.381211,43.679509],[-79.381119,43.679353],[-79.3808,43.678607],[-79.380543,43.678001],[-79.380514,43.677794],[-79.38054,43.677587],[-79.380543,43.677415],[-79.380593,43.676939],[-79.380618,43.676623],[-79.380633,43.676425],[-79.380636,43.676255],[-79.380614,43.675974],[-79.3806,43.675842],[-79.380585,43.675727],[-79.380563,43.675605],[-79.380521,43.675447],[-79.380466,43.675294],[-79.380197,43.674638],[-79.380169,43.674572],[-79.380162,43.674554],[-79.380146,43.67451],[-79.379961,43.674027],[-79.379869,43.673786],[-79.379832,43.673626],[-79.379645,43.672814],[-79.379605,43.672641],[-79.37948,43.672363],[-79.379426,43.672129],[-79.37939,43.671977],[-79.37932,43.671682],[-79.379318,43.671622],[-79.379316,43.671425],[-79.379316,43.671296],[-79.379333,43.671211],[-79.379412,43.67096],[-79.37947,43.670793],[-79.379553,43.670542],[-79.379733,43.670104],[-79.37974,43.67004],[-79.379739,43.669981],[-79.379732,43.669929],[-79.379699,43.669845],[-79.379611,43.669633],[-79.379545,43.669198],[-79.379447,43.668952],[-79.379421,43.668888],[-79.379395,43.668824],[-79.379113,43.668159],[-79.379058,43.668024],[-79.379019,43.667935],[-79.378985,43.667858],[-79.378924,43.667711],[-79.378728,43.667231],[-79.378683,43.66712],[-79.378565,43.66684],[-79.378494,43.666673],[-79.378451,43.666571],[-79.378364,43.666363],[-79.378334,43.666291],[-79.378451,43.666261],[-79.379414,43.666046],[-79.379879,43.665944],[-79.379943,43.66593],[-79.380829,43.665738],[-79.380939,43.665712],[-79.381044,43.665687],[-79.38139,43.665614],[-79.381536,43.665581],[-79.381671,43.665553],[-79.382054,43.665471],[-79.382387,43.665397],[-79.382492,43.665374],[-79.382702,43.665329],[-79.382798,43.665309],[-79.383444,43.665169],[-79.383675,43.665116],[-79.383751,43.6651],[-79.383859,43.665078],[-79.383957,43.665057],[-79.384466,43.664952],[-79.384569,43.664935],[-79.384673,43.664917],[-79.384992,43.664849],[-79.385182,43.664809],[-79.385459,43.664749],[-79.386189,43.664589],[-79.386623,43.664494],[-79.387019,43.664406],[-79.387155,43.664377],[-79.387292,43.664348],[-79.387728,43.664255],[-79.388008,43.664192],[-79.38818,43.664154],[-79.389037,43.663961],[-79.389273,43.663907],[-79.389369,43.663885],[-79.389476,43.66386],[-79.390463,43.66365],[-79.390498,43.663642],[-79.390621,43.66361],[-79.390728,43.663581],[-79.390804,43.663562],[-79.390831,43.663555],[-79.390886,43.663543],[-79.391611,43.663369],[-79.392349,43.663204],[-79.392638,43.663152],[-79.392812,43.663126],[-79.392791,43.663204],[-79.392813,43.66328],[-79.392863,43.663356],[-79.393129,43.663622],[-79.393253,43.663767],[-79.393375,43.663905],[-79.393397,43.663929],[-79.393472,43.664016],[-79.393622,43.664214],[-79.393795,43.664673],[-79.39385,43.664798],[-79.393876,43.664889],[-79.393896,43.664956],[-79.393915,43.665037],[-79.394031,43.665029],[-79.394246,43.664998],[-79.395137,43.66481],[-79.395702,43.664691],[-79.395785,43.664673],[-79.39605,43.664617],[-79.396904,43.664437],[-79.397832,43.664241],[-79.398063,43.664192],[-79.398251,43.664153],[-79.398294,43.664144],[-79.398342,43.664134],[-79.398441,43.664077],[-79.398591,43.663991],[-79.39867,43.663937],[-79.398791,43.663847],[-79.398898,43.663782],[-79.398973,43.663741],[-79.399036,43.663716],[-79.399117,43.663694],[-79.399243,43.663668],[-79.39949,43.663616],[-79.399972,43.663516],[-79.400044,43.663497],[-79.400143,43.663477],[-79.400452,43.663414],[-79.400649,43.663372],[-79.401279,43.663242],[-79.401548,43.663187],[-79.401753,43.663144],[-79.401819,43.663131],[-79.401915,43.663111],[-79.401995,43.663094],[-79.40208,43.663077],[-79.402121,43.663068],[-79.402203,43.663051],[-79.402278,43.663033],[-79.402382,43.663012],[-79.40268,43.662952],[-79.402735,43.662941],[-79.403074,43.662874],[-79.40376,43.662736],[-79.403857,43.662717],[-79.403917,43.662705],[-79.404808,43.662512],[-79.40537,43.662397],[-79.405937,43.662285],[-79.406015,43.66227],[-79.406077,43.662259],[-79.406631,43.662163],[-79.407204,43.662051],[-79.407272,43.662038],[-79.407872,43.661918],[-79.4085,43.661789],[-79.408526,43.661784],[-79.40917,43.66165],[-79.409639,43.661552],[-79.409733,43.661532],[-79.409753,43.661528],[-79.409718,43.661447],[-79.409085,43.659885],[-79.409059,43.65982],[-79.40908,43.659817],[-79.409177,43.659799],[-79.409673,43.659691],[-79.410267,43.65957],[-79.410896,43.659443],[-79.410911,43.659485],[-79.411046,43.659852],[-79.411188,43.660187],[-79.411339,43.660563],[-79.41145,43.660828]]

# Known major intersections and traffic controls along this route - REVERSED ORDER
# Based on Toronto street knowledge, but in reverse direction
TRAFFIC_CONTROLS = [
    # Format: (approx_lon, approx_lat, type, street_name, wait_time_seconds)
    (-79.3769, 43.7047, "stop_sign", "Belsize Dr & Mount Pleasant Rd", 5),
    (-79.3781, 43.7026, "traffic_light", "Mount Pleasant Rd & Davisville Ave", 50),
    (-79.3807, 43.7016, "traffic_light", "Mount Pleasant Rd & Soudan Ave", 45),
    (-79.3862, 43.7003, "traffic_light", "Mount Pleasant Rd & Heath St", 40),
    (-79.3862, 43.6981, "traffic_light", "Mount Pleasant Rd & St Clair Ave", 60),
    (-79.3832, 43.6820, "traffic_light", "Davenport Rd & Bathurst St", 55),
    (-79.3806, 43.6768, "traffic_light", "Davenport Rd & Dupont St", 50),
    (-79.3796, 43.6720, "traffic_light", "Davenport Rd & Christie St", 40),
    (-79.3795, 43.6663, "traffic_light", "Harbord St & Dovercourt Rd", 45),
    (-79.3846, 43.6651, "traffic_light", "Harbord St & Ossington Ave", 50),
    (-79.3896, 43.6639, "traffic_light", "Harbord St & Shaw St", 40),
    (-79.3938, 43.6650, "stop_sign", "Harbord St & Crawford St", 3),
    (-79.3986, 43.6642, "traffic_light", "Harbord St & Grace St", 35),
    (-79.4028, 43.6631, "traffic_light", "Harbord St & Manning Ave", 45),
    (-79.4073, 43.6620, "traffic_light", "Harbord St & Palmerston Ave", 40),
    (-79.4106, 43.6598, "traffic_light", "Harbord St & Markham St", 45),
]

def haversine_distance(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
    """Calculate distance between two coordinates in meters"""
    R = 6371000  # Earth's radius in meters
    lat1, lon1 = math.radians(coord1[1]), math.radians(coord1[0])
    lat2, lon2 = math.radians(coord2[1]), math.radians(coord2[0])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))

    return R * c

def find_closest_point_on_route(traffic_control: Tuple, route_coords: List) -> int:
    """Find the index of the closest point on route to a traffic control"""
    min_dist = float('inf')
    closest_idx = 0

    control_coord = (traffic_control[0], traffic_control[1])

    for i, coord in enumerate(route_coords):
        dist = haversine_distance(control_coord, coord)
        if dist < min_dist:
            min_dist = dist
            closest_idx = i

    return closest_idx

def interpolate_points(coord1: List[float], coord2: List[float], num_points: int) -> List[List[float]]:
    """Interpolate additional points between two coordinates"""
    points = []
    for i in range(1, num_points + 1):
        ratio = i / (num_points + 1)
        lon = coord1[0] + (coord2[0] - coord1[0]) * ratio
        lat = coord1[1] + (coord2[1] - coord1[1]) * ratio
        points.append([lon, lat])
    return points

def generate_realistic_route():
    """Generate realistic route with traffic controls and timing"""

    # Start time: 2:00 AM for minimal traffic - SAME AS FORWARD ROUTE
    start_time = datetime(2025, 1, 20, 2, 0, 0)

    # Night-time speeds (km/h) for different road types
    SPEEDS = {
        'residential': 40,  # 40 km/h on residential streets
        'arterial': 55,     # 55 km/h on main roads at night
        'stopped': 0,       # Stopped at lights
        'accelerating': 20, # Accelerating from stop
        'decelerating': 25  # Slowing for stop
    }

    enhanced_route = []
    current_time = start_time

    # Map traffic controls to route indices
    traffic_control_indices = {}
    for control in TRAFFIC_CONTROLS:
        idx = find_closest_point_on_route(control, ROUTE_COORDS)
        traffic_control_indices[idx] = control

    # Process each segment
    for i in range(len(ROUTE_COORDS)):
        coord = ROUTE_COORDS[i]

        # Determine road type and speed - REVERSED logic
        if i < 130:  # Mount Pleasant Rd and Davenport area
            speed_kmh = SPEEDS['arterial']
        elif i < 160:  # Davenport to Harbord transition
            speed_kmh = SPEEDS['arterial']
        elif i < 260:  # Harbord St (arterial)
            speed_kmh = SPEEDS['arterial']
        else:  # Final residential area approaching Markham St
            speed_kmh = SPEEDS['residential']

        # Check if we're at a traffic control
        if i in traffic_control_indices:
            control = traffic_control_indices[i]
            control_type = control[2]
            wait_time = control[4]

            # Add deceleration points before stop
            if i > 0:
                decel_dist = 30  # Start decelerating 30m before
                decel_points = 3
                for j in range(decel_points):
                    ratio = (j + 1) / decel_points
                    decel_coord = [
                        ROUTE_COORDS[i-1][0] + (coord[0] - ROUTE_COORDS[i-1][0]) * ratio,
                        ROUTE_COORDS[i-1][1] + (coord[1] - ROUTE_COORDS[i-1][1]) * ratio
                    ]
                    decel_time = 1.5 * ratio  # Takes 1.5 seconds to decelerate
                    current_time += timedelta(seconds=decel_time)
                    enhanced_route.append({
                        'timestamp': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'latitude': decel_coord[1],
                        'longitude': decel_coord[0],
                        'speed_kmh': SPEEDS['decelerating'] * (1 - ratio),
                        'status': f'Decelerating for {control_type}'
                    })

            # Add stop point
            enhanced_route.append({
                'timestamp': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                'latitude': coord[1],
                'longitude': coord[0],
                'speed_kmh': 0,
                'status': f'Stopped at {control[3]}'
            })

            # Wait at control
            current_time += timedelta(seconds=wait_time)

            # Add acceleration points after stop
            if i < len(ROUTE_COORDS) - 1:
                accel_points = 3
                for j in range(accel_points):
                    ratio = (j + 1) / accel_points
                    accel_coord = [
                        coord[0] + (ROUTE_COORDS[i+1][0] - coord[0]) * ratio * 0.3,
                        coord[1] + (ROUTE_COORDS[i+1][1] - coord[1]) * ratio * 0.3
                    ]
                    accel_time = 2 * ratio  # Takes 2 seconds to accelerate
                    current_time += timedelta(seconds=accel_time)
                    enhanced_route.append({
                        'timestamp': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'latitude': accel_coord[1],
                        'longitude': accel_coord[0],
                        'speed_kmh': SPEEDS['accelerating'] * ratio + speed_kmh * ratio,
                        'status': f'Accelerating from {control_type}'
                    })
        else:
            # Regular travel point
            if i > 0:
                distance = haversine_distance(ROUTE_COORDS[i-1], coord)
                time_seconds = (distance / 1000) / speed_kmh * 3600
                current_time += timedelta(seconds=time_seconds)

            enhanced_route.append({
                'timestamp': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                'latitude': coord[1],
                'longitude': coord[0],
                'speed_kmh': speed_kmh,
                'status': 'Driving'
            })

    return enhanced_route

def main():
    """Generate and save the realistic REVERSE route data"""
    print("Generating realistic REVERSE route with traffic controls...")
    print("From: 405 Belsize Dr")
    print("To: 450 Markham St")

    route_data = generate_realistic_route()

    # Save to CSV
    output_file = 'vehicle_tracking/realistic_reverse_route_simulation.csv'

    with open(output_file, 'w', newline='') as csvfile:
        fieldnames = ['timestamp', 'latitude', 'longitude', 'speed_kmh', 'status']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for point in route_data:
            writer.writerow(point)

    print(f"\nGenerated {len(route_data)} data points")
    print(f"Route saved to: {output_file}")
    print(f"\nSummary:")
    print(f"- Start time: {route_data[0]['timestamp']}")
    print(f"- End time: {route_data[-1]['timestamp']}")
    print(f"- Total traffic controls: {len(TRAFFIC_CONTROLS)}")
    print(f"- Original route points: {len(ROUTE_COORDS)} (reversed)")
    print(f"- Enhanced route points: {len(route_data)}")

if __name__ == "__main__":
    main()