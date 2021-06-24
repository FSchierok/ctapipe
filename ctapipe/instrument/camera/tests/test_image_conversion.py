import pytest
import numpy as np
from numpy.testing import assert_allclose
from ctapipe.image.toymodel import Gaussian
import astropy.units as u


def create_mock_image(geom):
    """
    creates a mock image, which parameters are adapted to the camera size
    """

    camera_r = np.max(np.sqrt(geom.pix_x ** 2 + geom.pix_y ** 2))
    model = Gaussian(
        x=0.3 * camera_r,
        y=0 * u.m,
        width=0.03 * camera_r,
        length=0.10 * camera_r,
        psi="25d",
    )

    _, image, _ = model.generate_image(
        geom, intensity=0.5 * geom.n_pixels, nsb_level_pe=3
    )
    return image


@pytest.mark.parametrize("rot", [3])
def test_single_image(camera_geometry, rot):
    """
    Test if we can transform toy images for different geometries
    and get the same images after transforming back
    """
    image = create_mock_image(camera_geometry)
    image_2d = camera_geometry.to_regular_image(image)
    image_1d = camera_geometry.regular_image_to_1d(image_2d)
    assert np.nansum(image) == np.nansum(image_2d)
    assert_allclose(image, image_1d)


@pytest.mark.xfail()
@pytest.mark.parametrize("rot", [3])
def test_multiple_images(camera_geometry, rot):
    """
    Test if we can transform toy images for different geometries
    and get the same images after transforming back
    """
    images = np.array([create_mock_image(camera_geometry) for i in range(5)])
    images_2d = camera_geometry.to_regular_image(images.T)
    images_1d = camera_geometry.regular_image_to_1d(images_2d)
    assert np.nansum(images) == np.nansum(images_2d)
    assert_allclose(images, images_1d)
