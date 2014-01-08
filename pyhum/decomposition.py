## -*- coding: utf8 -*-
## Copyright (c) 2014 Júlio Hoffimann Mendes
##
## This file is part of HUM.
##
## HUM is free software: you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
##
## HUM is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with HUM.  If not, see <http://www.gnu.org/licenses/>.
##
## Created: 06 Jan 2014
## Author: Júlio Hoffimann Mendes

import numpy as np
from scipy.linalg import eigh, norm

class KernelPCA(object):
    """
    Kernel Principal Component Analysis (kPCA)

    The algorithm is implemented for kernels of the form:

      k(x,y) = <x,y> + <x,y>^2 + ... + <x,y>^d

    Such kernels were proposed by Sarma et. al for petroleum engineering
    problems. They aren't available on any of the Python libraries for
    Machine Learning (sklearn, mlpy, etc.)

    The code is based on a matricial formulation I developed myself during
    my Master's dissertation which can be found on the WWW. Please refer
    to the appendices.

    Parameters
    ----------
    degree: int, optional
        Degree of the kernel function

    References
    ----------
      MENDES, J. H.; WILLMERSDORF, R. B.; ARAUJO, E. R., 2014. The Inverse
      Problem of History Matching - A Probabilistic Framework for Reservoir
      Characterization and Real Time Updating.

      SCHÖLKOPF, B.; SMOLA, A.; MÜLLER, K., 1996. Nonlinear Component
      Analysis as a Kernel Eigenvalue Problem.

      SCHÖLKOPF, B.; MIKA, S.; SMOLA, A.; RÄTSCH, G.; MÜLLER, K.
      Kernel PCA Pattern Reconstruction via Approximate Pre-Images.

      SARMA, P.; DURLOFSKY, L. J.; KHALID, A., 2007. Kernel Principal
      Component Analysis for Efficient, Differentiable Parametrization
      of Multipoint Geostatistics.
    """
    def __init__(self, degree=1):
        assert degree > 0, "Degree must be integer greater than zero"
        self._d = degree


    def train(self, X, ncomps=None):
        """
        Solve the eigenproblem and stores the basis for future predictions.

        Parameters
        ----------
        X: ndarray or matrix
            Data matrix (nfeatures x nsamples).

        ncomps: int or None
            Number of components (0 < ncomps <= nsamples). If None, all
            eigenvalues below a threshold are discarded.
            Default: None
        """
        m = X.shape[1]

        # k(x,y) = <x,y> + <x,y>^2 + ... + <x,y>^d
        K = np.matrix(np.polyval(np.ones(self._d+1), np.dot(X.T, X)) - 1)

        # center in the feature space
        ones = 1./m * np.ones([m,m])
        K = K - (ones*K + K*ones) + ones*K*ones

        # enforce symmetry
        K = (K + K.T) / 2.

        # The kernel Gramian matrix is positive semidefinite,
        # all eigenvalues are nonnegative.
        if ncomps is None:
            # discard eigenvalues below a threshold
            lambdas, V = eigh(K, overwrite_a=True)
            idx = lambdas >= 1e-8
            lambdas = lambdas[idx]
            V = V[:,idx]
        else:
            # retain the desired number of components
            assert 0 < ncomps and ncomps <= m, "ncomps is not valid"
            lambdas, V = eigh(K, overwrite_a=True, eigvals=(m-ncomps,m-1))

        # normalize
        self.eigbasis = np.dot(V, np.diag(1./np.sqrt(lambdas)))

        # stores a reference to the data
        self.X = X


    def predict(self, csi, tol=1e-8, ntries=100):
        """
        Given a set of randomly generated (and uncorrelated) coordinates,
        reconstruct a plausible image using the just trained eigenbasis.

        Note that almost always the number of coordinates is chosen to be
        smaller than the number of samples in the training set.

        Parameters
        ----------
        csi: array
            Coordinates for the eigenbasis (ncomps)

        Returns
        -------
        x: array
            A valid reconstructed image as those found in the data matrix
        """
        A = self.eigbasis

        assert A.shape[1] == csi.size, "Invalid number of coordinates"

        # linear kernel has closed form
        if self._d == 1:
            b = np.dot(A, csi)
            return np.dot(self.X, b / sum(b))
        else:
            b = np.dot(A, csi)
            guess = np.mean(self.X, 1) + np.random.randn(self.X.shape[0])
            return self._fixed_point(guess, b, tol, ntries)


    def denoise(self, x, tol=1e-8, ntries=100):
        """
        Given a valid image, for example any of the images in the data matrix or a
        predicted image, removes the noise contained in the lowest-eigenvalue components.

        Parameters
        ----------
        x: array
            Valid image to be denoised (nfeatures)

        Returns
        -------
        x_clean: array
            Denoised version of x
        """
        A = self.eigbasis

        # linear kernel has closed form
        if self._d == 1:
            b = np.dot(A, np.dot(A.T, np.dot(self.X.T, x)))
            return np.dot(self.X, b / sum(b))
        else:
            Kx = np.polyval(np.ones(self._d+1), np.dot(self.X.T, x)) - 1

            b = np.dot(A, np.dot(A.T, Kx))
            guess = x + np.random.randn(x.size)
            return self._fixed_point(guess, b, tol, ntries)


    # Fixed point iteration for the preimage problem
    def _fixed_point(self, guess, b, tol, ntries):
        coeffs = range(self._d, 0, -1)
        preimg = guess
        for _ in xrange(ntries):
            z = preimg
            c = np.dot(np.diag(np.polyval(coeffs, np.dot(self.X.T, z)) / np.polyval(coeffs, np.dot(z, z))), b)
            preimg = np.dot(self.X, c / sum(c))
            if norm(preimg-z) / norm(z) < tol:
                break

        return preimg