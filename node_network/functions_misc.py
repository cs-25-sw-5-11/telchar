from math import radians, sin, cos, sqrt, atan2
import os
import json

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi/2)**2 + cos(phi1)*cos(phi2)*sin(dlambda/2)**2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))

def output_network_distances(vertex_layers):
    from functions_mapping import all_pairs_network_distances_between_layers
    
    trip = 'trips_150103_6'
    data_output_dict = {
        'transitions':  {
            trip: {}
        }
    }


    for i in range(len(vertex_layers)-1):
        result = all_pairs_network_distances_between_layers(vertex_layers[i], vertex_layers[i+1])        
        transition = {}
        for k, v in result.items():
            transition[k.id] = {vv.id: dist for vv, dist in v.items()}
        data_output_dict['transitions'][trip][i] = transition

    output_path = 'peter_fucking_around/output_data/network_distances.json'
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(data_output_dict, f, indent=4)
