import json
import logging

logger = logging.getLogger(__name__)

def load_observations(raw_data):
    total_observations = []
    for gps_pos in sorted(raw_data.keys(), key=int):
        gps_data = raw_data[gps_pos]
        total_observations.append(gps_data)
        
    final_states = []

    for final_state in total_observations[-1]:
        states = list(total_observations[-1][final_state].keys())
        for s in states:
            final_states.append(s)

    final_states_dict = {}

    for state in final_states:
        final_states_dict[state] = {}

    total_observations.append(final_states_dict)


    return total_observations



def get_states_per_time(observations):
    states_per_time = []
    for obs in observations:
        states = set()
        for src in obs:
            states.add(src)
            for dest in obs[src]:
                states.add(dest)
        
        states_per_time.append(states)

    return states_per_time



def run_viterbi(observations, states_per_t):
    V = [{}]
    path = {}

   
    for state in states_per_t[0]:
        V[0][state] = (0.0, None)
        path[state] = [state]

   
    for t in range(1, len(observations)):
        V.append({})
        next_path = {}

        for next_state in states_per_t[t]:
            min_cost = float('inf')
            best_prev_state = None

            for curr_state in observations[t - 1]:
                if next_state in observations[t - 1][curr_state]:
                    transition_cost = observations[t - 1][curr_state][next_state]
                    total_cost = V[t - 1][curr_state][0] + transition_cost

                    if total_cost < min_cost:
                        min_cost = total_cost
                        best_prev_state = curr_state

            if best_prev_state is not None:
                V[t][next_state] = (min_cost, best_prev_state)
                next_path[next_state] = path[best_prev_state] + [next_state]

        if not next_path:
            logger.debug("cannot find path")
            return None  
        path = next_path

    return V, path



def backtrace_best_path(V, path):
    if not V[-1]:
        logger.debug("no valid path found")
        return None

    final_states = V[-1]
    best_final_state = min(final_states, key=lambda s: final_states[s][0])
    best_path = path[best_final_state]
    total_cost = final_states[best_final_state][0]

    return best_path, total_cost


def viterbi_algorithm(raw_data):
    observations = load_observations(raw_data)
    states_per_t = get_states_per_time(observations)
    result = run_viterbi(observations, states_per_t)
    # Default to an empty path so callers can safely iterate/measure length
    best_path = []

    if result is not None:
        V, path = result
        best_path_result = backtrace_best_path(V, path)

        if best_path_result:
            best_path, total_cost = best_path_result

    return best_path

