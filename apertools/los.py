"""Functions to deal with Line of sight vector computation
"""
from __future__ import division, print_function
import os
import numpy as np
from numpy import sin, cos
import h5py
# from scipy import interpolate

from apertools import sario

from apertools.log import get_log
import matplotlib.pyplot as plt
logger = get_log()


def find_enu_coeffs(lon, lat, geo_path=None, los_map_file=None, verbose=False):
    """For arbitrary lat/lon, find the coefficients for ENU components of LOS vector

    Args:
        lon (float): longitude of point to get LOS vector
        lat (float): latitude of point
        geo_path (str): path to the directory with the sentinel
            timeseries inversion (contains line-of-sight deformation.npy, dem.rsc,
            and has .db files one directory higher)

    Returns:
        ndarray: enu_coeffs, shape = (3,) array [alpha_e, alpha_n, alpha_up]
        Pointing from satellite to ground
        Can be used to project an ENU vector into the line of sight direction
    """

    if los_map_file is not None:
        return _read_los_map_file(los_map_file, lat, lon)


def _read_los_map_file(los_map_file, lat, lon):
    with h5py.File(los_map_file) as f:
        lats = f["lats"]
        lons = f["lons"]
        row = _find_nearest(lats, lat)
        col = _find_nearest(lons, lon)
        return f["stack"][:, row, col]


def _find_nearest(array, value):
    array = np.asarray(array)
    idx = (np.abs(array - value)).argmin()
    return array[idx]


def los_to_enu(los_file=None, lat_lons=None, xyz_los_vecs=None):
    """Converts Line of sight vectors from xyz to ENU

    Can read in the LOS vec file, or take a list `xyz_los_vecs`
    Args:
        los_file (str): file to the recorded LOS vector at lat,lon points
        lat_lons (list[tuple[float]]): list of (lat, lon) coordinares for LOS vecs
        xyz_los_vecs (list[tuple[float]]): list of xyz LOS vectors

    Notes:
        Second two args are the result of read_los_output, mutually
        exclusive with los_file

    Returns:
        ndarray: k x 3 ENU 3-vectors
    """
    # if los_file:
    # lat_lons, xyz_los_vecs = read_los_output(los_file)
    return convert_xyz_latlon_to_enu(lat_lons, xyz_los_vecs)


def convert_xyz_latlon_to_enu(lat_lons, xyz_array):
    return np.array(
        [rotate_xyz_to_enu(xyz, lat, lon) for (lat, lon), xyz in zip(lat_lons, xyz_array)])


def rotate_xyz_to_enu(xyz, lat, lon):
    """Rotates a vector in XYZ coords to ENU

    Args:
        xyz (list[float], ndarray[float]): length 3 x,y,z coordinates, either
            as list of 3, or a 3xk array of k ENU vectors
        lat (float): latitude (deg) of point to rotate into
        lon (float): longitude (deg) of point to rotate into

    Reference: https://gssc.esa.int/navipedia/index.php/\
Transformations_between_ECEF_and_ENU_coordinates

    """
    # Rotate about axis 3 with longitude, then axis 1 with latitude
    R3 = rot(90 + lon, 3, in_degrees=True)
    R1 = rot(90 - lat, 1, in_degrees=True)
    return np.matmul(R1, np.matmul(R3, xyz))


def rot(angle, axis, in_degrees=True):
    """
    Find a 3x3 euler rotation matrix given an angle and axis.

    Rotation matrix used for rotating a vector about a single axis.

    Args:
        angle (float): angle in degrees to rotate
        axis (int): 1, 2 or 3
        in_degrees (bool): specify the angle in degrees. if false, using
            radians for `angle`
    """
    R = np.eye(3)
    if in_degrees:
        angle = np.deg2rad(angle)
    cang = cos(angle)
    sang = sin(angle)
    if axis == 1:
        R[1, 1] = cang
        R[2, 2] = cang
        R[1, 2] = sang
        R[2, 1] = -sang
    elif axis == 2:
        R[0, 0] = cang
        R[2, 2] = cang
        R[0, 2] = -sang
        R[2, 0] = sang
    elif axis == 3:
        R[0, 0] = cang
        R[1, 1] = cang
        R[1, 0] = -sang
        R[0, 1] = sang
    else:
        raise ValueError("axis must be 1, 2 or 2")
    return R


def project_enu_to_los(enu, los_vec=None, lat=None, lon=None, enu_coeffs=None):
    """Find magnitude of an ENU vector in the LOS direction

    Rotates the line of sight vector to ENU coordinates at
    (lat, lon), then dots with the enu data vector

    Args:
        enu (list[float], ndarray[float]): E,N,U coordinates, either
            as list of 3, or a (3, k) array of k ENU vectors
        los_vec (ndarray[float]) length 3 line of sight, in XYZ frame
        lat (float): degrees latitude of los point
        lon (float): degrees longitude of los point
        enu_coeffs (ndarray) size 3 array of the E,N,U coefficients
        of a line of sight vector. Comes from `find_enu_coeffs`.
            If this arg is used, others are not needed

    Returns:
        ndarray: magnitudes same length as enu input, (k, 1)

    Examples:
    # >>> print('%.2f' % project_enu_to_los([1,2,3],[1, 0, 0], 0, 0))
    # -2.00
    # >>> print('%.2f' % project_enu_to_los([1,2,3],[0, 1, 0], 0, 0))
    # -3.00
    # >>> print('%.2f' % project_enu_to_los([1,2,3],[0, 0, 1], 0, 0))
    # 1.00
    """
    if enu_coeffs is None:
        los_hat = los_vec / np.linalg.norm(los_vec)
        enu_coeffs = rotate_xyz_to_enu(los_hat, lat, lon)
    return np.dot(enu_coeffs, enu)


def find_vertical_def(asc_path, desc_path):
    """Calculates vertical deformation for all points in the LOS files

    Args:
        asc_path (str): path to the directory with the ascending sentinel files
            Should contain elevation.dem.rsc, .db files, and igram folder
        desc_path (str): same as asc_path but for descending orbit
    Returns:
        tuple[ndarray, ndarray]: def_east, def_vertical, the two matrices of
            deformation separated by verticl and eastward motion
    """
    asc_path = os.path.realpath(asc_path)
    desc_path = os.path.realpath(desc_path)

    eu_asc = find_east_up_coeffs(asc_path)
    eu_desc = find_east_up_coeffs(desc_path)

    east_up_coeffs = np.vstack((eu_asc, eu_desc))
    print("East-up asc and desc:")
    print(east_up_coeffs)

    asc_igram_path = os.path.join(asc_path, 'igrams')
    desc_igram_path = os.path.join(desc_path, 'igrams')

    asc_geolist, asc_deform = sario.load_deformation(asc_igram_path)
    desc_geolist, desc_deform = sario.load_deformation(desc_igram_path)

    print(asc_igram_path, asc_deform.shape)
    print(desc_igram_path, desc_deform.shape)
    assert asc_deform.shape == desc_deform.shape, 'Asc and desc def images not same size'
    nlayers, nrows, ncols = asc_deform.shape
    # Stack and solve for the East and Up deformation
    d_asc_desc = np.vstack([asc_deform.reshape(-1), desc_deform.reshape(-1)])
    dd = np.linalg.solve(east_up_coeffs, d_asc_desc)
    def_east = dd[0, :].reshape((nlayers, nrows, ncols))
    def_vertical = dd[1, :].reshape((nlayers, nrows, ncols))
    return def_east, def_vertical


def merge_geolists(geolist1, geolist2):
    """Task asc and desc geolists, makes one merged

    Gives the overlap indices of the merged list for each smaller

    """
    merged_geolist = np.concatenate((geolist1, geolist2))
    merged_geolist.sort()

    _, indices1, _ = np.intersect1d(merged_geolist, geolist1, return_indices=True)
    _, indices2, _ = np.intersect1d(merged_geolist, geolist2, return_indices=True)
    return merged_geolist, indices1, indices2


def plot_enu_maps(enu_ll, title=None, cmap='jet'):
    fig, axes = plt.subplots(1, 3)

    titles = ['east', 'north', 'up']
    for idx in range(3):
        axim = axes[idx].imshow(np.abs(enu_ll[idx]), vmin=0, vmax=1, cmap=cmap)
        axes[idx].set_title(titles[idx])

    fig.subplots_adjust(right=0.8)
    cbar_ax = fig.add_axes([0.85, 0.15, 0.05, 0.7])
    fig.colorbar(axim, cax=cbar_ax)
    fig.suptitle(title)
