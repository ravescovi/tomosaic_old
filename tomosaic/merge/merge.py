#!/usr/bin/env python
# -*- coding: utf-8 -*-

# #########################################################################
# Copyright (c) 2015, UChicago Argonne, LLC. All rights reserved.         #
#                                                                         #
# Copyright 2015. UChicago Argonne, LLC. This software was produced       #
# under U.S. Government contract DE-AC02-06CH11357 for Argonne National   #
# Laboratory (ANL), which is operated by UChicago Argonne, LLC for the    #
# U.S. Department of Energy. The U.S. Government has rights to use,       #
# reproduce, and distribute this software.  NEITHER THE GOVERNMENT NOR    #
# UChicago Argonne, LLC MAKES ANY WARRANTY, EXPRESS OR IMPLIED, OR        #
# ASSUMES ANY LIABILITY FOR THE USE OF THIS SOFTWARE.  If software is     #
# modified to produce derivative works, such modified software should     #
# be clearly marked, so as not to confuse it with the version available   #
# from ANL.                                                               #
#                                                                         #
# Additionally, redistribution and use in source and binary forms, with   #
# or without modification, are permitted provided that the following      #
# conditions are met:                                                     #
#                                                                         #
#     * Redistributions of source code must retain the above copyright    #
#       notice, this list of conditions and the following disclaimer.     #
#                                                                         #
#     * Redistributions in binary form must reproduce the above copyright #
#       notice, this list of conditions and the following disclaimer in   #
#       the documentation and/or other materials provided with the        #
#       distribution.                                                     #
#                                                                         #
#     * Neither the name of UChicago Argonne, LLC, Argonne National       #
#       Laboratory, ANL, the U.S. Government, nor the names of its        #
#       contributors may be used to endorse or promote products derived   #
#       from this software without specific prior written permission.     #
#                                                                         #
# THIS SOFTWARE IS PROVIDED BY UChicago Argonne, LLC AND CONTRIBUTORS     #
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT       #
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS       #
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL UChicago     #
# Argonne, LLC OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,        #
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,    #
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;        #
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER        #
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT      #
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN       #
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE         #
# POSSIBILITY OF SUCH DAMAGE.                                             #
# #########################################################################

"""
Module for image merging
"""

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging
import six
import operator, time
import numpy as np
import scipy
from scipy.stats import norm
from scipy.ndimage.filters import gaussian_filter
from scipy.signal import convolve2d
from scipy.sparse import csc_matrix
import scipy.sparse.linalg as lng
from itertools import izip
import gc
import tomosaic.register.morph as morph
import dxchange

logger = logging.getLogger(__name__)

__author__ = "Rafael Vescovi"
__credits__ = "Doga Gursoy"
__copyright__ = "Copyright (c) 2015, UChicago Argonne, LLC."
__docformat__ = 'restructuredtext en'
__all__ = ['blend',
           'img_merge_alpha',
           'img_merge_max',
           'img_merge_min',
           'img_merge_poisson',
           'img_merge_pyramid',]


def blend(img1, img2, shift, method, **kwargs):
    """
    Blend images.
    Parameters
    ----------
    img1, img2 : ndarray
        3D tomographic data.
    shift : array
        Projection angles in radian.

    method : {str, function}
        One of the following string values.
        'alpha'
        'max'
        'min'
        'poison'
        'pyramid'

    filter_par: list, optional
        Filter parameters as a list.
    Returns
    -------
    ndarray
        Reconstructed 3D object.
    """

    allowed_kwargs = {
    'alpha': ['alpha'],
    'max': [],
    'min': [],
    'poisson': [],
    'pyramid': ['blur', 'margin', 'depth'],
    }

    generic_kwargs = []
    # Generate kwargs for the algorithm.
    kwargs_defaults = _get_algorithm_kwargs()

    if isinstance(method, six.string_types):

        # Check whether we have an allowed method
        if method not in allowed_kwargs:
            raise ValueError(
                'Keyword "method" must be one of %s, or a Python method.' %
                (list(allowed_kwargs.keys()),))

        # Make sure have allowed kwargs appropriate for algorithm.
        for key, value in list(kwargs.items()):
            if key not in allowed_kwargs[method]:
                raise ValueError(
                    '%s keyword not in allowed keywords %s' %
                    (key, allowed_kwargs[method]))
            else:
                # Make sure they are numpy arrays.
                if not isinstance(kwargs[key], (np.ndarray, np.generic)) and not isinstance(kwargs[key], six.string_types):
                    kwargs[key] = np.array(value)

                # Make sure reg_par and filter_par is float32.
                if key == 'alpha':
                    if not isinstance(kwargs[key], np.float32):
                        kwargs[key] = np.array(value, dtype='float32')
                # if key == 'blur':
                #     if not isinstance(kwargs[key], np.float32):
                #         kwargs[key] = np.array(value, dtype='float32')
        # Set kwarg defaults.
        for kw in allowed_kwargs[method]:
            kwargs.setdefault(kw, kwargs_defaults[kw])

    elif hasattr(method, '__call__'):
    # Set kwarg defaults.
        for kw in generic_kwargs:
            kwargs.setdefault(kw, kwargs_defaults[kw])
    else:
       raise ValueError(
            'Keyword "method" must be one of %s, or a Python method.' %
           (list(allowed_kwargs.keys()),))

    func = _get_func(method)
    return func(img1, img2, shift, **kwargs)

def _get_func(method):
    if method == 'alpha':
        func = img_merge_alpha
    elif method == 'max':
        func = img_merge_max
    elif method == 'min':
        func = img_merge_min
    elif method == 'poisson':
        func = img_merge_poisson
    elif method == 'pyramid':
        func = img_merge_pyramid
    return func

def _get_algorithm_kwargs():
    return {'alpha': 1, 'blur': 0.4, 'margin': 50, 'depth': 4}

def img_merge_alpha(img1, img2, shift, alpha=0.4):
    """
    Change dynamic range of values in an array.

    Parameters
    ----------
        Output array.
        :param img1:
        :param img2:
        :param shift:
        :param alpha:

    Returns
    -------
    ndarray
    """
    print('Alpha Blend = ' + str(alpha))
    newimg1 = morph.arrange_image(img1, img2, shift, order=1)
    newimg2 = morph.arrange_image(img1, img2, shift, order=2)
    final_img = alpha * newimg1 + (1 - alpha) * newimg2
    return final_img


def img_merge_max(img1, img2, shift):
    """
    Change dynamic range of values in an array.

    Parameters
    ----------
        :param img1:
        :param img2:
        :param shift:

    Returns
    -------
    ndarray
        Output array.
    """
    print('Max Blend')
    newimg1 = morph.arrange_image(img1, img2, shift, order=1)
    newimg2 = morph.arrange_image(img1, img2, shift, order=2)
    buff = np.dstack((newimg1, newimg2))
    final_img = buff.max(2)

    return final_img



def img_merge_min(img1, img2, shift):
    """
    Change dynamic range of values in an array.

    Parameters
    ----------
        :param img1:
        :param img2:
        :param shift:

    Returns
    -------
    ndarray
        Output array.
    """
    newimg1 = morph.arrange_image(img1, img2, shift, order=1)
    newimg2 = morph.arrange_image(img1, img2, shift, order=2)
    buff = np.dstack((newimg1, newimg2))
    final_img = buff.min(2)

    return final_img


# Modified for subpixel fourier shift.
def img_merge_poisson(img1, img2, shift):
    newimg = morph.arrange_image(img1, img2, shift)
    if abs(shift[0]) < 10 and abs(shift[1]) < 10:
        return newimg
    # Get corner positions for img2 INCLUDING boundary.
    shape = np.squeeze(img2.shape)
    corner = _get_corner(morph.get_roughshift(shift), shape)
    img2_boo_part = _find_bound(shape, corner, newimg)
    img2_boo = np.ones([shape[0], shape[1]], dtype='bool')
    img2_boo[0, :] = False
    img2_boo[:, 0] = False
    img2_boo[-1, :] = False
    img2_boo[:, -1] = False
    # Overwrite overlapping boundary with img1
    bound_y, bound_x = np.nonzero(np.invert(img2_boo_part))
    bound_y += corner[0, 0]
    bound_x += corner[0, 1]
    newimg[[bound_y, bound_x]] = img1[[bound_y, bound_x]]
    # Embroider non-overlapping part with blurred img2
    bound_y, bound_x = np.nonzero(np.invert(img2_boo) - np.invert(img2_boo_part))
    img2_blur = scipy.ndimage.filters.gaussian_filter(img2, 10)
    bound_y += corner[0, 0]
    bound_x += corner[0, 1]
    newimg[[bound_y, bound_x]] = img2_blur[[bound_y - corner[0, 0], bound_x - corner[0, 1]]]
    ##
    spot = newimg[corner[0, 0]:corner[1, 0] + 1, corner[0, 1]:corner[1, 1] + 1]
    print("    Blend: Building matrix... ", end="")
    t0 = time.time()
    A = _matrix_builder(img2_boo)
    print("Done in " + str(time.time() - t0) + " sec.")
    print("    Blend: Building constant vector... ", end="")
    t0 = time.time()
    b = _const_builder(img2_boo, spot, img2)
    print("Done in " + str(time.time() - t0) + " sec.")
    print("    Blend: Solving linear system... ", end="")
    t0 = time.time()
    x = lng.bicg(A, b)[0]
    print("Done in " + str(time.time() - t0) + " sec.")
    spot[img2_boo] = x
    newimg[corner[0, 0]:corner[1, 0] + 1, corner[0, 1]:corner[1, 1] + 1] = spot
    return newimg


# Return a Boolean matrix with equal size to img2, with True for interior and False for boundary (d-Omega).
# shape: shape array of img2.
# corner: corner pixel indices of img2 in full image space.
def _find_bound(shape, corner, newimg):
    img2_boo = np.ones(shape).astype('bool')
    newimg_expand = np.zeros([newimg.shape[0] + 2, newimg.shape[1] + 2])
    newimg_expand[:, :] = np.NaN
    newimg_expand[1:-1, 1:-1] = newimg
    corner = corner + [[1, 1], [1, 1]]
    # Top edge
    for i, j in izip(range(corner[0, 1], corner[1, 1] + 1), range(shape[1])):
        if not np.isnan(newimg_expand[corner[0, 0] - 1, i]):
            img2_boo[0, j] = False
    # Right edge
    for i, j in izip(range(corner[0, 0], corner[1, 0] + 1), range(shape[0])):
        if not np.isnan(newimg_expand[i, corner[1, 1] + 1]):
            img2_boo[j, -1] = False
    # Bottom edge
    for i, j in izip(range(corner[0, 1], corner[1, 1] + 1), range(shape[1])):
        if not np.isnan(newimg_expand[corner[1, 0] + 1, i]):
            img2_boo[-1, j] = False
    # Left edge
    for i, j in izip(range(corner[0, 0], corner[1, 0] + 1), range(shape[0])):
        if not np.isnan(newimg_expand[i, corner[0, 1] - 1]):
            img2_boo[j, 0] = False
    return img2_boo


# Return coordinates of the top right and bottom left pixels of an image in the expanded full image space. Both
# pixels are WITHIN the domain of the pasted image.
def _get_corner(shift, img2_shape):
    corner_uly, corner_ulx, corner_bry, corner_brx = (shift[0], shift[1], shift[0] + img2_shape[0] - 1,
                                                      shift[1] + img2_shape[1] - 1)
    return np.squeeze([[corner_uly, corner_ulx], [corner_bry, corner_brx]]).astype('int')


# Build sparse square matrix A in Poisson equation Ax = b.
def _matrix_builder(img2_boo):
    n_mat = np.count_nonzero(img2_boo)
    shape = img2_boo.shape
    img2_count = np.zeros([shape[0], shape[1]])
    img2_count[:, :] = 4
    img2_count[:, 0] -= 1
    img2_count[0, :] -= 1
    img2_count[:, -1] -= 1
    img2_count[-1, :] -= 1
    data = img2_count[img2_boo]
    y_ind = np.arange(n_mat)
    x_ind = np.arange(n_mat)
    ##
    img2_count_expand = np.zeros([shape[0] + 2, shape[1] + 2], dtype='int')
    img2_count_expand[1:-1, 1:-1] = img2_boo.astype('int')
    img2_u = np.roll(img2_count_expand, 1, axis=0)
    img2_d = np.roll(img2_count_expand, -1, axis=0)
    img2_l = np.roll(img2_count_expand, 1, axis=1)
    img2_r = np.roll(img2_count_expand, -1, axis=1)
    img2_u = img2_u[1:-1, 1:-1]
    img2_d = img2_d[1:-1, 1:-1]
    img2_l = img2_l[1:-1, 1:-1]
    img2_r = img2_r[1:-1, 1:-1]
    img2_u = img2_u[img2_boo]
    img2_d = img2_d[img2_boo]
    img2_l = img2_l[img2_boo]
    img2_r = img2_r[img2_boo]
    row_int = shape[1] - 2
    count = 0
    y_ind_app = np.squeeze(np.nonzero(img2_u))
    x_ind_app = y_ind_app - row_int
    y_ind = np.append(y_ind, y_ind_app)
    x_ind = np.append(x_ind, x_ind_app)
    count += len(x_ind_app)
    y_ind_app = np.squeeze(np.nonzero(img2_d))
    x_ind_app = y_ind_app + row_int
    y_ind = np.append(y_ind, y_ind_app)
    x_ind = np.append(x_ind, x_ind_app)
    count += len(x_ind_app)
    y_ind_app = np.squeeze(np.nonzero(img2_l))
    x_ind_app = y_ind_app - 1
    y_ind = np.append(y_ind, y_ind_app)
    x_ind = np.append(x_ind, x_ind_app)
    count += len(x_ind_app)
    y_ind_app = np.squeeze(np.nonzero(img2_r))
    x_ind_app = y_ind_app + 1
    y_ind = np.append(y_ind, y_ind_app)
    x_ind = np.append(x_ind, x_ind_app)
    count += len(x_ind_app)
    data_app = np.zeros(count)
    data_app[:] = -1
    data = np.append(data, data_app)
    A = csc_matrix((data, (y_ind, x_ind)), shape=(n_mat, n_mat))
    return A


# Build the constant column b in Ax = b. Panorama is built from left to right, from top tp bottom by default.
# img1_bound can be any matrix with equal size to img2 as long as the boundary position is filled with img1.
def _const_builder(img2_boo, img1_bound, img2):
    n_mat = np.count_nonzero(img2_boo)
    shape = img2_boo.shape
    img2_bound_boo = np.invert(img2_boo)
    img2_bound = np.zeros([shape[0], shape[1]])
    img2_bound[img2_bound_boo] = img1_bound[img2_bound_boo]
    img2_bound_expand = np.zeros([shape[0] + 2, shape[1] + 2])
    img2_bound_expand[1:-1, 1:-1] = img2_bound
    img2_bound_expand = _circ_neighbor(img2_bound_expand)
    img2_bound = img2_bound_expand[1:-1, 1:-1]
    b = img2_bound[img2_boo]
    ##
    img2_expand = np.zeros([shape[0] + 2, shape[1] + 2])
    img2_expand[1:-1, 1:-1] = img2
    img2_expand = 4 * img2_expand - _circ_neighbor(img2_expand)
    img2 = img2_expand[1:-1, 1:-1]
    b += img2[img2_boo]
    return b


# Find the sum of neighbors assuming periodic boundary. Pad the input matrix with 0 when necessary.
def _circ_neighbor(mat):
    return np.roll(mat, 1, axis=0) + np.roll(mat, -1, axis=0) + np.roll(mat, 1, axis=1) + np.roll(mat, -1, axis=1)


# Pyramid blend.
# Codes are adapted from Computer Vision Lab, Image blending using pyramid, https://compvisionlab.wordpress.com/2013/
# 05/13/image-blending-using-pyramid/.
def img_merge_pyramid(img1, img2, shift, margin=100, blur=0.4, depth=4):
    t00 = time.time()
    t0 = time.time()
    print(    'Starting pyramid blend...')
    newimg = morph.arrange_image(img1, img2, shift)
    #test_out(newimg.astype(np.float32), '/raid/data/xbrainmap/FullBrain/fly_mosaic_OsPb_Test1/')
    if abs(shift[0]) < margin and abs(shift[1]) < margin:
        return newimg
    rough_shift = morph.get_roughshift(shift)
    print('    Blend: Image aligned and built in', str(time.time() - t0))
    ##
    t0 = time.time()
    corner = _get_corner(rough_shift, img2.shape)
    # for new image with overlap at left and top 
    if abs(rough_shift[1]) > margin and abs(rough_shift[0]) > margin:
        temp0 = img2.shape[0] if corner[1, 0] <= img1.shape[0] - 1 else img1.shape[0] - corner[0, 0]
        temp1 = img2.shape[1] if corner[1, 1] <= img1.shape[1] - 1 else img1.shape[1] - corner[0, 1]
        mask2 = np.zeros([temp0, temp1])
        mask2[:, :] = np.nan
        temp = img1[corner[0, 0]:corner[0, 0] + temp0, corner[0, 1]:corner[0, 1] + temp1]
        temp = np.isfinite(temp)
        wid_ver = np.count_nonzero(temp[:, -1])
        wid_hor = np.count_nonzero(temp[-1, :])
        mask2[:wid_ver, :] = 1
        mask2[:, :wid_hor] = 1
        buffer1 = img1[corner[0, 0]:corner[0, 0] + mask2.shape[0], corner[0, 1]:corner[0, 1] + mask2.shape[1]]
        buffer2 = img2[:mask2.shape[0], :mask2.shape[1]]
    # for new image with overlap at top only
    elif abs(rough_shift[1]) < margin and abs(rough_shift[0]) > margin:
        abs_height = np.count_nonzero(np.isfinite(img1[:, margin]))
        wid_ver = abs_height - corner[0, 0]
        wid_hor = img2.shape[1] if img1.shape[1] > img2.shape[1] else img2.shape[1] - corner[0, 1]
        mask2 = np.ones([wid_ver, wid_hor])
        buffer1 = img1[corner[0, 0]:corner[0, 0] + wid_ver, corner[0, 1]:corner[0, 1] + wid_hor]
        buffer2 = img2[:wid_ver, :wid_hor]
    # for new image with overlap at left only
    else:
        abs_width = np.count_nonzero(np.isfinite(img1[margin, :]))
        wid_ver = img2.shape[0] - corner[0, 0]
        wid_hor = abs_width - corner[0, 1]
        mask2 = np.ones([wid_ver, wid_hor])
        buffer1 = img1[corner[0, 0]:corner[0, 0] + wid_ver, corner[0, 1]:corner[0, 1] + wid_hor]
        buffer2 = img2[:wid_ver, :wid_hor]
    if abs(rough_shift[1]) > margin:
        mask2[:, :int(wid_hor / 2)] = 0
    if abs(rough_shift[0]) > margin:
        mask2[:int(wid_ver / 2), :] = 0
    ##
    buffer1[np.isnan(buffer1)] = 0
    mask2[np.isnan(mask2)] = 1
    t0 = time.time()
    gauss_mask = _gauss_pyramid(mask2.astype('float'), depth, blur, mask=True)
    gauss1 = _gauss_pyramid(buffer1, depth, blur)
    gauss2 = _gauss_pyramid(buffer2, depth, blur)
    lapl1 = _lapl_pyramid(gauss1, blur)
    lapl2 = _lapl_pyramid(gauss2, blur)
    ovlp_blended = _collapse(_blend(lapl2, lapl1, gauss_mask), blur)
    print('    Blend: Blending done in', str(time.time() - t0), 'sec.')
    ##
    if abs(rough_shift[1]) > margin and abs(rough_shift[0]) > margin:
        newimg[corner[0, 0]:corner[0, 0] + wid_ver, corner[0, 1]:corner[0, 1] + mask2.shape[1]] = \
            ovlp_blended[:wid_ver, :]
        newimg[corner[0, 0] + wid_ver:corner[0, 0] + mask2.shape[0], corner[0, 1]:corner[0, 1] + wid_hor] = \
            ovlp_blended[wid_ver:, :wid_hor]
    else:
        newimg[corner[0, 0]:corner[0, 0] + wid_ver, corner[0, 1]:corner[0, 1] + wid_hor] = ovlp_blended
    print('    Blend: Done with this tile in', str(time.time() - t00), 'sec.')
    gc.collect()
    return newimg


def _generating_kernel(a):
    w_1d = np.array([0.25 - a / 2.0, 0.25, a, 0.25, 0.25 - a / 2.0])
    return np.outer(w_1d, w_1d)


def _ireduce(image, blur):
    kernel = _generating_kernel(blur)
    outimage = scipy.signal.convolve2d(image, kernel, mode='same', boundary='symmetric')
    out = outimage[::2, ::2]
    return out


def _iexpand(image, blur):
    kernel = _generating_kernel(blur)
    outimage = np.zeros((image.shape[0] * 2, image.shape[1] * 2), dtype=np.float64)
    outimage[::2, ::2] = image[:, :]
    out = 4 * scipy.signal.convolve2d(outimage, kernel, mode='same', boundary='symmetric')
    return out


def _gauss_pyramid(image, levels, blur, mask=False):
    output = []
    if mask:
        image = gaussian_filter(image, 20)
    output.append(image)
    tmp = np.copy(image)
    for i in range(0, levels):
        tmp = _ireduce(tmp, blur)
        output.append(tmp)
    return output


def _lapl_pyramid(gauss_pyr, blur):
    output = []
    k = len(gauss_pyr)
    for i in range(0, k - 1):
        gu = gauss_pyr[i]
        egu = _iexpand(gauss_pyr[i + 1], blur)
        if egu.shape[0] > gu.shape[0]:
            egu = np.delete(egu, (-1), axis=0)
        if egu.shape[1] > gu.shape[1]:
            egu = np.delete(egu, (-1), axis=1)
        output.append(gu - egu)
    output.append(gauss_pyr.pop())
    return output


def _blend(lapl_pyr_white, lapl_pyr_black, gauss_pyr_mask):
    blended_pyr = []
    k = len(gauss_pyr_mask)
    for i in range(0, k):
        p1 = gauss_pyr_mask[i] * lapl_pyr_white[i]
        p2 = (1 - gauss_pyr_mask[i]) * lapl_pyr_black[i]
        blended_pyr.append(p1 + p2)
    return blended_pyr


def _collapse(lapl_pyr, blur):
    output = np.zeros((lapl_pyr[0].shape[0], lapl_pyr[0].shape[1]), dtype=np.float64)
    for i in range(len(lapl_pyr) - 1, 0, -1):
        lap = _iexpand(lapl_pyr[i], blur)
        lapb = lapl_pyr[i - 1]
        if lap.shape[0] > lapb.shape[0]:
            lap = np.delete(lap, (-1), axis=0)
        if lap.shape[1] > lapb.shape[1]:
            lap = np.delete(lap, (-1), axis=1)
        tmp = lap + lapb
        lapl_pyr.pop()
        lapl_pyr.pop()
        lapl_pyr.append(tmp)
        output = tmp
    return output
