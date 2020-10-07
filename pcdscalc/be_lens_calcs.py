'''
Module for Beryllium Lens Calculations
'''
from periodictable import xsf
# from periodictable import formula as ptable_formula
import numpy as np
# import datetime
# import os
# import shutil
# import pprint
from itertools import product


"""
If you are using the IMS IOC, each lens motor should have a
base record associated with it  i.e MFX:DIA:XFLS.
There should also be a binary record for each state,
that is just this base plus an arbitrary string i.e MFX:DIA:XFLS:OUT
"""

# We have sets of Be lenses with thicknesses:
LENS_RADII = [50e-6, 100e-6, 200e-6, 300e-6, 500e-6, 1000e-6, 1500e-6]


def get_att_len(E, material="Be", density=None):
    '''
    Get the attenuation length of material (in meter).
    If no parameter is given for the predefined energy,
    then T = exp(-thickness/att_len)

    Parameters
    ----------
    E : number
        Beam Energy (keV)
    material : `str`
        Default - Beryllium. TODO: (default Si) in the old code??
        The use of beryllium extends the range of operation
        of compound refractive lenses, improving transmission,
        aperture size, and gain
    density : TODO: find out what is density?

    Returns
    -------
    att_len : `float`
        The attenuation length of material
    '''
    att_len = float(xsf.attenuation_length(material, density=density,
                    energy=E))
    return att_len


def get_delta(E, material="Be", density=None):
    '''
    Calculate delta for a given material at a given energy

    Parameters
    ----------
    E : number
        Beam Energy
    material : `str`
        Default - Beryllium.
        The use of beryllium extends the range of operation
        of compound refractive lenses, improving transmission,
        aperture size, and gain
    density : TODO: find out what density is

    Returns
    -------
    delta : `int` TODO: not sure if int here or float?
    '''
    delta = 1 - np.real(xsf.index_of_refraction(material, density=density,
                        energy=E))
    return delta


def calc_focal_length_for_single_lens(E, radius, material="Be", density=None):
    '''
    Calculate the Focal Length for a single lens.

    Parameters
    ----------
    E: number
        Beam Energy
    radius : float TODO: is this float or no?
    material : `str`
        Default - Beryllium.
        The use of beryllium extends the range of operation
        of compound refractive lenses, improving transmission,
        aperture size, and gain
    density : TODO: find out what density is

    Returns
    -------
    focal_length : `float`
        The focal length for a single lens
    '''
    delta = get_delta(E, material, density)
    focal_length = radius / 2.0 / delta
    return focal_length


def calc_focal_length(E, lens_set, material="Be", density=None):
    '''
    Calculate the Focal Length for certain lenses configuration and energy.

    Parameters
    ----------
    E: number
        Beam Energy
    lens_set : `list`
        [(numer1, lensthick1), (number2, lensthick2)...]
    material : `str`
        Default - Beryllium.
        The use of beryllium extends the range of operation
        of compound refractive lenses, improving transmission,
        aperture size, and gain
    density : TODO: find out what density is

    Returns
    -------
    focal_length : `float`
    '''
    num = []
    rad = []
    ftot_inverse = 0
    # if type(lens_set) is int:
    #     lens_set = getLensSet(lens_set)
    # range() only works with integers, dividing with the / operator always
    # results in a float value. TOo fix it, we use // floor division operator.
    for i in range(len(lens_set) // 2):
        num = lens_set[2 * i]
        rad = lens_set[2 * i + 1]
        if rad is not None:
            # rad = float(rad)
            # num = float(num)
            ftot_inverse += num / calc_focal_length_for_single_lens(
                            E, rad, material, density)
    return 1.0 / ftot_inverse


def calc_beam_fwhm(E, lens_set, distance=None, material="Be",
                   density=None, fwhm_unfocused=None, printsummary=True):
    '''
    Calculate beam parameters for certain lenses configuration
    and energy at a given distance.
    Optionally some other parameters can be set

    Parameters
    ----------
    E : number
        Beam Energy
    lens_set : `list`
        [(numer1, lensthick1), (number2, lensthick2)...]
    distance: `float`
        Distance from the lenses to the sample is 3.852 m at XPP.
    material : `str`
        Default - Beryllium.
        The use of beryllium extends the range of operation
        of compound refractive lenses, improving transmission,
        aperture size, and gain
    density : TODO: find out what density is
    fwhm_unfocused : `float`
    printsummary : `bool`
        Prints summary of parameters/calculations if True

    Returns
    -------
    Size FWHM : `float`
    '''
    # Focal length for certain lenses configuration and energy
    focal_length = calc_focal_length(E, lens_set, material, density)
    lam = 1.2398 / E * 1e-9
    # the w parameter used in the usual formula is 2*sigma

    # TODO: remove this next line
    fwhm_unfocused = 2
    w_unfocused = fwhm_unfocused * 2 / 2.35
    # assuming gaussian beam divergence = w_unfocused/f we can obtain
    waist = lam / np.pi * focal_length / w_unfocused
    rayleigh_range = np.pi * waist ** 2 / lam
    size = waist * np.sqrt(1.0 + (distance - focal_length) ** 2.0 /
                           rayleigh_range ** 2)
    size_fwhm = size * 2.35 / 2.0

    if printsummary:
        print("FWHM at lens   : %.3e" % (fwhm_unfocused))
        print("waist          : %.3e" % (waist))
        print("waist FWHM     : %.3e" % (waist * 2.35 / 2.0))
        print("rayleigh_range : %.3e" % (rayleigh_range))
        print("focal length   : %.3e" % (focal_length))
        print("size           : %.3e" % (size))
        print("size FWHM      : %.3e" % (size_fwhm))

    return size_fwhm


def find_energy(lens_set, distance=3.952, material="Be", density=None):
    '''
    Find the energy that would focus at a given distance

    Parameters
    ----------
    lens_set : `list`
        [(numer1, lensthick1), (number2, lensthick2)...]
    distance : `float`
    material : str
        Beryllium. The use of beryllium extends the range of operation
        of compound refractive lenses, improving transmission,
        aperture size, and gain
    density : TODO: find out what density is

    usage findEnergy( (2,200e-6,4,500e-6) ,distance =4 )

    Returns
    -------
    E : float
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
            print("somehow failed ...")
            break
        abs_diff = abs(distance - focal_length)
    print("Energy that would focus at a distance of %.3f is %.3f"
          % (distance, energy))
    s = calc_beam_fwhm(energy, lens_set, distance, material, density)
    # TODO: s is not used, might have to remove it
    # but for now printing it out here
    print('s: %d', s)
    return energy


def calc_distance_for_size(size_fwhm, lens_set=None, E=None,
                           fwhm_unfocused=None):
    '''
    Calculate the distance for size
    '''
    size = size_fwhm * 2.0 / 2.35
    f = calc_focal_length(E, lens_set, "Be", density=None)
    lam = 12.398 / E * 1e-10
    # the w parameter used in the usual formula is 2*sigma
    w_unfocused = fwhm_unfocused * 2 / 2.35
    # assuming gaussian beam divergence = w_unfocused/f we can obtain
    waist = lam / np.pi * f / w_unfocused
    rayleigh_range = np.pi * waist ** 2 / lam
    # bs = (size/waist)**2-1
    # if bs >= 0:
    distance = (
        np.sqrt((size / waist) ** 2 - 1) * np.asarray([-1.0, 1.0]) *
        rayleigh_range) + f
    # else:
    # distance = nan
    #
    return distance


def calc_lens_set(E, size_fwhm, distance, n_max=12, max_each=5,
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
                        E,
                        lens_set + [1, eff_rad0],
                        distance=distance,
                        printit=False,
                        fwhm_unfocused=fwhm_unfocused,
                    )
                )
                foclens.append(calc_focal_length(E, lens_set + [1, eff_rad0]))

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


def calc_trans_for_single_lens(E, radius, material="Be", density=None,
                               fwhm_unfocused=900e-6, disk_thickness=1.0e-3,
                               apex_distance=30e-6):
    '''
    Calculate the transmission for a single lens.
    Usage : calcTransForSingleLens(E,radius,material="Be",density=None,
            fwhm_unfocused=800e-6,diskthickness=1.0e-3,apexdistance=30e-6):
    '''
    delta = get_delta(E, material, density)
    # TODO: delta is not used, might have to remove it
    # but for now printing it out here
    print('delta: %d', delta)
    mu = 1.0 / get_att_len(E, material="Be", density=None)
    s = fwhm_unfocused / 2.35482
    S = (s ** (-2.0) + 2.0 * mu / radius) ** (-0.5)
    R0 = np.sqrt(radius * (disk_thickness - apex_distance))
    trans = (
        (S ** 2 / s ** 2)
        * np.exp(-mu * apex_distance)
        * (1 - np.exp(-(R0 ** 2.0) / (2.0 * S ** 2)))
    )
    return trans


def calc_trans_lens_set(E, lens_set, material="Be", density=None,
                        fwhm_unfocused=900e-6, disk_thickness=1.0e-3,
                        apex_distance=30e-6):
    '''
    Calculte the transmission of a lens set.
    usage : calcTrans(E,lens_set,material="Be",density=None,
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
    for i in range(len(lens_set) / 2):
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
        E,
        radius_total,
        material,
        density,
        fwhm_unfocused,
        equivalent_disk_thickness,
        apex_distance_tot,
    )
    return transtot
