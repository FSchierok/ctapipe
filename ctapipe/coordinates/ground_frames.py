"""This module defines the important coordinate systems to be used in
reconstruction with the CTA pipeline and the transformations between
this different systems. Frames and transformations are defined using
the astropy.coordinates framework. This module defines transformations
for ground based cartesian and planar systems.

For examples on usage see examples/coordinate_transformations.py

This code is based on the coordinate transformations performed in the
read_hess code

TODO:

- Tests Tests Tests!
"""
import astropy.units as u
from astropy.units.quantity import Quantity
import numpy as np
from astropy.coordinates import (
    AltAz,
    BaseCoordinateFrame,
    CartesianRepresentation,
    CoordinateAttribute,
    FunctionTransform,
    RepresentationMapping,
    frame_transform_graph,
    AffineTransform,
)
from numpy import cos, sin

__all__ = [
    "GroundFrame",
    "TiltedGroundFrame",
    "project_to_ground",
    "EastingNorthingFrame",
]


class GroundFrame(BaseCoordinateFrame):
    """Ground coordinate frame.  The ground coordinate frame is a simple
    cartesian frame describing the 3 dimensional position of objects
    compared to the array ground level in relation to the nomial
    centre of the array.  Typically this frame will be used for
    describing the position on telescopes and equipment.
    In this frame x points north, y points west and z is meters above array center.

    Frame attributes: None

    """

    default_representation = CartesianRepresentation


class EastingNorthingFrame(BaseCoordinateFrame):
    """GroundFrame but in standard Easting/Northing coordinates instead of
    SimTel/Corsika conventions

    Frame attributes: None

    """

    default_representation = CartesianRepresentation

    frame_specific_representation_info = {
        CartesianRepresentation: [
            RepresentationMapping("x", "easting"),
            RepresentationMapping("y", "northing"),
            RepresentationMapping("z", "height"),
        ]
    }


class TiltedGroundFrame(BaseCoordinateFrame):
    """Tilted ground coordinate frame.  The tilted ground coordinate frame
    is a cartesian system describing the 2 dimensional projected
    positions of objects in a tilted plane described by
    pointing_direction Typically this frame will be used for the
    reconstruction of the shower core position

    Frame attributes:

    * ``pointing_direction``
        Alt,Az direction of the tilted reference plane

    """

    default_representation = CartesianRepresentation
    # Pointing direction of the tilted system (alt,az),
    # could be the telescope pointing direction or the reconstructed shower
    # direction
    pointing_direction = CoordinateAttribute(default=None, frame=AltAz)


def get_shower_trans_matrix(azimuth, altitude):
    """Get Transformation matrix for conversion from the ground system to
    the Tilted system and back again (This function is directly lifted
    from read_hess, probably could be streamlined using python
    functionality)

    Parameters
    ----------
    azimuth: float
        Azimuth angle of the tilted system used
    altitude: float
        Altitude angle of the tilted system used

    Returns
    -------
    trans: 3x3 ndarray transformation matrix
    """

    cos_z = sin(altitude)
    sin_z = cos(altitude)
    cos_az = cos(azimuth)
    sin_az = sin(azimuth)

    trans = np.array(
        [
            [cos_z * cos_az, -cos_z * sin_az, -sin_z],
            [sin_az, cos_az, np.zeros_like(sin_z)],
            [sin_z * cos_az, -sin_z * sin_az, cos_z],
        ],
        dtype=np.float64,
    )

    return trans


@frame_transform_graph.transform(FunctionTransform, GroundFrame, TiltedGroundFrame)
def ground_to_tilted(ground_coord, tilted_frame):
    """
    Transformation from ground system to tilted ground system

    Parameters
    ----------
    ground_coord: `astropy.coordinates.SkyCoord`
        Coordinate in GroundFrame
    tilted_frame: `ctapipe.coordinates.TiltedFrame`
        Frame to transform to

    Returns
    -------
    SkyCoordinate transformed to `tilted_frame` coordinates
    """
    x_grd, y_grd, z_grd = ground_coord.cartesian.xyz

    altitude = tilted_frame.pointing_direction.alt.to_value(u.rad)
    azimuth = tilted_frame.pointing_direction.az.to_value(u.rad)

    trans = get_shower_trans_matrix(azimuth, altitude)

    x_tilt = trans[0, 0] * x_grd + trans[0, 1] * y_grd + trans[0, 2] * z_grd
    y_tilt = trans[1, 0] * x_grd + trans[1, 1] * y_grd + trans[1, 2] * z_grd
    z_tilt = trans[2, 0] * x_grd + trans[2, 1] * y_grd + trans[2, 2] * z_grd

    representation = CartesianRepresentation(x_tilt, y_tilt, z_tilt)

    return tilted_frame.realize_frame(representation)


@frame_transform_graph.transform(FunctionTransform, TiltedGroundFrame, GroundFrame)
def tilted_to_ground(tilted_coord, ground_frame):
    """
    Transformation from tilted ground system to  ground system

    Parameters
    ----------
    tilted_coord: `astropy.coordinates.SkyCoord`
        TiltedGroundFrame system
    ground_frame: `astropy.coordinates.SkyCoord`
        GroundFrame system

    Returns
    -------
    GroundFrame coordinates
    """
    x_tilt, y_tilt, z_tilt = tilted_coord.cartesian.xyz

    altitude = tilted_coord.pointing_direction.alt.to(u.rad)
    azimuth = tilted_coord.pointing_direction.az.to(u.rad)

    trans = get_shower_trans_matrix(azimuth, altitude)

    x_grd = trans[0][0] * x_tilt + trans[1][0] * y_tilt + trans[2][0] * z_tilt
    y_grd = trans[0][1] * x_tilt + trans[1][1] * y_tilt + trans[2][1] * z_tilt
    z_grd = trans[0][2] * x_tilt + trans[1][2] * y_tilt + trans[2][2] * z_tilt

    representation = CartesianRepresentation(x_grd, y_grd, z_grd)

    grd = ground_frame.realize_frame(representation)
    return grd


def project_to_ground(tilt_system):
    """Project position in the tilted system onto the ground. This is
    needed as the standard transformation will return the 3d position
    of the tilted frame. This projection may ultimately be the
    standard use case so may be implemented in the tilted to ground
    transformation

    Parameters
    ----------
    tilt_system: `astropy.coordinates.SkyCoord`
        coorinate in the the tilted ground system

    Returns
    -------
    Projection of tilted system onto the ground (GroundSystem)

    """
    ground_system = tilt_system.transform_to(GroundFrame)

    unit = ground_system.x.unit
    x_initial = ground_system.x.value
    y_initial = ground_system.y.value
    z_initial = ground_system.z.value

    trans = get_shower_trans_matrix(
        tilt_system.pointing_direction.az, tilt_system.pointing_direction.alt
    )

    x_projected = x_initial - trans[2][0] * z_initial / trans[2][2]
    y_projected = y_initial - trans[2][1] * z_initial / trans[2][2]

    return GroundFrame(x=x_projected * unit, y=y_projected * unit, z=0 * unit)


@frame_transform_graph.transform(FunctionTransform, GroundFrame, GroundFrame)
def ground_to_ground(ground_coords, ground_frame):
    """Null transform for going from ground to ground, since there are no
    attributes of the GroundSystem"""
    return ground_coords


# Matrices for transforming between GroundFrame and EastingNorthingFrame
NO_OFFSET = CartesianRepresentation(Quantity([0, 0, 0], u.m))
GROUND_TO_EASTNORTH = np.asarray([[0, -1, 0], [1, 0, 0], [0, 0, 1]])


@frame_transform_graph.transform(AffineTransform, GroundFrame, EastingNorthingFrame)
def ground_to_easting_northing(ground_coords, eastnorth_frame):
    """
    convert GroundFrame points into eastings/northings for plotting purposes

    """

    return GROUND_TO_EASTNORTH, NO_OFFSET


@frame_transform_graph.transform(AffineTransform, EastingNorthingFrame, GroundFrame)
def easting_northing_to_ground(eastnorth_coords, ground_frame):
    """
    convert  eastings/northings back to GroundFrame

    """
    return GROUND_TO_EASTNORTH.T, NO_OFFSET
