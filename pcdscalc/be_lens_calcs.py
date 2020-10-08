'''
Module for Beryllium Lens Calculations
'''
import logging
from itertools import product

import numpy as np
import xraydb as xdb
from periodictable import xsf

logger = logging.getLogger(__name__)

# We have sets of Be lenses with thicknesses:
LENS_RADII = [50e-6, 100e-6, 200e-6, 300e-6, 500e-6, 1000e-6, 1500e-6]


def get_att_len(energy, material="Be", density=None):
    '''
    Get the attenuation length (in meter) of a material, if no
    parameter is given for the predefined energy;
    then T=exp(-thickness/att_len);

    Parameters
    ----------
    energy : number
        Beam Energy given in keV
    material : `str`
        Default - Beryllium.
        The use of beryllium extends the range of operation
        of compound refractive lenses, improving transmission,
        aperture size, and gain
    density : `float`
        Material density in g/cm^3

    Returns
    -------
    att_len : `numpy.float64`
        Attenuation length
    '''
    att_len = 1.0 / xdb.material_mu(material, energy * 1.0e3)
    old_att_len = float(attenuation_length(compound=material,
                                           density=density,
                                           energy=energy))
    logger.debug(xdb.atomic_density(material))
    return att_len, old_att_len


def get_delta(energy, material="Be", density=None):
    '''
    Calculate delta for a given material at a given energy

    Parameters
    ----------
    energy : number
        x-ray energy in eV
    material : `str`
        Chemical formula (‘Fe2O3’, ‘CaMg(CO3)2’, ‘La1.9Sr0.1CuO4’)
        Default - Beryllium.
    density : `float`
        Material density in g/cm^3

    Returns
    -------
    delta : `numpy.float64`
        Real part of index of refraction
    '''
    # xray_delta_beta returns (delta, beta, atlen),
    # wehre delta : real part of index of refraction
    delta = xdb.xray_delta_beta(material, energy=energy * 1.0e3,
                                density=xdb.atomic_density(material))[0]

    old_delta = 1 - np.real(xsf.index_of_refraction(material,
                            density=xdb.atomic_density(material),
                            energy=energy))
    logger.debug(xdb.atomic_density(material))
    return delta, old_delta


def calc_focal_length_for_single_lens(energy, radius, material="Be",
                                      density=None):
    '''
    Calculate the Focal Length for a single lens.

    Parameters
    ----------
    energy : number
        Beam Energy
    radius : `float` TODO: is this float or not always?
    material : `str`
        Default - Beryllium.
        The use of beryllium extends the range of operation
        of compound refractive lenses, improving transmission,
        aperture size, and gain
    density : `float`
        Material density in g/cm^3

    Returns
    -------
    focal_length : `float`
        The focal length for a single lens
    '''
    delta = get_delta(energy, material, density)
    focal_length = radius / 2.0 / delta
    return focal_length


def calc_focal_length(energy, lens_set, material="Be", density=None):
    '''
    Calculate the Focal Length for certain lenses configuration and energy.

    Parameters
    ----------
    energy : number
        Beam Energy
    lens_set : `list`
        [numer1, lensthick1, number2, lensthick2 ...]
    material : `str`
        Default - Beryllium.
        The use of beryllium extends the range of operation
        of compound refractive lenses, improving transmission,
        aperture size, and gain
    density : `float`
        Material density in g/cm^3

    Returns
    -------
    focal_length : `float`
    '''
    f_tot_inverse = 0

    lens_set = (list(zip(lens_set[::2], lens_set[1::2])))
    for num, radius in lens_set:
        fln = calc_focal_length_for_single_lens(
                    energy, radius, material, density)
        f_tot_inverse += num/fln

    return 1.0 / f_tot_inverse


# TODO: check what to do with fwhm_unfocused if None - for now
# I added a "default" value but it will complain fi None
def calc_beam_fwhm(energy, lens_set, distance=None, source_distance=None,
                   material="Be", density=None, fwhm_unfocused=500e-6,
                   printsummary=True):
    '''
    Calculates beam parameters for certain lenses configuration
    and energy at a given distance.
    Optionally some other parameters can be set

    Parameters
    ----------
    energy : number
        Beam Energy
    lens_set : `list`
        [numer1, lensthick1, number2, lensthick2...]
    distance : `float`
        Distance from the lenses to the sample is 3.852 m at XPP.
    source_distance : `float`
        Distance from source to lenses. This is about 160 m at XPP.
    material : `str`
        Beryllium. The use of beryllium extends the range of operation
        of compound refractive lenses, improving transmission,
        aperture size, and gain
    density : `float`
        Material density in g/cm^3
    fwhm_unfocused : `float`
        This is about 400 microns at XPP.
    printsummary : `bool`
        Prints summary of parameters/calculations if True

    Returns
    -------
    size_fwhm : `float`
    '''
    # Focal length for certain lenses configuration and energy
    logger.debug('lens_set %s', lens_set)
    focal_length = calc_focal_length(energy, lens_set, material, density)

    # use lens makers equation to find distance to image of source
    if source_distance is not None:
        focal_length = 1 / (1 / focal_length - 1 / source_distance)

    lam = 1.2398 / energy * 1e-9
    # the w parameter used in the usual formula is 2*sigma

    w_unfocused = fwhm_unfocused * 2 / 2.35
    # assuming gaussian beam divergence = w_unfocused/f we can obtain
    waist = lam / np.pi * focal_length / w_unfocused
    rayleigh_range = np.pi * waist ** 2 / lam
    size = waist * np.sqrt(1.0 + (distance - focal_length) ** 2.0 /
                           rayleigh_range ** 2)
    size_fwhm = size * 2.35 / 2.0

    if printsummary:
        logger.info("FWHM at lens   : %.3e" % (fwhm_unfocused))
        logger.info("waist          : %.3e" % (waist))
        logger.info("waist FWHM     : %.3e" % (waist * 2.35 / 2.0))
        logger.info("rayleigh_range : %.3e" % (rayleigh_range))
        logger.info("focal length   : %.3e" % (focal_length))
        logger.info("size           : %.3e" % (size))
        logger.info("size FWHM      : %.3e" % (size_fwhm))

    return size_fwhm


def calc_distance_for_size(size_fwhm, lens_set=None, energy=None,
                           fwhm_unfocused=None):
    '''
    Calculate the distance for size
    '''
    size = size_fwhm * 2.0 / 2.35
    focal_length = calc_focal_length(energy, lens_set, "Be", density=None)
    lam = 12.398 / energy * 1e-10
    # the w parameter used in the usual formula is 2*sigma
    w_unfocused = fwhm_unfocused * 2 / 2.35
    # assuming gaussian beam divergence = w_unfocused/f we can obtain
    waist = lam / np.pi * focal_length / w_unfocused
    rayleigh_range = np.pi * waist ** 2 / lam
    # TODO: should i be handling this below it was commente out in the old code
    # bs = (size/waist)**2-1
    # if bs >= 0:
    distance = (
        np.sqrt((size / waist) ** 2 - 1) * np.asarray([-1.0, 1.0]) *
        rayleigh_range) + focal_length
    # TODO: the distance is in this format: [  4.         134.90095291]
    # check to see if that's what we want
    # else:
    # distance = nan
    #
    return distance


# TODO: ========== WE MIGHT NOT NEED THESE FUNCTIONS BELOW =================
def calc_lens_set(energy, size_fwhm, distance, n_max=12, max_each=5,
                  lens_radii=[100e-6, 200e-6, 300e-6, 500e-6, 1000e-6],
                  fwhm_unfocused=0.0005, eff_rad0=None):
    nums = product(*([list(range(max_each + 1))] * len(lens_radii)))
    sets = []
    sizes = []
    effrads = []
    foclens = []
    for num in nums:
        lens_set = []
        if sum(num) <= n_max and sum(num) > 0:
            if eff_rad0 is None:
                teffradinv = 0
            else:
                teffradinv = 1 / eff_rad0
            for tn, tl in zip(num, lens_radii):
                lens_set += [tn, tl]
                teffradinv += tn / tl
            teffrad = np.round(1 / teffradinv, 6)
            # print teffrad
            if teffrad in effrads:
                ind = effrads.index(teffrad)
                # print num
                # print sets[ind]
                # raw_input()

                if sum(sets[ind]) > sum(num):
                    sets[ind] = num
                else:
                    continue
            else:
                effrads.append(teffrad)
                sets.append(num)
                sizes.append(
                    calc_beam_fwhm(
                        energy,
                        lens_set + [1, eff_rad0],
                        distance=distance,
                        source_distance=None,
                        fwhm_unfocused=fwhm_unfocused,
                        printsummary=False,
                    )
                )
                foclens.append(calc_focal_length(energy, lens_set + [1,
                               eff_rad0]))

    sizes = np.asarray(sizes)
    sets = np.asarray(sets)
    foclens = np.asarray(foclens)
    indsort = (np.abs(sizes - size_fwhm)).argsort()

    return (
        sets[indsort, :],
        np.asarray(effrads)[indsort],
        sizes[indsort],
        foclens[indsort],
    )


def calc_lens_aperture_radius(radius, diskthickness=1e-3, apexdistance=30e-6):
    R0 = np.sqrt(radius * (diskthickness - apexdistance))
    return R0


def calc_trans_for_single_lens(energy, radius, material="Be", density=None,
                               fwhm_unfocused=900e-6, disk_thickness=1.0e-3,
                               apex_distance=30e-6):
    '''
    Calculate the transmission for a single lens.
    Usage : calcTransForSingleLens(energy,radius,material="Be",density=None,
            fwhm_unfocused=800e-6,diskthickness=1.0e-3,apexdistance=30e-6):
    '''
    delta = get_delta(energy, material, density)
    # TODO: delta is not used, might have to remove it
    # but for now printing it out here
    logger.debug('delta: %d', delta)
    mu = 1.0 / get_att_len(energy, material="Be", density=None)
    s = fwhm_unfocused / 2.35482
    S = (s ** (-2.0) + 2.0 * mu / radius) ** (-0.5)
    R0 = np.sqrt(radius * (disk_thickness - apex_distance))
    trans = (
        (S ** 2 / s ** 2)
        * np.exp(-mu * apex_distance)
        * (1 - np.exp(-(R0 ** 2.0) / (2.0 * S ** 2)))
    )
    return trans


def calc_trans_lens_set(energy, lens_set, material="Be", density=None,
                        fwhm_unfocused=900e-6, disk_thickness=1.0e-3,
                        apex_distance=30e-6):
    '''
    Calculte the transmission of a lens set.
    usage : calcTrans(energy,lens_set,material="Be",density=None,
            fwhm_unfocused=900e-6)
    There is latex document that explains the formula.
    Can be adapted to use different thicknesses for each lens,
    and different apex distances, but this would require changing
    the format of lens_set, which would mean changing
    a whole bunch of other programs too.
    '''

    apex_distance_tot = 0
    radius_total_inv = 0
    # this is an ugly hack: the radius will never be bigger than 1m,
    # so will always be overwritten
    radius_aperture = 1.0
    # if type(lens_set) is int:
    #     lens_set = get_lens_set(lens_set)
    # TODO: might be in a situation where lens_set is not a
    # list but a float or int? - what to do?
    for i in range(len(lens_set) // 2):
        num = lens_set[2 * i]
        rad = lens_set[2 * i + 1]
        new_rad_ap = np.sqrt(rad * (disk_thickness - apex_distance))
        radius_aperture = min(radius_aperture, new_rad_ap)
        radius_total_inv += num / rad
        apex_distance_tot += num * apex_distance
    radius_total = 1.0 / radius_total_inv
    equivalent_disk_thickness = (radius_aperture ** 2 / radius_total +
                                 apex_distance_tot)
    transtot = calc_trans_for_single_lens(
        energy,
        radius_total,
        material,
        density,
        fwhm_unfocused,
        equivalent_disk_thickness,
        apex_distance_tot,
    )
    return transtot


def find_energy(lens_set, distance=3.952, material="Be", density=None):
    '''
    Find the energy that would focus at a given distance

    Parameters
    ----------
    lens_set : `list`
        [numer1, lensthick1, number2, lensthick2...]
    distance : `float`
    material : str
        Beryllium. The use of beryllium extends the range of operation
        of compound refractive lenses, improving transmission,
        aperture size, and gain
    density : TODO: find out what density is

    usage find_energy( (2,200e-6,4,500e-6) ,distance=4 )

    Returns
    -------
    energy : float
        Energy
    '''
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
    logger.info("Energy that would focus at a distance of %.3f is %.3f"
                % (distance, energy))

    s = calc_beam_fwhm(energy, lens_set, distance=distance,
                       source_distance=None, material=material,
                       density=density)
    # TODO: s is not used, might have to remove it
    # but for now printing it out here
    logger.debug(f's: {s}')
    return energy


# leaving this here for now to compare with the new implementation
# This function was part of our Frankenstein periodic table build.
# It now lives here because it was never an official part of the module.
# I copied it in and adjusted namespaces accordingly.
def attenuation_length(
    compound, density=None, natural_density=None, energy=None, wavelength=None
):
    """
    Calculates the attenuation length for a compound
    Transmisison if then exp(-thickness/attenuation_length)
    :Parameters:
        *compound* : Formula initializer
            Chemical formula.
        *density* : float | |g/cm^3|
            Mass density of the compound, or None for default.
        *natural_density* : float | |g/cm^3|
            Mass density of the compound at naturally occurring isotope
            abundance.
        *wavelength* : float or vector | |Ang|
            Wavelength of the X-ray.
        *energy* : float or vector | keV
            Energy of the X-ray, if *wavelength* is not specified.
    :Returns:
        *attenuation_length* : vector | |m|
            as function of (energy)
    :Notes:
    against http://henke.lbl.gov/optical_constants/
    """

    if energy is not None:
        wavelength = xsf.xray_wavelength(energy)
    assert wavelength is not None, 'scattering calculation '
    'needs energy or wavelength'
    if np.isscalar(wavelength):
        wavelength = np.array([wavelength])
    n = xsf.index_of_refraction(
        compound=compound,
        density=density,
        natural_density=natural_density,
        wavelength=wavelength,
    )
    attenuation_length = (wavelength * 1e-10) / (4 * np.pi * np.imag(n))
    return np.abs(attenuation_length)
