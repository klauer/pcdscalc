"""Module for Beryllium Lens Calculations."""
import json
import logging
import os
import shutil
from datetime import date
from itertools import chain, product

import numpy as np
import xraydb as xdb

logger = logging.getLogger(__name__)

# Constant for converting between FWHM and sigma of a Gaussian function.
FWHM_SIGMA_CONVERSION = 2.35482004503
# Constant for converting between wavelength and photon energy.
WAVELENGTH_PHOTON = 1.2398
# Path the the lens_set file. Users shuld use :meth:`configure_lens_set_file`
# to configure it to the correct path
LENS_SET_FILE = None

# full width at half maximum unfocused
FWHM_UNFOCUSED = 500e-6
# Disk Thickness
DISK_THICKNESS = 1.0e-3
# Apex of the lens
APEX_DISTANCE = 30e-6
# Distance from the lenses to the sample
DISTANCE = 4.0
# Atomic symbol for element, defaults to 'Be'
MATERIAL = 'Be'
# Set of Be lenses with thicknesses.
LENS_RADII = [50e-6, 100e-6, 200e-6, 300e-6,
              500e-6, 1000e-6, 1500e-6, 2000e-6, 3000e-6]


def configure_defaults(fwhm_unfocused=None, disk_thickness=None,
                       apex_distance=None, distance=None,
                       material=None, lens_radii=None):
    """
    Configure defaults.

    Parameters
    -----------
    fwhm_unfocused : float, optional
        Full width at half maximum unfocused
    disk_thickness : float, optional
    apex_distance : float, optional
    distance : float, optional
        Distance from the lenses to the sample
    material : str, optional
        Atomic symbol for element, defaults to 'Be'
    lens_radii : list
         Set of Be lenses with thicknesses.

    Examples
    --------
    >>> configure_defaults(distance=3.852)
    """
    global FWHM_UNFOCUSED
    global DISK_THICKNESS
    global APEX_DISTANCE
    global DISTANCE
    global MATERIAL
    global LENS_RADII

    FWHM_UNFOCUSED = fwhm_unfocused or FWHM_UNFOCUSED
    DISK_THICKNESS = disk_thickness or DISK_THICKNESS
    APEX_DISTANCE = apex_distance or APEX_DISTANCE
    DISTANCE = distance or DISTANCE
    MATERIAL = material or MATERIAL
    LENS_RADII = lens_radii or LENS_RADII


def configure_lens_set_file(lens_file_path):
    """
    Configure the path to the lens set file.

    Parameters
    ----------
    lens_file_path : str
        Path to the lens_set file.
    """
    global LENS_SET_FILE
    if not os.path.exists(lens_file_path):
        err_msg = ('Provided invalid path for lens set file: %s',
                   lens_file_path)
        logger.error(err_msg)
        raise FileNotFoundError(err_msg)
    LENS_SET_FILE = os.path.abspath(lens_file_path)
    return LENS_SET_FILE


def photon_to_wavelength(energy):
    """
    Find the wavelength in micrometers.

    Use photon energy in electronvolts. The equation is approximately: λ[µm] =
    1.2398 / E[eV]. The photon energy at 1 μm wavelength, the wavelength of
    near infrared radiation, is approximately 1.2398 eV.

    Parameters
    ----------
    energy : number
        Photon energy in electronvolts

    Returns
    -------
    Wavelength in micrometers

    Examples
    --------
    >>> photon_to_wavelength(8)
    0.154975
    """
    return WAVELENGTH_PHOTON / energy


def gaussian_sigma_to_fwhm(sigma):
    """
    Convert between FWHM and sigma of a Gaussian function.

    FWHM = 2.35482004503 * sigma

    https://brainder.org/2011/08/20/gaussian-kernels-convert-fwhm-to-sigma/

    Parameters
    ----------
    sigma : float

    Returns
    -------
    FWHM -  Full Width at the Half Maximum

    Examples
    --------
    >>> gaussian_sigma_to_fwhm(0.3)
    0.7064460135089999
    """
    return FWHM_SIGMA_CONVERSION * sigma


def gaussian_fwhm_to_sigma(fwhm):
    """
    Convert between FWHM and sigma of a Gaussian function.

    sigma = FWHM / 2.35482004503

    https://brainder.org/2011/08/20/gaussian-kernels-convert-fwhm-to-sigma/

    Parameters
    ----------
    fwhm : float
        Full Width at the Half Maximum

    Returns
    -------
    sigma

    Examples
    --------
    >>> gaussian_fwhm_to_sigma(0.023)
    0.009767200703316157
    """
    return fwhm / FWHM_SIGMA_CONVERSION


def get_lens_set(set_number_top_to_bot, filename=None):
    """
    Get the lens set from the file provided.

    Parameters
    ----------
    set_number_top_to_bot : int
        The Be lens holders can take 3 different sets that we usually set
        before experiments, this is to specify what number set.
    filename : str, optional
        File path of the lens_set file.

    Returns
    -------
    lens_set : list
        [numer1, lensthick1, number2, lensthick2 ...]
    """
    if filename is None and LENS_SET_FILE is None:
        err_msg = ('You must provide the path to the lens_set file or you '
                   'must configure it via configure_lens_set_file function')
        logger.error(err_msg)
        raise ValueError(err_msg)
    elif filename is None:
        filename = LENS_SET_FILE
    if not os.path.exists(filename):
        err_msg = ('Provided invalid path for lens set file: %s', filename)
        logger.error(err_msg)
        raise FileNotFoundError(err_msg)
    if os.stat(filename).st_size == 0:
        err_msg = ('The file is empyt: %s, use set_lens_set_to_file to write '
                   'set lenses to the file.', filename)
        logger.error(err_msg)
        raise ValueError(err_msg)
    with open(filename) as lens_file:
        try:
            sets = json.loads(lens_file.read())
        except json.decoder.JSONDecodeError as err:
            logger.error('When getting the lens set: %s', err)
            raise err

        if set_number_top_to_bot not in range(1, len(sets)):
            err_msg = ('Provided an invalid set_number_top_to_bottom %s,'
                       'please provide a number from 1 to %s ',
                       set_number_top_to_bot, len(sets))
            logger.error(err_msg)
            raise ValueError(err_msg)
    # if only one set in the list, return the list
    if not isinstance(sets[0], list):
        return sets
    else:
        return sets[set_number_top_to_bot - 1]


def set_lens_set_to_file(list_of_sets, filename,
                         make_backup=True):
    """
    Write lens set to a file.

    The Be lens holders can take 3 different sets that we usually set before
    few experiments so we only vent the relevant beamline section once. We then
    store these sets into a config file that we can call from some methods.
    Later, we save this config file to the specific experiment so users can
    make sure that they know which stack was used for there beamtime.

    Parameters
    ----------
    list_of_sets : list
        List of lists with lens sets
    filename : str, optional
        Path to the filename to set the lens sets list to.
        This should be a .npy format file.
    make_backup : bool, optional
        To indicate if a backup file should be created or not.
        Defaults to `True`.

    Examples
    --------
    >>> list_of_sets = [[3, 0.0001, 1, 0.0002],
                        [1, 0.0001, 1, 0.0003, 1, 0.0005],
                        [2, 0.0001, 1, 0.0005]]
    >>> set_lens_set_to_file(list_of_sets, '../path/to/lens_set')
    """
    if filename is None and LENS_SET_FILE is None:
        logger.error('You must provide the path to the lens_set file or you '
                     'must configure it via :meth: `configure_lens_set_file`')
        return
    elif filename is None:
        filename = LENS_SET_FILE
    # Make a backup with today's date.
    if make_backup:
        backup_path = filename + str(date.today()) + '.bak'
        try:
            shutil.copyfile(filename, backup_path)
        except Exception as ex:
            logger.error('Something went wrong with copying the file %s', ex)
            pass
    with open(filename, 'w') as lens_file:
        try:
            lens_file.write(json.dumps(list_of_sets))
        except json.decoder.JSONDecodeError as err:
            logger.error('Something went wrong when writing lens set to the '
                         'file %s', err)
            raise err


def get_att_len(energy, material=None, density=None):
    """
    Get the attenuation length (in meter) of a material.

    The X-ray beam intensity I(x) at depth x in a material is a function of the
    attenuation coefficient mu, and can be calculated by the Beer-Lambert law.
    The Absorption Length (or Attenuation Length) is defined as the distance
    into a material where the x-ray beam intensity has decreased to a value of
    1/e (~ 40%) of the incident beam intensity (Io).

    (1/e) = e^(-mu * x)
    ln(1/e) = ln(e^(-mu * x))
    1 = mu * x
    x = 1/mu

    Parameters
    ----------
    energy : number
        Beam Energy given in KeV
    material : str, optional
        Atomic symbol for element, defaults to 'Be'
    density : float, optional
        Material density in g/cm^3

    Returns
    -------
    att_len : float
        Attenuation length

    Raises
    ------
    ValueError
        If an invalid symbol is provided for material.

    Examples
    --------
    >>> get_att_len(energy=8, material='Be')
    0.004810113254120656
    """
    material = material or MATERIAL
    density = density or xdb.atomic_density(material)
    try:
        # xdb.material_my returns absorption length in 1/cm and takes energy
        # or array of energies in eV.
        att_len = 1.0 / (xdb.material_mu(material, energy * 1.0e3,
                                         density=density)) * 1.0e-2
    except Exception as ex:
        logger.error('Get Attenuation Length error: %s', ex)
        raise ex
    return att_len


def get_delta(energy, material=None, density=None):
    """
    Calculate delta for a given material at a given energy.

    Anomalous components of the index of refraction for a material, using the
    tabulated scattering components from Chantler.

    Parameters
    ----------
    energy : number
        x-ray energy in KeV
    material : str, optional
        Atomic symbol for element, defaults to 'Be'.
    density : float, optional
        Material density in g/cm^3

    Returns
    -------
    delta : float
        Real part of index of refraction

    Raises
    ------
    ValueError
        If an invalid symbol is provided for material.
    ZeroDivisionError
        When energy is 0.

    Examples
    --------
    >>> get_delta(energy=8, material='Au')
    4.728879989419882e-05
    """
    material = material or MATERIAL
    # xray_delta_beta returns (delta, beta, atlen), wehre delta : real part of
    # index of refraction, and takes x-ray energy in eV.
    if density is None:
        density = xdb.atomic_density(material)
    try:
        delta = xdb.xray_delta_beta(material,
                                    density=density,
                                    energy=energy * 1.0e3)[0]
    except Exception as ex:
        logger.error('Get Delta error: %s', ex)
        raise ex
    return delta


def calc_focal_length_for_single_lens(energy, radius, material=None,
                                      density=None):
    """
    Calculate the Focal Length for a single lens.

    Parameters
    ----------
    energy : number
        Beam Energy
    radius : float
    material : str, optional
        Atomic symbol for element, defaults to 'Be'.
    density : float, optional
        Material density in g/cm^3

    Returns
    -------
    focal_length : float
        The focal length for a single lens

    Examples
    --------
    >>> calc_focal_length_for_single_lens(8, 0.03, 'Be')
    2814.0101061895903
    """
    material = material or MATERIAL

    delta = get_delta(energy, material, density)
    focal_length = radius / 2.0 / delta
    return focal_length


def calc_focal_length(energy, lens_set, material=None, density=None):
    """
    Calculate the Focal Length for certain lenses configuration and energy.

    Parameters
    ----------
    energy : number
        Beam Energy
    lens_set : list
        [numer1, lensthick1, number2, lensthick2 ...]
    material : str, optional
        Atomic symbol for element, defaults to 'Be'.
    density : float, optional
        Material density in g/cm^3

    Returns
    -------
    focal_length : float

    Examples
    --------
    >>> calc_focal_length(8, [1, 0.3, 2, 0.4], 'Be')
    11256.040424758363
    """
    material = material or MATERIAL

    f_tot_inverse = 0
    if isinstance(lens_set, int):
        try:
            lens_set = get_lens_set(lens_set)
        except Exception as ex:
            logger.error('When calling get_lens_set error occurred: %s', ex)
            raise ex
    lens_set = (list(zip(lens_set[::2], lens_set[1::2])))
    for num, radius in lens_set:
        if radius is not None:
            fln = calc_focal_length_for_single_lens(energy, radius,
                                                    material, density)
            f_tot_inverse += num/fln

    return 1.0 / f_tot_inverse


def calc_beam_fwhm(energy, lens_set, distance=None, source_distance=None,
                   material=None, density=None,
                   fwhm_unfocused=None, printsummary=True):
    """
    Calculate beam Full Width at the Half Maximum.

    Calculate beam parameters for certain lenses configuration and energy at a
    given distance. FWHM -  Full Width at the Half Maximum Optionally some
    other parameters can be set.

    Parameters
    ----------
    energy : number
        Beam Energy
    lens_set : list
        [numer1, lensthick1, number2, lensthick2...]
    distance : float
        Distance from the lenses to the sample is 3.852 m at XPP.
    source_distance : float, optional
        Distance from source to lenses. This is about 160 m at XPP.
    material : str, optional
        Atomic symbol for element, defaults to 'Be'.
    density : float, optional
        Material density in g/cm^3
    fwhm_unfocused : float, optional
        This is about 400 microns at XPP.
        This is about 900 microns at MEC.
    printsummary : bool, optional
        Prints summary of parameters/calculations if `True`.

    Returns
    -------
    size_fwhm : float

    Examples
    --------
    >>> calc_beam_fwhm(energy=9, lens_set=[2, 0.03, 4, 0.002], distance=4,
                       material='Be', fwhm_unfocused=800e-6)
    0.0008373516816325981
    """
    fwhm_unfocused = fwhm_unfocused or FWHM_UNFOCUSED
    distance = distance or DISTANCE
    material = material or MATERIAL
    # Focal length for certain lenses configuration and energy.
    focal_length = calc_focal_length(energy, lens_set, material, density)

    # Use lens makers equation to find distance to image of source.
    if source_distance is not None:
        focal_length = 1 / (1 / focal_length - 1 / source_distance)

    lam = photon_to_wavelength(energy) * 1e-9

    # The w parameter used in the usual formula is 2 * sigma.
    w_unfocused = gaussian_fwhm_to_sigma(fwhm_unfocused) * 2

    # Assuming gaussian beam divergence = w_unfocused/f we can obtain.
    waist = lam / np.pi * focal_length / w_unfocused
    rayleigh_range = np.pi * waist ** 2 / lam
    size = waist * np.sqrt(1.0 + (distance - focal_length) ** 2.0
                           / rayleigh_range ** 2)

    size_fwhm = gaussian_sigma_to_fwhm(size) / 2.0

    if printsummary:
        logger.info("FWHM at lens   : %.3e" % (fwhm_unfocused))
        logger.info("waist          : %.3e" % (waist))
        logger.info("waist FWHM     : %.3e" % (waist
                                               * FWHM_SIGMA_CONVERSION / 2.0))
        logger.info("rayleigh_range : %.3e" % (rayleigh_range))
        logger.info("focal length   : %.3e" % (focal_length))
        logger.info("size           : %.3e" % (size))
        logger.info("size FWHM      : %.3e" % (size_fwhm))

    return size_fwhm


def calc_distance_for_size(size_fwhm, lens_set, energy,
                           fwhm_unfocused=None):
    """
    Calculate the distance for size.

    Parameters
    ----------
    size_fwhm : float
    lens_set : list
        [numer1, lensthick1, number2, lensthick2...]
    energy : number
        Beam Energy
    fwhm_unfocused : float, optional
        This is about 400 microns at XPP

    Returns
    -------
    distance : float

    Examples
    --------
    >>> calc_distance_for_size(0.023, [2, 0.03, 4, 0.002], 8, 0.078)
    array([32.00383702, 58.77068253])
    """
    fwhm_unfocused = fwhm_unfocused or FWHM_UNFOCUSED

    size = gaussian_fwhm_to_sigma(size_fwhm) * 2.0
    focal_length = calc_focal_length(energy, lens_set, 'Be', density=None)

    lam = photon_to_wavelength(energy) * 1e-9

    # The w parameter used in the usual formula is 2 * sigma.
    w_unfocused = gaussian_fwhm_to_sigma(fwhm_unfocused) * 2.0

    # Assuming gaussian beam divergence = w_unfocused/f we can obtain.
    waist = lam / np.pi * focal_length / w_unfocused
    rayleigh_range = np.pi * waist ** 2 / lam

    distance = (np.sqrt((size / waist) ** 2 - 1) * np.asarray([-1.0, 1.0])
                * rayleigh_range) + focal_length

    return distance


def calc_lens_aperture_radius(radius, disk_thickness=None,
                              apex_distance=None):
    """
    Calculate the lens aperture radius.

    It is of importance to optimize which lens radius to use at a specific
    photon energy.

    Parameters
    ----------
    radius : float
    disk_thickness : float, optional
        Defaults to 1.0e-3
    apex_distance : float, optional
        Defaults to 30e-6

    Returns
    -------
    aperture_radius : float

    Examples
    --------
    >>> calc_lens_aperture_radius(radius=4.0, disk_thickness=1e-3,
                                  apex_distance=30e-6)
    0.06228964600958975
    """
    disk_thickness = disk_thickness or DISK_THICKNESS
    apex_distance = apex_distance or APEX_DISTANCE

    aperture_radius = np.sqrt(radius * (disk_thickness - apex_distance))
    return aperture_radius


def calc_trans_for_single_lens(energy, radius, material=None, density=None,
                               fwhm_unfocused=None,
                               disk_thickness=None,
                               apex_distance=None):
    """
    Calculate the transmission for a single lens.

    Parameters
    ----------
    energy : number
        Beam Energy
    radius : float
    material : str, optional
        Atomic symbol for element, defaults to 'Be'.
    density : float, optional
        Material density in g/cm^3
    fwhm_unfocused : float, optional
        This is about 400 microns at XPP.
    disk_thickness : float, optional
        Defaults to 1.0e-3
    apex_distance : float, optional
        Defaults to 30e-6

    Returns
    -------
    transmission : float
        Transmission for a single lens

    Examples
    --------
    >>> calc_trans_for_single_lens(energy=8, radius=0.03, material='Be',
                                   density=None, fwhm_unfocused=800e-6,
                                   disk_thickness=1.0e-3, apex_distance=30e-6)
    0.9921954096643786
    """
    material = material or MATERIAL
    fwhm_unfocused = fwhm_unfocused or FWHM_UNFOCUSED
    disk_thickness = disk_thickness or DISK_THICKNESS
    apex_distance = apex_distance or APEX_DISTANCE

    # mu = mass attenuation coefficient?
    mu = 1.0 / get_att_len(energy, material=material, density=None)

    sigma = gaussian_fwhm_to_sigma(fwhm_unfocused)
    # TODO: what is S - Responsivity of a lens?
    S = (sigma ** (-2.0) + 2.0 * mu / radius) ** (-0.5)
    aperture_radius = calc_lens_aperture_radius(radius=radius,
                                                disk_thickness=disk_thickness,
                                                apex_distance=apex_distance)

    transmission = ((S ** 2 / sigma ** 2) * np.exp(-mu * apex_distance)
                    * (1 - np.exp(-(aperture_radius ** 2.0) / (2.0 * S ** 2))))
    return transmission


def calc_trans_lens_set(energy, lens_set, material=None, density=None,
                        fwhm_unfocused=None,
                        disk_thickness=None,
                        apex_distance=None):
    """
    Calculate  the transmission of a lens set.

    These would allow us to estimate the total transmission of the lenses TODO:
    where is this document is this message below still relevant?  There is
    latex document that explains the formula.  Can be adapted to use different
    thicknesses for each lens, and different apex distances, but this would
    require changing the format of lens_set, which would mean changing a whole
    bunch of other programs too.

    Parameters
    ----------
    energy : number
        Beam Energy
    lens_set : list
        [numer1, lensthick1, number2, lensthick2...]
    material : str, optional
        Atomic symbol for element, defaults to 'Be'.
    density : float, optional
        Material density in g/cm^3
    fwhm_unfocused : float, optional
        This is about 400 microns at XPP. Default = 900e-6
    disk_thickness : float, optional
        Defaults to 1.0e-3
    apex_distance : float, optional
        Defaults to 30e-6

    Returns
    -------
    transmission : float
        Transmission for a set of lens

    Examples
    --------
    >>> calc_trans_lens_set(energy=8, lens_set=[1, 0.03, 4, 0.02],
                            material='Be', density=None,
                            fwhm_unfocused=400e-6)
    0.955752311215339
    """
    material = material or MATERIAL
    fwhm_unfocused = fwhm_unfocused or FWHM_UNFOCUSED
    disk_thickness = disk_thickness or DISK_THICKNESS
    apex_distance = apex_distance or APEX_DISTANCE

    apex_distance_tot = 0
    radius_total_inv = 0
    if isinstance(lens_set, int):
        try:
            lens_set = get_lens_set(lens_set)
        except Exception as ex:
            logger.error('When calling get_lens_set error occurred: %s', ex)
            raise ex
    lens_set = (list(zip(lens_set[::2], lens_set[1::2])))

    radius_total_inv = sum(num / radius for num, radius in lens_set)
    apex_distance_tot = sum(num * apex_distance for num, _ in lens_set)
    radius_aperture = min(np.sqrt(radius * (disk_thickness - apex_distance))
                          for _, radius in lens_set)

    radius_total = 1.0 / radius_total_inv
    equivalent_disk_thickness = (radius_aperture ** 2 / radius_total
                                 + apex_distance_tot)

    transmission_total = calc_trans_for_single_lens(energy, radius_total,
                                                    material, density,
                                                    fwhm_unfocused,
                                                    equivalent_disk_thickness,
                                                    apex_distance_tot)
    return transmission_total


def calc_lens_set(energy, size_fwhm, distance, n_max=25, max_each=5,
                  lens_radii=None,
                  fwhm_unfocused=None, eff_rad0=None):
    """
    Calculate lens set.

    Parameters
    ----------
    energy : number
        Beam Energy
    size_fwhm : float
    distance : float
    n_max : int, optional
    max_each : int, optional
    lens_radii : list, optional
    fwhm_unfocused : float, optional
        This is about 400 microns at XPP. Defaults to 500e-6.
    eff_rad0 : float, optional

    Returns
    -------
    lens_sets : tuple
        Lens sets

    Examples
    --------
    >>> calc_lens_set(energy=7, size_fwhm=0.54, distance=3)
    """
    lens_radii = lens_radii or LENS_RADII
    fwhm_unfocused = fwhm_unfocused or FWHM_UNFOCUSED

    nums = product(*([list(range(max_each + 1))] * len(lens_radii)))
    sets = []
    sizes = []
    eff_rads = []
    foc_lens = []
    for num in nums:
        lens_set = []
        if sum(num) <= n_max and sum(num) > 0:
            if eff_rad0 is None:
                teff_rad_inv = 0
            else:
                teff_rad_inv = 1 / eff_rad0
            for tn, tl in zip(num, lens_radii):
                lens_set += [tn, tl]
                teff_rad_inv += tn / tl
            teff_rad = np.round(1 / teff_rad_inv, 6)
            if teff_rad in eff_rads:
                ind = eff_rads.index(teff_rad)
                if sum(sets[ind]) > sum(num):
                    sets[ind] = num
                else:
                    continue
            else:
                eff_rads.append(teff_rad)
                sets.append(num)
                sizes.append(calc_beam_fwhm(energy, lens_set + [1, eff_rad0],
                                            distance=distance,
                                            source_distance=None,
                                            fwhm_unfocused=fwhm_unfocused,
                                            printsummary=False))
                foc_lens.append(calc_focal_length(energy,
                                                  lens_set + [1, eff_rad0]))

    sizes = np.asarray(sizes)
    sets = np.asarray(sets)
    foc_lens = np.asarray(foc_lens)
    indsort = (np.abs(sizes - size_fwhm)).argsort()

    lens_sets = (sets[indsort, :],
                 np.asarray(eff_rads)[indsort],
                 sizes[indsort],
                 foc_lens[indsort])
    return lens_sets


def find_radius(energy, distance=None, material=None, density=None):
    """
    Find the radius of curvature.

    Find the radius of curvature of the lens that would focus the energy at the
    distance.

    Parameters
    ----------
    energy : number
        Beam Energy
    distance : float, optional
    material : str, optional
        Atomic symbol for element, defaults to 'Be'.
    density : float, optional
        Material density in g/cm^3

    Returns
    -------
    radius : float

    Examples
    --------
    >>> find_radius(energy=8, distance=4.0, material='Be', density=None)
    4.2643770090253954e-05
    """
    distance = distance or DISTANCE
    material = material or MATERIAL

    delta = get_delta(energy, material, density)
    radius = distance * 2 * delta
    return radius


def find_energy(lens_set, distance=None, material=None, density=None):
    """
    Find the energy that would focus at a given distance.

    Parameters
    ----------
    lens_set : list
        [numer1, lensthick1, number2, lensthick2...]
    distance : float, optional
    material : str, optional
        Atomic symbol for element, defaults to 'Be'.
    density : float, optional
        Material density in g/cm^3

    Returns
    -------
    energy : float
        Energy

    Examples
    --------
    >>> find_energy([2, 200e-6, 4, 500e-6], distance=4)
    7.0100555419921875
    """
    distance = distance or DISTANCE
    material = material or MATERIAL

    energy_min = 1.0
    energy_max = 24.0
    energy = (energy_max + energy_min) / 2.0
    abs_diff = 100
    while abs_diff > 0.0001:
        focal_length_min = calc_focal_length(energy_min, lens_set,
                                             material, density)
        focal_length_max = calc_focal_length(energy_max, lens_set,
                                             material, density)
        energy = (energy_max + energy_min) / 2.0
        focal_length = calc_focal_length(energy, lens_set, material, density)
        if (distance < focal_length_max) and (distance > focal_length):
            energy_min = energy
        elif (distance > focal_length_min) and (distance < focal_length):
            energy_max = energy
        else:
            logger.error("somehow failed ...")
            break
        abs_diff = abs(distance - focal_length)
    logger.info("Energy that would focus at a distance of %.3f is %.3f",
                distance, energy)

    return energy


def find_z_pos(energy, lens_set, spot_size_fwhm, material=None,
               density=None, fwhm_unfocused=None):
    """
    Find the Be Lens distances.

    Find the two distances the Be lens needs to be at to get the spotsize in
    the chamber center.

    Parameters
    ----------
    energy : number
        Beam Energy
    lens_set : list
        [numer1, lensthick1, number2, lensthick2...]
    spot_size_fwhm :
    material : str, optional
        Atomic symbol for element, defaults to 'Be'.
    density : float, optional
        Material density in g/cm^3
    fwhm_unfocused : float, optional
        This is about 400 microns at XPP. Defaults to 500e-6

    Returns
    -------
    z_position : tuple
        (z1, z2)

    Examples
    --------
    >>> lens_set = [2, 200e-6, 4, 500e-6]
    >>> find_z_pos(energy=8, lens_set=lens_set, spot_size_fwhm=0.09,
                   material='Be', density=None, fwhm_unfocused=800e-6)
    (-2339.797291538794, 2350.2195511913483)
    """
    material = material or MATERIAL
    fwhm_unfocused = fwhm_unfocused or FWHM_UNFOCUSED

    focal_length = calc_focal_length(energy, lens_set, material, density)

    lam = photon_to_wavelength(energy) * 1e-9
    # The w parameter used in the usual formula is 2 * sigma.
    w_unfocused = gaussian_fwhm_to_sigma(fwhm_unfocused) * 2
    waist = lam / np.pi * focal_length / w_unfocused
    rayleigh_range = np.pi * waist ** 2 / lam

    logger.info("waist          : %.3e" % waist)
    logger.info("waist FWHM     : %.3e" % (waist
                                           * FWHM_SIGMA_CONVERSION / 2.0))
    logger.info("rayleigh_range : %.3e" % rayleigh_range)
    logger.info("focal length   : %.3e" % focal_length)

    w = gaussian_fwhm_to_sigma(spot_size_fwhm) * 2
    delta_z = rayleigh_range * np.sqrt((w / waist) ** 2 - 1)
    z1 = focal_length - delta_z
    z2 = focal_length + delta_z
    z_position = (z1, z2)
    return z_position


def plan_set(energy, z_offset, z_range, beam_size_unfocused, size_horizontal,
             size_vertical=None, exclude=[], max_tot_number_of_lenses=25,
             max_each=5, focus_before_sample=False):
    """
    Macro to help plan for what lens set to use.

    Parameters
    ----------
    energy : number
    z_offset : float
    z_range : list
    beam_size_unfocused : float
    size_horiz
    size_vert
    excluede : list
    max_tot_number_of_lenses : int
    max_each : int
    focus_before_sample : bool
    """
    if None in (z_offset, z_range, beam_size_unfocused):
        logger.error('Cannot plan_set. At least one of z_offset,'
                     ' z_range, beam_size_unfocused not defined.')
        return
    focus_before_sample = int(focus_before_sample)
    if size_vertical is not None:
        size_calc_1 = np.max(size_horizontal, size_vertical)
    else:
        size_calc_1 = size_horizontal

    t_lens_radii = LENS_RADII
    for rad in exclude:
        t_lens_radii.remove(rad)

    sets, effrads, sizes, foc_lens = calc_lens_set(
        energy=energy,
        size_fwhm=size_calc_1,
        distance=z_offset,
        n_max=max_tot_number_of_lenses,
        max_each=max_each,
        lens_radii=LENS_RADII,
    )

    distances = np.asarray([
            calc_distance_for_size(
                size_calc_1,
                list(chain(*list(zip(set, t_lens_radii)))),
                energy=energy,
                fwhm_unfocused=beam_size_unfocused,
            )[focus_before_sample] for set in sets])

    good_sets = np.logical_and(
        distances > np.min(z_offset + np.asarray(z_range)),
        distances < np.max(z_offset + np.asarray(z_range)))

    sets = sets[good_sets]
    size_range_min = np.asarray([
            calc_beam_fwhm(
                energy,
                list(chain(*list(zip(set, t_lens_radii)))),
                distance=z_offset - min(z_range),
                fwhm_unfocused=beam_size_unfocused,
                printsummary=False,
            ) for set in sets])

    size_range_max = np.asarray([
        calc_beam_fwhm(
            energy,
            list(chain(*list(zip(set, t_lens_radii)))),
            distance=z_offset - max(z_range),
            fwhm_unfocused=beam_size_unfocused,
            printsummary=False,
        ) for set in sets])

    sizes = sizes[good_sets]
    effrads = effrads[good_sets]
    distances = distances[good_sets]
    foclens = foc_lens[good_sets]
    transms = np.asarray(
        [lens_transmission(r=ter, fwhm=beam_size_unfocused, energy=energy)
            for ter in effrads])
    Nlenses_s = np.sum(sets, 1)

    # used for testing
    num = []
    f_m = []
    min_um = []
    max_um = []
    t_percent = []

    resstring = " N   f/m   Min/um   Max/um   T/%  Set  \n"
    zips = list(
        zip(sets, size_range_min, size_range_max,
            effrads, transms, Nlenses_s, foclens)
    )

    t = "{:2d} {:5.2f} {:8.1f} {:8.1f} {:5.1f}  "
    for n, z in enumerate(zips):
        the_set, sizemin, sizemax, eff_rad, transm, n_lenses, foclen = z
        logger.debug('eff_rad: %s', eff_rad)
        logger.debug('n_lenses: %s', n_lenses)

        num.append(n)
        f_m.append(foclen)
        min_um.append(sizemin * 1e6)
        max_um.append(sizemax * 1e6)
        t_percent.append(transm * 100)

        resstring += t.format(n, foclen, sizemin * 1e6,
                              sizemax * 1e6, transm * 100)
        resstring += ", ".join(
            [
                "%d x %dum" % (setLensno, t_lens_radii[m] * 1e6)
                for m, setLensno in enumerate(the_set)
                if setLensno > 0
            ]
        )
        resstring += "\n"
    logger.info('\n %s', resstring)
    return num, f_m, min_um, max_um, t_percent


def lens_transmission(r, fwhm, n=1, energy=None, id_material="IF1",
                      lens_thicknes=None):
    """
    Find the CRL (Compound Refractive Lens) transmission.

    Parameters
    ----------
    radius : float
        Effective radius of curvature
    fwhm : float
        Incident beam size on the lens in meters
    num : int
        Number of lenses in the stack
    energy : number
        Photon energy
    id_material : str
        Lens material

    Returns
    -------
    trans : float
    """
    lens_thicknes = lens_thicknes or APEX_DISTANCE
    id_material = alias.get(id_material, id_material)
    waist = 2 * gaussian_fwhm_to_sigma(fwhm)
    x = np.linspace(-2 * fwhm, 2 * fwhm, 101)
    y = x
    intensity = np.zeros((len(x), len(y)))
    thickness = np.zeros((len(x), len(y)))
    for i in range(len(x)):
        for j in range(len(y)):
            intensity[i, j] = (
                np.abs(np.exp(-2 * (x[i] ** 2 + y[j] ** 2) / waist ** 2))
                * 2
                / waist ** 2
                / np.pi
                * (x[2] - x[1]) ** 2
            )
            thickness[i, j] = (x[i] ** 2 + y[j] ** 2) / r + n * lens_thicknes
    d = density.get(id_material)
    att_length = get_att_len(energy, id_material, d)
    trans_intensity = intensity * np.exp(-thickness / att_length)
    trans = np.sum(trans_intensity)
    return trans


# Material density in g/cm^3
density = {
    "H": 0.00008988,
    "He": 0.0001785,
    "Li": 0.543,
    "Be": 1.85,
    "B": 2.34,
    "C": 3.5,
    "N": 0.0012506,
    "O": 0.001429,
    "F": 0.001696,
    "Ne": 0.0008999,
    "Na": 0.971,
    "Mg": 1.738,
    "Al": 2.698,
    "Si": 2.3296,
    "P": 1.82,
    "S": 2.067,
    "Cl": 0.003214,
    "Ar": 0.0017837,
    "K": 0.862,
    "Ca": 1.54,
    "Sc": 2.989,
    "Ti": 4.54,
    "V": 6.11,
    "Cr": 7.15,
    "Mn": 7.44,
    "Fe": 7.874,
    "Co": 8.86,
    "Ni": 8.912,
    "Cu": 8.96,
    "Zn": 7.134,
    "Ga": 5.907,
    "Ge": 5.323,
    "As": 5.776,
    "Se": 4.809,
    "Br": 3.122,
    "Kr": 0.003733,
    "Rb": 1.532,
    "Sr": 2.64,
    "Y": 4.469,
    "Zr": 6.506,
    "Nb": 8.57,
    "Mo": 10.22,
    "Tc": 11.5,
    "Ru": 12.37,
    "Rh": 12.41,
    "Pd": 12.02,
    "Ag": 10.501,
    "Cd": 8.69,
    "In": 7.31,
    "Sn": 7.287,
    "Sb": 6.685,
    "Te": 6.232,
    "I": 4.93,
    "Xe": 0.005887,
    "Cs": 1.873,
    "Ba": 3.594,
    "La": 6.145,
    "Ce": 6.77,
    "Pr": 6.773,
    "Nd": 7.007,
    "Pm": 7.26,
    "Sm": 7.52,
    "Eu": 5.243,
    "Gd": 7.895,
    "Tb": 8.229,
    "Dy": 8.55,
    "Ho": 8.795,
    "Er": 9.066,
    "Tm": 9.321,
    "Yb": 6.965,
    "Lu": 9.84,
    "Hf": 13.31,
    "Ta": 16.654,
    "W": 19.25,
    "WC": 15.8,
    "Re": 21.02,
    "Os": 22.61,
    "Ir": 22.56,
    "Pt": 21.46,
    "Au": 19.282,
    "Hg": 13.5336,
    "Tl": 11.85,
    "Pb": 11.342,
    "Bi": 9.807,
    "Po": 9.32,
    "At": 7,
    "Rn": 0.00973,
    "Fr": 1.87,
    "Ra": 5.5,
    "Ac": 10.07,
    "Th": 11.72,
    "Pa": 15.37,
    "U": 18.95,
    "Np": 20.45,
    "Pu": 19.84,
    "H2O": 1.0,
    "B4C": 2.52,
    "SiC": 3.217,
    "SiO2": 2.2,
    "Al2O3": 3.97,
    "ZnSe": 5.42,
    "ZnTe": 6.34,
    "CdS": 6.749,
    "CdSe": 7.01,
    "CdTe": 7.47,
    "BN": 3.49,
    "GaSb": 5.619,
    "GaAs": 5.316,
    "GaMnAs": 5.316,
    "GaP": 4.13,
    "InP": 4.787,
    "InAs": 5.66,
    "InSb": 5.775,
    "TaC": 13.9,
    "TiB2": 4.52,
    "YAG": 4.55,
    "CuBe": 8.96,
    "ZnO": 5.606,
    "SiC2": 3.217,
    "AlN": 3.3,
    "Si3N4": 3.44,
    "CaF2": 3.18,
    "LiF": 2.635,
    "KF": 2.48,
    "PbF2": 8.24,
    "SrF2": 4.24,
    "KBr": 2.75,
    "ZrO2": 5.6,
    "Gd3Ga5O12": 7.08,
    "CaSiO5": 2.4,
    "LaMnO3": 5.7,
    "LaAlO3": 6.52,
    "La0.7Sr0.3MnO3": 6.17,
    "La0.5Ca0.5MnO3": 6.3,
    "Fe.68Cr.2Ni.1Mn.02": 8.03,
    "CaSO4H4O2": 2.32,
    "C10H8O4": 1.4,
    "C22H10N2O5": 1.43,
    "C3H6O": 0.79,
    "C5H8O2": 1.19,
    "C2F4": 2.2,
    "C7H8": 0.867,
    "Y3Al5O12": 4.56,
    "CHN.3O7.6": 1.06,
    "C1.5H0.3O4.3N0.4PCa2.2": 1.92,
    ("Be0.9983O0.0003Al0.0001Ca0.0002C0.0003Cr0.000035Co0.000005Cu0.00005Fe0."
     "0003Pb0.000005Mg0.00006Mn0.00003Mo0.00001Ni0.0002Si0.0001Ag0.000005Ti0."
     "00001Zn0.0001"): 1.85,
    ("Be.994O.004Al.0005B.000003Cd.0000002Ca.0001C.0006Cr.0001Co.00001Cu."
     "0001Fe.0008Pb.00002Li.000003Mg.00049Mn.0001Mo.00002Ni.0002N.0003Si."
     "0004Ag.00001"): 1.85,
}


# Chemical Formula Aliases
alias = {
    "Air": "N1.562O.42C.0003Ar.0094",
    "air": "N1.562O.42C.0003Ar.0094",
    "C*": "C",
    "mylar": "C10H8O4",
    "Mylar": "C10H8O4",
    "polyimide": "C22H10N2O5",
    "Polyimide": "C22H10N2O5",
    "kapton": "C22H10N2O5",
    "Kapton": "C22H10N2O5",
    "304SS": "Fe.68Cr.2Ni.1Mn.02",
    "Acetone": "C3H6O",
    "acetone": "C3H6O",
    "PMMA": "C5H8O2",
    "Teflon": "C2F4",
    "teflon": "C2F4",
    "Toluene": "C7H8",
    "toluene": "C7H8",
    "FS": "SiO2",
    "GGG": "Gd3Ga5O12",
    "quartz": "SiO2",
    "Quartz": "SiO2",
    "Silica": "SiO2",
    "silica": "SiO2",
    "water": "H2O",
    "Water": "H2O",
    "Calcite": "CaCO3",
    "calcite": "CaCO3",
    "YAG": "Y3Al5O12",
    "yag": "Y3Al5O12",
    "Sapphire": "Al2O3",
    "sapphire": "Al2O3",
    "Blood": "CHN.3O7.6",
    "LMSO": "La0.7Sr0.3MnO3",
    "blood": "CHN.3O7.6",
    "Bone": "C1.5H0.3O4.3N0.4PCa2.2",
    "bone": "C1.5H0.3O4.3N0.4PCa2.2",
    "IF1": ("Be0.9983O0.0003Al0.0001Ca0.0002C0.0003Cr0.000035Co0.000005Cu0."
            "00005Fe0.0003Pb0.000005Mg0.00006Mn0.00003Mo0.00001Ni0.0002Si0."
            "0001Ag0.000005Ti0.00001Zn0.0001"),
    "PF60": ("Be.994O.004Al.0005B.000003Cd.0000002Ca.0001C.0006Cr.0001Co."
             "00001Cu.0001Fe.0008Pb.00002Li.000003Mg.00049Mn.0001Mo.00002Ni."
             "0002N.0003Si.0004Ag.00001"),
}
