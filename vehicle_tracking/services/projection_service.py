"""
Mandatory metric projection service for forensic vehicle tracking.

This module provides metric projection setup that ensures speed calculations
EXACTLY match interpolated geometry. No Haversine fallbacks allowed.
"""

from typing import Tuple, Optional, Callable, Dict, Any
import logging

# Check for pyproj availability
HAS_PYPROJ = False
try:
    import pyproj
    HAS_PYPROJ = True
except ImportError:
    # This should be a critical error in production
    logging.critical("pyproj not available - forensic accuracy cannot be guaranteed")

from ..models.vehicle_tracking_models import GPSPoint


def make_local_metric_projection(
    center_point: GPSPoint
) -> Tuple[Optional[Callable], Optional[Callable]]:
    """
    Create mandatory metric projection for forensic accuracy.

    Uses Azimuthal Equidistant (AEQD) projection centered on data.
    This ensures speed calculations EXACTLY match interpolated geometry.
    No more Haversine/projection mismatches.

    Args:
        center_point: GPS point at center of data (typically middle point)

    Returns:
        Tuple of (to_metric, to_wgs84) transformer functions

    Raises:
        ValueError: If pyproj is not available or projection creation fails
                   (metric projection is MANDATORY for forensic accuracy)

    Note:
        AEQD projection is accurate within ~100km radius of center point.
        For larger areas, consider UTM or other appropriate projections.
    """
    if not HAS_PYPROJ:
        raise ValueError(
            "pyproj is required for forensic speed calculation. "
            "Install with: pip install pyproj>=3.6.0"
        )

    try:
        # Define AEQD projection centered on track
        aeqd = pyproj.CRS.from_proj4(
            f"+proj=aeqd "
            f"+lat_0={center_point.latitude} "
            f"+lon_0={center_point.longitude} "
            f"+datum=WGS84 "
            f"+units=m "
            f"+no_defs"
        )

        # WGS84 (standard GPS coordinate system)
        wgs84 = pyproj.CRS.from_epsg(4326)

        # Create transformers
        # always_xy=True ensures (longitude, latitude) order
        to_metric = pyproj.Transformer.from_crs(
            wgs84, aeqd, always_xy=True
        ).transform

        to_wgs84 = pyproj.Transformer.from_crs(
            aeqd, wgs84, always_xy=True
        ).transform

        # Verify transformers work (sanity check)
        test_x, test_y = to_metric(center_point.longitude, center_point.latitude)
        test_lon, test_lat = to_wgs84(test_x, test_y)

        # Center point should transform to (0, 0) in AEQD
        if abs(test_x) > 1.0 or abs(test_y) > 1.0:
            logging.warning(
                f"AEQD center point transformed to ({test_x}, {test_y}), "
                "expected near (0, 0)"
            )

        # Round-trip should preserve coordinates
        if abs(test_lon - center_point.longitude) > 1e-6 or \
           abs(test_lat - center_point.latitude) > 1e-6:
            logging.warning(
                f"Projection round-trip error: "
                f"({center_point.longitude}, {center_point.latitude}) -> "
                f"({test_lon}, {test_lat})"
            )

        return to_metric, to_wgs84

    except Exception as e:
        # This should never fail in production
        # Metric projection is MANDATORY for forensic accuracy
        raise ValueError(f"Failed to create mandatory metric projection: {e}")


def get_utm_projection(
    center_point: GPSPoint
) -> Tuple[Optional[Callable], Optional[Callable]]:
    """
    Create UTM projection as alternative to AEQD.

    UTM provides better accuracy for larger areas than AEQD.

    Args:
        center_point: GPS point for determining UTM zone

    Returns:
        Tuple of (to_metric, to_wgs84) transformer functions

    Raises:
        ValueError: If projection creation fails
    """
    if not HAS_PYPROJ:
        raise ValueError("pyproj is required for UTM projection")

    try:
        # Calculate UTM zone from longitude
        zone = int((center_point.longitude + 180) / 6) + 1

        # Determine hemisphere
        hemisphere = 'north' if center_point.latitude >= 0 else 'south'

        # Create UTM CRS
        utm = pyproj.CRS.from_string(
            f"+proj=utm +zone={zone} +{hemisphere} +datum=WGS84"
        )

        wgs84 = pyproj.CRS.from_epsg(4326)

        # Create transformers
        to_metric = pyproj.Transformer.from_crs(
            wgs84, utm, always_xy=True
        ).transform

        to_wgs84 = pyproj.Transformer.from_crs(
            utm, wgs84, always_xy=True
        ).transform

        return to_metric, to_wgs84

    except Exception as e:
        raise ValueError(f"Failed to create UTM projection: {e}")


def select_best_projection(
    points: list[GPSPoint],
    area_threshold_km: float = 100.0
) -> Tuple[Callable, Callable, str]:
    """
    Select the best projection based on data extent.

    Args:
        points: List of GPS points to analyze
        area_threshold_km: Threshold for choosing between AEQD and UTM

    Returns:
        Tuple of (to_metric, to_wgs84, projection_name)

    Raises:
        ValueError: If no suitable projection can be created
    """
    if not points:
        raise ValueError("No points provided for projection selection")

    # Calculate data extent
    min_lat = min(p.latitude for p in points)
    max_lat = max(p.latitude for p in points)
    min_lon = min(p.longitude for p in points)
    max_lon = max(p.longitude for p in points)

    # Calculate approximate extent in km (rough estimation)
    lat_extent_km = (max_lat - min_lat) * 111  # 1 degree lat ≈ 111 km
    lon_extent_km = (max_lon - min_lon) * 111 * \
                    abs(math.cos(math.radians((min_lat + max_lat) / 2)))

    max_extent_km = max(lat_extent_km, lon_extent_km)

    # Choose center point
    center_lat = (min_lat + max_lat) / 2
    center_lon = (min_lon + max_lon) / 2
    center_point = GPSPoint(
        latitude=center_lat,
        longitude=center_lon,
        timestamp=points[0].timestamp  # Dummy timestamp
    )

    # Select projection based on extent
    if max_extent_km <= area_threshold_km:
        # Use AEQD for smaller areas (better for local accuracy)
        to_metric, to_wgs84 = make_local_metric_projection(center_point)
        projection_name = f"AEQD centered at ({center_lat:.4f}, {center_lon:.4f})"
    else:
        # Use UTM for larger areas
        to_metric, to_wgs84 = get_utm_projection(center_point)
        zone = int((center_lon + 180) / 6) + 1
        projection_name = f"UTM Zone {zone}"

    logging.info(
        f"Selected {projection_name} for area extent ~{max_extent_km:.1f} km"
    )

    return to_metric, to_wgs84, projection_name


def create_projection_cache() -> Dict[str, Any]:
    """
    Create a cache for projection transformers.

    Useful when processing multiple vehicles in the same area.

    Returns:
        Dictionary to store projection transformers
    """
    return {
        'projections': {},  # Key: (center_lat, center_lon), Value: (to_metric, to_wgs84)
        'hits': 0,
        'misses': 0,
        'max_cache_size': 100
    }


def get_cached_projection(
    cache: Dict[str, Any],
    center_point: GPSPoint,
    tolerance: float = 0.01  # ~1km tolerance
) -> Tuple[Optional[Callable], Optional[Callable]]:
    """
    Get projection from cache or create new one.

    Args:
        cache: Projection cache dictionary
        center_point: Center point for projection
        tolerance: Tolerance in degrees for cache hits

    Returns:
        Tuple of (to_metric, to_wgs84) transformer functions
    """
    # Check cache for nearby projections
    for (cached_lat, cached_lon), transformers in cache['projections'].items():
        if (abs(cached_lat - center_point.latitude) < tolerance and
            abs(cached_lon - center_point.longitude) < tolerance):
            cache['hits'] += 1
            return transformers

    # Cache miss - create new projection
    cache['misses'] += 1
    to_metric, to_wgs84 = make_local_metric_projection(center_point)

    # Add to cache (with size limit)
    if len(cache['projections']) >= cache['max_cache_size']:
        # Remove oldest entry (simple FIFO)
        oldest_key = next(iter(cache['projections']))
        del cache['projections'][oldest_key]

    cache_key = (center_point.latitude, center_point.longitude)
    cache['projections'][cache_key] = (to_metric, to_wgs84)

    return to_metric, to_wgs84


# Import math for calculations
import math