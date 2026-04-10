"""
Downstream settlement exposure analysis for GLOF risk.

Identifies settlements downstream of glacial lakes using DEM-based
flow routing and population data (GHS-POP from EU JRC).
"""

import numpy as np
from scipy import ndimage


def compute_flow_direction(dem):
    """Compute D8 flow direction from a DEM.

    Parameters
    ----------
    dem : numpy.ndarray
        Digital elevation model (2D array).

    Returns
    -------
    numpy.ndarray
        Flow direction grid. Values 1-8 represent the 8 cardinal/diagonal
        directions, following the D8 algorithm (steepest descent).
    """
    h, w = dem.shape
    flow_dir = np.zeros((h, w), dtype=np.int8)

    # 8 neighbor offsets: N, NE, E, SE, S, SW, W, NW
    offsets = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]
    distances = [1, np.sqrt(2), 1, np.sqrt(2), 1, np.sqrt(2), 1, np.sqrt(2)]

    for r in range(1, h - 1):
        for c in range(1, w - 1):
            max_slope = 0
            max_dir = 0
            for d, (dr, dc) in enumerate(offsets):
                nr, nc = r + dr, c + dc
                slope = (dem[r, c] - dem[nr, nc]) / distances[d]
                if slope > max_slope:
                    max_slope = slope
                    max_dir = d + 1
            flow_dir[r, c] = max_dir

    return flow_dir


def trace_flow_path(flow_dir, start_row, start_col, max_steps=5000):
    """Trace a flow path downstream from a starting point.

    Parameters
    ----------
    flow_dir : numpy.ndarray
        D8 flow direction grid.
    start_row, start_col : int
        Starting pixel coordinates.
    max_steps : int
        Maximum path length.

    Returns
    -------
    list of tuple
        [(row, col), ...] coordinates along the flow path.
    """
    offsets = {
        1: (-1, 0),
        2: (-1, 1),
        3: (0, 1),
        4: (1, 1),
        5: (1, 0),
        6: (1, -1),
        7: (0, -1),
        8: (-1, -1),
    }

    h, w = flow_dir.shape
    path = [(start_row, start_col)]
    r, c = start_row, start_col

    for _ in range(max_steps):
        d = flow_dir[r, c]
        if d == 0:
            break
        dr, dc = offsets[d]
        r, c = r + dr, c + dc
        if r < 0 or r >= h or c < 0 or c >= w:
            break
        path.append((r, c))

    return path


def find_downstream_zone(flow_dir, lake_mask, max_distance_km=50, pixel_size_m=30):
    """Compute the downstream flood zone from a glacial lake.

    Parameters
    ----------
    flow_dir : numpy.ndarray
        D8 flow direction grid.
    lake_mask : numpy.ndarray
        Boolean mask of the glacial lake.
    max_distance_km : float
        Maximum downstream distance to consider.
    pixel_size_m : float

    Returns
    -------
    numpy.ndarray
        Boolean mask of the potential flood zone.
    """
    max_pixels = int(max_distance_km * 1000 / pixel_size_m)

    # Find lake outlet (lowest elevation point on lake boundary)
    lake_boundary = lake_mask & ~ndimage.binary_erosion(lake_mask)
    outlet_coords = np.argwhere(lake_boundary)

    if len(outlet_coords) == 0:
        return np.zeros_like(lake_mask, dtype=bool)

    # Trace flow from each boundary pixel and combine
    flood_zone = np.zeros_like(lake_mask, dtype=bool)
    for r, c in outlet_coords:
        path = trace_flow_path(flow_dir, r, c, max_steps=max_pixels)
        for pr, pc in path:
            flood_zone[pr, pc] = True

    # Buffer the flow path (floods spread laterally)
    flood_zone = ndimage.binary_dilation(flood_zone, iterations=10)

    return flood_zone


def estimate_population_at_risk(flood_zone, population_grid, pixel_size_m=30):
    """Estimate the population within the potential flood zone.

    Parameters
    ----------
    flood_zone : numpy.ndarray
        Boolean mask of flood zone.
    population_grid : numpy.ndarray
        Population count per pixel (e.g. from GHS-POP).
    pixel_size_m : float

    Returns
    -------
    dict
        Keys: total_population, n_settled_pixels, flood_zone_area_km2.
    """
    total_pop = float(np.nansum(population_grid[flood_zone]))
    n_settled = int(np.sum((population_grid > 0) & flood_zone))
    area_km2 = float(np.sum(flood_zone)) * (pixel_size_m**2) / 1e6

    return {
        "total_population": total_pop,
        "n_settled_pixels": n_settled,
        "flood_zone_area_km2": area_km2,
    }


def compute_flow_distance_km(lake_centroid, settlement_coords, dem, pixel_size_m=30):
    """Compute downstream flow distance from lake to settlement.

    Parameters
    ----------
    lake_centroid : tuple
        (row, col) of lake center.
    settlement_coords : tuple
        (row, col) of settlement.
    dem : numpy.ndarray
    pixel_size_m : float

    Returns
    -------
    float
        Flow distance in km (along the flow path, not straight-line).
    """
    flow_dir = compute_flow_direction(dem)
    path = trace_flow_path(flow_dir, lake_centroid[0], lake_centroid[1])

    # Find the path point closest to the settlement
    min_dist = np.inf
    path_length = 0

    for i, (r, c) in enumerate(path):
        if i > 0:
            prev_r, prev_c = path[i - 1]
            step_dist = np.sqrt((r - prev_r) ** 2 + (c - prev_c) ** 2) * pixel_size_m
            path_length += step_dist

        dist_to_settlement = (
            np.sqrt((r - settlement_coords[0]) ** 2 + (c - settlement_coords[1]) ** 2)
            * pixel_size_m
        )

        if dist_to_settlement < min_dist:
            min_dist = dist_to_settlement
            closest_path_length = path_length

    return closest_path_length / 1000  # Convert to km
