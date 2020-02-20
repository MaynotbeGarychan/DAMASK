import numpy as np

from . import Lambert

P = -1

####################################################################################################
class Rotation:
    u"""
    Orientation stored with functionality for conversion to different representations.

    References
    ----------
    D. Rowenhorst et al., Modelling and Simulation in Materials Science and Engineering 23:083501, 2015
    https://doi.org/10.1088/0965-0393/23/8/083501

    Conventions
    -----------
    Convention 1: Coordinate frames are right-handed.
    Convention 2: A rotation angle ω is taken to be positive for a counterclockwise rotation
                  when viewing from the end point of the rotation axis towards the origin.
    Convention 3: Rotations will be interpreted in the passive sense.
    Convention 4: Euler angle triplets are implemented using the Bunge convention,
                  with the angular ranges as [0, 2π],[0, π],[0, 2π].
    Convention 5: The rotation angle ω is limited to the interval [0, π].
    Convention 6: the real part of a quaternion is positive, Re(q) > 0
    Convention 7: P = -1 (as default).

    Usage
    -----
    Vector "a" (defined in coordinate system "A") is passively rotated
               resulting in new coordinates "b" when expressed in system "B".
    b = Q * a
    b = np.dot(Q.asMatrix(),a)

    """

    __slots__ = ['quaternion']

    def __init__(self,quaternion = np.array([1.0,0.0,0.0,0.0])):
        """
        Initializes to identity unless specified.

        Parameters
        ----------
        quaternion : numpy.ndarray, optional
            Unit quaternion that follows the conventions. Use .fromQuaternion to perform a sanity check.

        """
        self.quaternion = quaternion.copy()

    def __copy__(self):
        """Copy."""
        return self.__class__(self.quaternion)

    copy = __copy__


    def __repr__(self):
        """Orientation displayed as unit quaternion, rotation matrix, and Bunge-Euler angles."""
        return '\n'.join([
               'Quaternion: (real={:.3f}, imag=<{:+.3f}, {:+.3f}, {:+.3f}>)'.format(*(self.quaternion)),
               'Matrix:\n{}'.format(self.asMatrix()),
               'Bunge Eulers / deg: ({:3.2f}, {:3.2f}, {:3.2f})'.format(*self.asEulers(degrees=True)),
                ])


    def __mul__(self, other):
        """
        Multiplication.

        Parameters
        ----------
        other : numpy.ndarray or Rotation
            Vector, second or fourth order tensor, or rotation object that is rotated.

        Todo
        ----
        Document details active/passive)
        considere rotation of (3,3,3,3)-matrix

        """
        if isinstance(other, Rotation):                                                             # rotate a rotation
            self_q  = self.quaternion[0]
            self_p  = self.quaternion[1:]
            other_q = other.quaternion[0]
            other_p = other.quaternion[1:]
            R = self.__class__(np.append(self_q*other_q - np.dot(self_p,other_p),
                                         self_q*other_p + other_q*self_p + P * np.cross(self_p,other_p)))
            return R.standardize()
        elif isinstance(other, (tuple,np.ndarray)):
            if isinstance(other,tuple) or other.shape == (3,):                                      # rotate a single (3)-vector or meshgrid
                A = self.quaternion[0]**2.0 - np.dot(self.quaternion[1:],self.quaternion[1:])
                B = 2.0 * (  self.quaternion[1]*other[0]
                           + self.quaternion[2]*other[1]
                           + self.quaternion[3]*other[2])
                C = 2.0 * P*self.quaternion[0]

                return np.array([
                  A*other[0] + B*self.quaternion[1] + C*(self.quaternion[2]*other[2] - self.quaternion[3]*other[1]),
                  A*other[1] + B*self.quaternion[2] + C*(self.quaternion[3]*other[0] - self.quaternion[1]*other[2]),
                  A*other[2] + B*self.quaternion[3] + C*(self.quaternion[1]*other[1] - self.quaternion[2]*other[0]),
                  ])
            elif other.shape == (3,3,):                                                             # rotate a single (3x3)-matrix
                return np.dot(self.asMatrix(),np.dot(other,self.asMatrix().T))
            elif other.shape == (3,3,3,3,):
                raise NotImplementedError
            else:
                return NotImplemented
        else:
            return NotImplemented


    def inverse(self):
        """In-place inverse rotation/backward rotation."""
        self.quaternion[1:] *= -1
        return self

    def inversed(self):
        """Inverse rotation/backward rotation."""
        return self.copy().inverse()


    def standardize(self):
        """In-place quaternion representation with positive q."""
        if self.quaternion[0] < 0.0: self.quaternion*=-1
        return self

    def standardized(self):
        """Quaternion representation with positive q."""
        return self.copy().standardize()


    def misorientation(self,other):
        """
        Get Misorientation.

        Parameters
        ----------
        other : Rotation
            Rotation to which the misorientation is computed.

        """
        return other*self.inversed()


    def average(self,other):
        """
        Calculate the average rotation.

        Parameters
        ----------
        other : Rotation
            Rotation from which the average is rotated.

        """
        return Rotation.fromAverage([self,other])


    ################################################################################################
    # convert to different orientation representations (numpy arrays)

    def asQuaternion(self):
        """
        Unit quaternion [q, p_1, p_2, p_3] unless quaternion == True: damask.quaternion object.

        Parameters
        ----------
        quaternion : bool, optional
            return quaternion as DAMASK object.

        """
        return self.quaternion

    def asEulers(self,
                 degrees = False):
        """
        Bunge-Euler angles: (φ_1, ϕ, φ_2).

        Parameters
        ----------
        degrees : bool, optional
            return angles in degrees.

        """
        eu = qu2eu(self.quaternion)
        if degrees: eu = np.degrees(eu)
        return eu

    def asAxisAngle(self,
                    degrees = False,
                    pair = False):
        """
        Axis angle representation [n_1, n_2, n_3, ω] unless pair == True: ([n_1, n_2, n_3], ω).

        Parameters
        ----------
        degrees : bool, optional
            return rotation angle in degrees.
        pair : bool, optional
            return tuple of axis and angle.

        """
        ax = qu2ax(self.quaternion)
        if degrees: ax[3] = np.degrees(ax[3])
        return (ax[:3],np.degrees(ax[3])) if pair else ax

    def asMatrix(self):
        """Rotation matrix."""
        return qu2om(self.quaternion)

    def asRodrigues(self,
                    vector = False):
        """
        Rodrigues-Frank vector representation [n_1, n_2, n_3, tan(ω/2)] unless vector == True:
        [n_1, n_2, n_3] * tan(ω/2).

        Parameters
        ----------
        vector : bool, optional
            return as actual Rodrigues--Frank vector, i.e. rotation axis scaled by tan(ω/2).

        """
        ro = qu2ro(self.quaternion)
        return ro[:3]*ro[3] if vector else ro

    def asHomochoric(self):
        """Homochoric vector: (h_1, h_2, h_3)."""
        return qu2ho(self.quaternion)

    def asCubochoric(self):
        """Cubochoric vector: (c_1, c_2, c_3)."""
        return qu2cu(self.quaternion)

    def asM(self):
        """
        Intermediate representation supporting quaternion averaging.

        References
        ----------
        F. Landis Markley et al., Journal of Guidance, Control, and Dynamics 30(4):1193-1197, 2007
        https://doi.org/10.2514/1.28949

        """
        return np.outer(self.quaternion,self.quaternion)


    ################################################################################################
    # static constructors. The input data needs to follow the convention, options allow to
    # relax these convections
    @staticmethod
    def fromQuaternion(quaternion,
                       acceptHomomorph = False,
                       P = -1):

        qu =   quaternion if isinstance(quaternion,np.ndarray) and quaternion.dtype == np.dtype(float) \
                          else np.array(quaternion,dtype=float)
        if P > 0: qu[1:4] *= -1                                                                     # convert from P=1 to P=-1
        if qu[0] < 0.0:
            if acceptHomomorph:
                qu *= -1.
            else:
                raise ValueError('Quaternion has negative first component.\n{}'.format(qu[0]))
        if not np.isclose(np.linalg.norm(qu), 1.0):
            raise ValueError('Quaternion is not of unit length.\n{} {} {} {}'.format(*qu))

        return Rotation(qu)

    @staticmethod
    def fromEulers(eulers,
                   degrees = False):

        eu = eulers if isinstance(eulers, np.ndarray) and eulers.dtype == np.dtype(float) \
                    else np.array(eulers,dtype=float)
        eu = np.radians(eu) if degrees else eu
        if np.any(eu < 0.0) or np.any(eu > 2.0*np.pi) or eu[1] > np.pi:
            raise ValueError('Euler angles outside of [0..2π],[0..π],[0..2π].\n{} {} {}.'.format(*eu))

        return Rotation(eu2qu(eu))

    @staticmethod
    def fromAxisAngle(angleAxis,
                      degrees = False,
                      normalise = False,
                      P = -1):

        ax = angleAxis if isinstance(angleAxis, np.ndarray) and angleAxis.dtype == np.dtype(float) \
                       else np.array(angleAxis,dtype=float)
        if P > 0:     ax[0:3] *= -1                                                                 # convert from P=1 to P=-1
        if degrees:   ax[  3]  = np.radians(ax[3])
        if normalise: ax[0:3] /= np.linalg.norm(ax[0:3])
        if ax[3] < 0.0 or ax[3] > np.pi:
            raise ValueError('Axis angle rotation angle outside of [0..π].\n'.format(ax[3]))
        if not np.isclose(np.linalg.norm(ax[0:3]), 1.0):
            raise ValueError('Axis angle rotation axis is not of unit length.\n{} {} {}'.format(*ax[0:3]))

        return Rotation(ax2qu(ax))

    @staticmethod
    def fromBasis(basis,
                  orthonormal = True,
                  reciprocal = False,
                 ):

        om = basis if isinstance(basis, np.ndarray) else np.array(basis).reshape((3,3))
        if reciprocal:
            om = np.linalg.inv(om.T/np.pi)                                                          # transform reciprocal basis set
            orthonormal = False                                                                     # contains stretch
        if not orthonormal:
            (U,S,Vh) = np.linalg.svd(om)                                                            # singular value decomposition
            om = np.dot(U,Vh)
        if not np.isclose(np.linalg.det(om),1.0):
            raise ValueError('matrix is not a proper rotation.\n{}'.format(om))
        if    not np.isclose(np.dot(om[0],om[1]), 0.0) \
           or not np.isclose(np.dot(om[1],om[2]), 0.0) \
           or not np.isclose(np.dot(om[2],om[0]), 0.0):
            raise ValueError('matrix is not orthogonal.\n{}'.format(om))

        return Rotation(om2qu(om))

    @staticmethod
    def fromMatrix(om,
                  ):

        return Rotation.fromBasis(om)

    @staticmethod
    def fromRodrigues(rodrigues,
                      normalise = False,
                      P = -1):

        ro = rodrigues if isinstance(rodrigues, np.ndarray) and rodrigues.dtype == np.dtype(float) \
                       else np.array(rodrigues,dtype=float)
        if P > 0:     ro[0:3] *= -1                                                                 # convert from P=1 to P=-1
        if normalise: ro[0:3] /= np.linalg.norm(ro[0:3])
        if not np.isclose(np.linalg.norm(ro[0:3]), 1.0):
            raise ValueError('Rodrigues rotation axis is not of unit length.\n{} {} {}'.format(*ro[0:3]))
        if ro[3] < 0.0:
            raise ValueError('Rodriques rotation angle not positive.\n'.format(ro[3]))

        return Rotation(ro2qu(ro))

    @staticmethod
    def fromHomochoric(homochoric,
                       P = -1):

        ho = homochoric if isinstance(homochoric, np.ndarray) and homochoric.dtype == np.dtype(float) \
                        else np.array(homochoric,dtype=float)
        if P > 0: ho *= -1                                                                          # convert from P=1 to P=-1

        return Rotation(ho2qu(ho))

    @staticmethod
    def fromCubochoric(cubochoric,
                       P = -1):

        cu = cubochoric if isinstance(cubochoric, np.ndarray) and cubochoric.dtype == np.dtype(float) \
                        else np.array(cubochoric,dtype=float)
        ho = cu2ho(cu)
        if P > 0: ho *= -1                                                                          # convert from P=1 to P=-1

        return Rotation(ho2qu(ho))


    @staticmethod
    def fromAverage(rotations,
                    weights = []):
        """
        Average rotation.

        References
        ----------
        F. Landis Markley et al., Journal of Guidance, Control, and Dynamics 30(4):1193-1197, 2007
        https://doi.org/10.2514/1.28949

        Parameters
        ----------
        rotations : list of Rotations
            Rotations to average from
        weights : list of floats, optional
            Weights for each rotation used for averaging

        """
        if not all(isinstance(item, Rotation) for item in rotations):
          raise TypeError("Only instances of Rotation can be averaged.")

        N = len(rotations)
        if weights == [] or not weights:
            weights = np.ones(N,dtype='i')

        for i,(r,n) in enumerate(zip(rotations,weights)):
            M =          r.asM() * n if i == 0 \
                else M + r.asM() * n                                                                # noqa add (multiples) of this rotation to average noqa
        eig, vec = np.linalg.eig(M/N)

        return Rotation.fromQuaternion(np.real(vec.T[eig.argmax()]),acceptHomomorph = True)


    @staticmethod
    def fromRandom():
        r = np.random.random(3)
        A = np.sqrt(r[2])
        B = np.sqrt(1.0-r[2])
        return Rotation(np.array([np.cos(2.0*np.pi*r[0])*A,
                                  np.sin(2.0*np.pi*r[1])*B,
                                  np.cos(2.0*np.pi*r[1])*B,
                                  np.sin(2.0*np.pi*r[0])*A])).standardize()



# ******************************************************************************************
class Symmetry:
    """
    Symmetry operations for lattice systems.

    References
    ----------
    https://en.wikipedia.org/wiki/Crystal_system

    """

    lattices = [None,'orthorhombic','tetragonal','hexagonal','cubic',]

    def __init__(self, symmetry = None):
        """
        Symmetry Definition.

        Parameters
        ----------
        symmetry : str, optional
            label of the crystal system

        """
        if symmetry is not None and symmetry.lower() not in Symmetry.lattices:
            raise KeyError('Symmetry/crystal system "{}" is unknown'.format(symmetry))

        self.lattice = symmetry.lower() if isinstance(symmetry,str) else symmetry


    def __copy__(self):
        """Copy."""
        return self.__class__(self.lattice)

    copy = __copy__


    def __repr__(self):
        """Readable string."""
        return '{}'.format(self.lattice)


    def __eq__(self, other):
        """
        Equal to other.

        Parameters
        ----------
        other : Symmetry
            Symmetry to check for equality.

        """
        return self.lattice == other.lattice

    def __neq__(self, other):
        """
        Not Equal to other.

        Parameters
        ----------
        other : Symmetry
            Symmetry to check for inequality.

        """
        return not self.__eq__(other)

    def __cmp__(self,other):
        """
        Linear ordering.

        Parameters
        ----------
        other : Symmetry
            Symmetry to check for for order.

        """
        myOrder    = Symmetry.lattices.index(self.lattice)
        otherOrder = Symmetry.lattices.index(other.lattice)
        return (myOrder > otherOrder) - (myOrder < otherOrder)

    def symmetryOperations(self,members=[]):
        """List (or single element) of symmetry operations as rotations."""
        if self.lattice == 'cubic':
            symQuats =  [
                          [ 1.0,            0.0,            0.0,            0.0            ],
                          [ 0.0,            1.0,            0.0,            0.0            ],
                          [ 0.0,            0.0,            1.0,            0.0            ],
                          [ 0.0,            0.0,            0.0,            1.0            ],
                          [ 0.0,            0.0,            0.5*np.sqrt(2), 0.5*np.sqrt(2) ],
                          [ 0.0,            0.0,            0.5*np.sqrt(2),-0.5*np.sqrt(2) ],
                          [ 0.0,            0.5*np.sqrt(2), 0.0,            0.5*np.sqrt(2) ],
                          [ 0.0,            0.5*np.sqrt(2), 0.0,           -0.5*np.sqrt(2) ],
                          [ 0.0,            0.5*np.sqrt(2),-0.5*np.sqrt(2), 0.0            ],
                          [ 0.0,           -0.5*np.sqrt(2),-0.5*np.sqrt(2), 0.0            ],
                          [ 0.5,            0.5,            0.5,            0.5            ],
                          [-0.5,            0.5,            0.5,            0.5            ],
                          [-0.5,            0.5,            0.5,           -0.5            ],
                          [-0.5,            0.5,           -0.5,            0.5            ],
                          [-0.5,           -0.5,            0.5,            0.5            ],
                          [-0.5,           -0.5,            0.5,           -0.5            ],
                          [-0.5,           -0.5,           -0.5,            0.5            ],
                          [-0.5,            0.5,           -0.5,           -0.5            ],
                          [-0.5*np.sqrt(2), 0.0,            0.0,            0.5*np.sqrt(2) ],
                          [ 0.5*np.sqrt(2), 0.0,            0.0,            0.5*np.sqrt(2) ],
                          [-0.5*np.sqrt(2), 0.0,            0.5*np.sqrt(2), 0.0            ],
                          [-0.5*np.sqrt(2), 0.0,           -0.5*np.sqrt(2), 0.0            ],
                          [-0.5*np.sqrt(2), 0.5*np.sqrt(2), 0.0,            0.0            ],
                          [-0.5*np.sqrt(2),-0.5*np.sqrt(2), 0.0,            0.0            ],
                        ]
        elif self.lattice == 'hexagonal':
            symQuats =  [
                          [ 1.0,            0.0,            0.0,            0.0            ],
                          [-0.5*np.sqrt(3), 0.0,            0.0,           -0.5            ],
                          [ 0.5,            0.0,            0.0,            0.5*np.sqrt(3) ],
                          [ 0.0,            0.0,            0.0,            1.0            ],
                          [-0.5,            0.0,            0.0,            0.5*np.sqrt(3) ],
                          [-0.5*np.sqrt(3), 0.0,            0.0,            0.5            ],
                          [ 0.0,            1.0,            0.0,            0.0            ],
                          [ 0.0,           -0.5*np.sqrt(3), 0.5,            0.0            ],
                          [ 0.0,            0.5,           -0.5*np.sqrt(3), 0.0            ],
                          [ 0.0,            0.0,            1.0,            0.0            ],
                          [ 0.0,           -0.5,           -0.5*np.sqrt(3), 0.0            ],
                          [ 0.0,            0.5*np.sqrt(3), 0.5,            0.0            ],
                        ]
        elif self.lattice == 'tetragonal':
            symQuats =  [
                          [ 1.0,            0.0,            0.0,            0.0            ],
                          [ 0.0,            1.0,            0.0,            0.0            ],
                          [ 0.0,            0.0,            1.0,            0.0            ],
                          [ 0.0,            0.0,            0.0,            1.0            ],
                          [ 0.0,            0.5*np.sqrt(2), 0.5*np.sqrt(2), 0.0            ],
                          [ 0.0,           -0.5*np.sqrt(2), 0.5*np.sqrt(2), 0.0            ],
                          [ 0.5*np.sqrt(2), 0.0,            0.0,            0.5*np.sqrt(2) ],
                          [-0.5*np.sqrt(2), 0.0,            0.0,            0.5*np.sqrt(2) ],
                        ]
        elif self.lattice == 'orthorhombic':
            symQuats =  [
                          [ 1.0,0.0,0.0,0.0 ],
                          [ 0.0,1.0,0.0,0.0 ],
                          [ 0.0,0.0,1.0,0.0 ],
                          [ 0.0,0.0,0.0,1.0 ],
                        ]
        else:
            symQuats =  [
                          [ 1.0,0.0,0.0,0.0 ],
                        ]

        symOps = list(map(Rotation,
                      np.array(symQuats)[np.atleast_1d(members) if members != [] else range(len(symQuats))]))
        try:
            iter(members)                                                                           # asking for (even empty) list of members?
        except TypeError:
            return symOps[0]                                                                        # no, return rotation object
        else:
            return symOps                                                                           # yes, return list of rotations


    def inFZ(self,rodrigues):
        """
        Check whether given Rodriques-Frank vector falls into fundamental zone of own symmetry.

        Fundamental zone in Rodrigues space is point symmetric around origin.
        """
        if (len(rodrigues) != 3):
            raise ValueError('Input is not a Rodriques-Frank vector.\n')

        if np.any(rodrigues == np.inf): return False

        Rabs = abs(rodrigues)

        if self.lattice == 'cubic':
            return     np.sqrt(2.0)-1.0 >= Rabs[0] \
                   and np.sqrt(2.0)-1.0 >= Rabs[1] \
                   and np.sqrt(2.0)-1.0 >= Rabs[2] \
                   and 1.0 >= Rabs[0] + Rabs[1] + Rabs[2]
        elif self.lattice == 'hexagonal':
            return     1.0 >= Rabs[0] and 1.0 >= Rabs[1] and 1.0 >= Rabs[2] \
                   and 2.0 >= np.sqrt(3)*Rabs[0] + Rabs[1] \
                   and 2.0 >= np.sqrt(3)*Rabs[1] + Rabs[0] \
                   and 2.0 >= np.sqrt(3) + Rabs[2]
        elif self.lattice == 'tetragonal':
            return     1.0 >= Rabs[0] and 1.0 >= Rabs[1] \
                   and np.sqrt(2.0) >= Rabs[0] + Rabs[1] \
                   and np.sqrt(2.0) >= Rabs[2] + 1.0
        elif self.lattice == 'orthorhombic':
            return     1.0 >= Rabs[0] and 1.0 >= Rabs[1] and 1.0 >= Rabs[2]
        else:
            return True


    def inDisorientationSST(self,rodrigues):
        """
        Check whether given Rodriques-Frank vector (of misorientation) falls into standard stereographic triangle of own symmetry.

        References
        ----------
        A. Heinz and P. Neumann, Acta Crystallographica Section A 47:780-789, 1991
        https://doi.org/10.1107/S0108767391006864

        """
        if (len(rodrigues) != 3):
          raise ValueError('Input is not a Rodriques-Frank vector.\n')
        R = rodrigues

        epsilon = 0.0
        if self.lattice == 'cubic':
            return R[0] >= R[1]+epsilon              and R[1] >= R[2]+epsilon and R[2] >= epsilon
        elif self.lattice == 'hexagonal':
            return R[0] >= np.sqrt(3)*(R[1]-epsilon) and R[1] >= epsilon      and R[2] >= epsilon
        elif self.lattice == 'tetragonal':
            return R[0] >= R[1]-epsilon              and R[1] >= epsilon      and R[2] >= epsilon
        elif self.lattice == 'orthorhombic':
            return R[0] >= epsilon                   and R[1] >= epsilon      and R[2] >= epsilon
        else:
            return True


    def inSST(self,
              vector,
              proper = False,
              color = False):
        """
        Check whether given vector falls into standard stereographic triangle of own symmetry.

        proper considers only vectors with z >= 0, hence uses two neighboring SSTs.
        Return inverse pole figure color if requested.
        Bases are computed from

        basis = {'cubic' :        np.linalg.inv(np.array([[0.,0.,1.],                               # direction of red
                                                          [1.,0.,1.]/np.sqrt(2.),                   # direction of green
                                                          [1.,1.,1.]/np.sqrt(3.)]).T),              # direction of blue
                 'hexagonal' :    np.linalg.inv(np.array([[0.,0.,1.],                               # direction of red
                                                          [1.,0.,0.],                               # direction of green
                                                          [np.sqrt(3.),1.,0.]/np.sqrt(4.)]).T),     # direction of blue
                 'tetragonal' :   np.linalg.inv(np.array([[0.,0.,1.],                               # direction of red
                                                          [1.,0.,0.],                               # direction of green
                                                          [1.,1.,0.]/np.sqrt(2.)]).T),              # direction of blue
                 'orthorhombic' : np.linalg.inv(np.array([[0.,0.,1.],                               # direction of red
                                                          [1.,0.,0.],                               # direction of green
                                                          [0.,1.,0.]]).T),                          # direction of blue
                }
        """
        if self.lattice == 'cubic':
            basis = {'improper':np.array([ [-1.            ,  0.            ,  1. ],
                                           [ np.sqrt(2.)   , -np.sqrt(2.)   ,  0. ],
                                           [ 0.            ,  np.sqrt(3.)   ,  0. ] ]),
                       'proper':np.array([ [ 0.            , -1.            ,  1. ],
                                           [-np.sqrt(2.)   , np.sqrt(2.)    ,  0. ],
                                           [ np.sqrt(3.)   ,  0.            ,  0. ] ]),
                    }
        elif self.lattice == 'hexagonal':
            basis = {'improper':np.array([ [ 0.            ,  0.            ,  1. ],
                                           [ 1.            , -np.sqrt(3.)   ,  0. ],
                                           [ 0.            ,  2.            ,  0. ] ]),
                     'proper':np.array([   [ 0.            ,  0.            ,  1. ],
                                           [-1.            ,  np.sqrt(3.)   ,  0. ],
                                           [ np.sqrt(3.)   , -1.            ,  0. ] ]),
                    }
        elif self.lattice == 'tetragonal':
            basis = {'improper':np.array([ [ 0.            ,  0.            ,  1. ],
                                           [ 1.            , -1.            ,  0. ],
                                           [ 0.            ,  np.sqrt(2.)   ,  0. ] ]),
                     'proper':np.array([   [ 0.            ,  0.            ,  1. ],
                                           [-1.            ,  1.            ,  0. ],
                                           [ np.sqrt(2.)   ,  0.            ,  0. ] ]),
                    }
        elif self.lattice == 'orthorhombic':
            basis = {'improper':np.array([ [ 0., 0., 1.],
                                           [ 1., 0., 0.],
                                           [ 0., 1., 0.] ]),
                       'proper':np.array([ [ 0., 0., 1.],
                                           [-1., 0., 0.],
                                           [ 0., 1., 0.] ]),
                    }
        else:                                                                                       # direct exit for unspecified symmetry
            if color:
                return (True,np.zeros(3,'d'))
            else:
                return True

        v = np.array(vector,dtype=float)
        if proper:                                                                                  # check both improper ...
            theComponents = np.around(np.dot(basis['improper'],v),12)
            inSST = np.all(theComponents >= 0.0)
            if not inSST:                                                                           # ... and proper SST
              theComponents = np.around(np.dot(basis['proper'],v),12)
              inSST = np.all(theComponents >= 0.0)
        else:
            v[2] = abs(v[2])                                                                        # z component projects identical
            theComponents = np.around(np.dot(basis['improper'],v),12)                               # for positive and negative values
            inSST = np.all(theComponents >= 0.0)

        if color:                                                                                   # have to return color array
            if inSST:
                rgb = np.power(theComponents/np.linalg.norm(theComponents),0.5)                     # smoothen color ramps
                rgb = np.minimum(np.ones(3,dtype=float),rgb)                                        # limit to maximum intensity
                rgb /= max(rgb)                                                                     # normalize to (HS)V = 1
            else:
                rgb = np.zeros(3,dtype=float)
            return (inSST,rgb)
        else:
            return inSST

# code derived from https://github.com/ezag/pyeuclid
# suggested reading: http://web.mit.edu/2.998/www/QuaternionReport1.pdf


# ******************************************************************************************
class Lattice:
  """
  Lattice system.

  Currently, this contains only a mapping from Bravais lattice to symmetry
  and orientation relationships. It could include twin and slip systems.

  References
  ----------
  https://en.wikipedia.org/wiki/Bravais_lattice

  """

  lattices = {
              'triclinic':{'symmetry':None},
              'bct':{'symmetry':'tetragonal'},
              'hex':{'symmetry':'hexagonal'},
              'fcc':{'symmetry':'cubic','c/a':1.0},
              'bcc':{'symmetry':'cubic','c/a':1.0},
             }


  def __init__(self, lattice):
    """
    New lattice of given type.

    Parameters
    ----------
    lattice : str
        Bravais lattice.

    """
    self.lattice  = lattice
    self.symmetry = Symmetry(self.lattices[lattice]['symmetry'])


  def __repr__(self):
    """Report basic lattice information."""
    return 'Bravais lattice {} ({} symmetry)'.format(self.lattice,self.symmetry)


  # Kurdjomov--Sachs orientation relationship for fcc <-> bcc transformation
  # from S. Morito et al., Journal of Alloys and Compounds 577:s587-s592, 2013
  # also see K. Kitahara et al., Acta Materialia 54:1279-1288, 2006
  KS = {'mapping':{'fcc':0,'bcc':1},
      'planes': np.array([
      [[  1,  1,  1],[  0,  1,  1]],
      [[  1,  1,  1],[  0,  1,  1]],
      [[  1,  1,  1],[  0,  1,  1]],
      [[  1,  1,  1],[  0,  1,  1]],
      [[  1,  1,  1],[  0,  1,  1]],
      [[  1,  1,  1],[  0,  1,  1]],
      [[  1, -1,  1],[  0,  1,  1]],
      [[  1, -1,  1],[  0,  1,  1]],
      [[  1, -1,  1],[  0,  1,  1]],
      [[  1, -1,  1],[  0,  1,  1]],
      [[  1, -1,  1],[  0,  1,  1]],
      [[  1, -1,  1],[  0,  1,  1]],
      [[ -1,  1,  1],[  0,  1,  1]],
      [[ -1,  1,  1],[  0,  1,  1]],
      [[ -1,  1,  1],[  0,  1,  1]],
      [[ -1,  1,  1],[  0,  1,  1]],
      [[ -1,  1,  1],[  0,  1,  1]],
      [[ -1,  1,  1],[  0,  1,  1]],
      [[  1,  1, -1],[  0,  1,  1]],
      [[  1,  1, -1],[  0,  1,  1]],
      [[  1,  1, -1],[  0,  1,  1]],
      [[  1,  1, -1],[  0,  1,  1]],
      [[  1,  1, -1],[  0,  1,  1]],
      [[  1,  1, -1],[  0,  1,  1]]],dtype='float'),
      'directions': np.array([
      [[ -1,  0,  1],[ -1, -1,  1]],
      [[ -1,  0,  1],[ -1,  1, -1]],
      [[  0,  1, -1],[ -1, -1,  1]],
      [[  0,  1, -1],[ -1,  1, -1]],
      [[  1, -1,  0],[ -1, -1,  1]],
      [[  1, -1,  0],[ -1,  1, -1]],
      [[  1,  0, -1],[ -1, -1,  1]],
      [[  1,  0, -1],[ -1,  1, -1]],
      [[ -1, -1,  0],[ -1, -1,  1]],
      [[ -1, -1,  0],[ -1,  1, -1]],
      [[  0,  1,  1],[ -1, -1,  1]],
      [[  0,  1,  1],[ -1,  1, -1]],
      [[  0, -1,  1],[ -1, -1,  1]],
      [[  0, -1,  1],[ -1,  1, -1]],
      [[ -1,  0, -1],[ -1, -1,  1]],
      [[ -1,  0, -1],[ -1,  1, -1]],
      [[  1,  1,  0],[ -1, -1,  1]],
      [[  1,  1,  0],[ -1,  1, -1]],
      [[ -1,  1,  0],[ -1, -1,  1]],
      [[ -1,  1,  0],[ -1,  1, -1]],
      [[  0, -1, -1],[ -1, -1,  1]],
      [[  0, -1, -1],[ -1,  1, -1]],
      [[  1,  0,  1],[ -1, -1,  1]],
      [[  1,  0,  1],[ -1,  1, -1]]],dtype='float')}

  # Greninger--Troiano orientation relationship for fcc <-> bcc transformation
  # from Y. He et al., Journal of Applied Crystallography 39:72-81, 2006
  GT = {'mapping':{'fcc':0,'bcc':1},
      'planes': np.array([
      [[  1,  1,  1],[  1,  0,  1]],
      [[  1,  1,  1],[  1,  1,  0]],
      [[  1,  1,  1],[  0,  1,  1]],
      [[ -1, -1,  1],[ -1,  0,  1]],
      [[ -1, -1,  1],[ -1, -1,  0]],
      [[ -1, -1,  1],[  0, -1,  1]],
      [[ -1,  1,  1],[ -1,  0,  1]],
      [[ -1,  1,  1],[ -1,  1,  0]],
      [[ -1,  1,  1],[  0,  1,  1]],
      [[  1, -1,  1],[  1,  0,  1]],
      [[  1, -1,  1],[  1, -1,  0]],
      [[  1, -1,  1],[  0, -1,  1]],
      [[  1,  1,  1],[  1,  1,  0]],
      [[  1,  1,  1],[  0,  1,  1]],
      [[  1,  1,  1],[  1,  0,  1]],
      [[ -1, -1,  1],[ -1, -1,  0]],
      [[ -1, -1,  1],[  0, -1,  1]],
      [[ -1, -1,  1],[ -1,  0,  1]],
      [[ -1,  1,  1],[ -1,  1,  0]],
      [[ -1,  1,  1],[  0,  1,  1]],
      [[ -1,  1,  1],[ -1,  0,  1]],
      [[  1, -1,  1],[  1, -1,  0]],
      [[  1, -1,  1],[  0, -1,  1]],
      [[  1, -1,  1],[  1,  0,  1]]],dtype='float'),
      'directions': np.array([
      [[ -5,-12, 17],[-17, -7, 17]],
      [[ 17, -5,-12],[ 17,-17, -7]],
      [[-12, 17, -5],[ -7, 17,-17]],
      [[  5, 12, 17],[ 17,  7, 17]],
      [[-17,  5,-12],[-17, 17, -7]],
      [[ 12,-17, -5],[  7,-17,-17]],
      [[ -5, 12,-17],[-17,  7,-17]],
      [[ 17,  5, 12],[ 17, 17,  7]],
      [[-12,-17,  5],[ -7,-17, 17]],
      [[  5,-12,-17],[ 17, -7,-17]],
      [[-17, -5, 12],[-17,-17,  7]],
      [[ 12, 17,  5],[  7, 17, 17]],
      [[ -5, 17,-12],[-17, 17, -7]],
      [[-12, -5, 17],[ -7,-17, 17]],
      [[ 17,-12, -5],[ 17, -7,-17]],
      [[  5,-17,-12],[ 17,-17, -7]],
      [[ 12,  5, 17],[  7, 17, 17]],
      [[-17, 12, -5],[-17,  7,-17]],
      [[ -5,-17, 12],[-17,-17,  7]],
      [[-12,  5,-17],[ -7, 17,-17]],
      [[ 17, 12,  5],[ 17,  7, 17]],
      [[  5, 17, 12],[ 17, 17,  7]],
      [[ 12, -5,-17],[  7,-17,-17]],
      [[-17,-12,  5],[-17,-7, 17]]],dtype='float')}

  # Greninger--Troiano' orientation relationship for fcc <-> bcc transformation
  # from Y. He et al., Journal of Applied Crystallography 39:72-81, 2006
  GTprime = {'mapping':{'fcc':0,'bcc':1},
      'planes': np.array([
      [[  7, 17, 17],[ 12,  5, 17]],
      [[ 17,  7, 17],[ 17, 12,  5]],
      [[ 17, 17,  7],[  5, 17, 12]],
      [[ -7,-17, 17],[-12, -5, 17]],
      [[-17, -7, 17],[-17,-12,  5]],
      [[-17,-17,  7],[ -5,-17, 12]],
      [[  7,-17,-17],[ 12, -5,-17]],
      [[ 17, -7,-17],[ 17,-12, -5]],
      [[ 17,-17, -7],[  5,-17,-12]],
      [[ -7, 17,-17],[-12,  5,-17]],
      [[-17,  7,-17],[-17, 12, -5]],
      [[-17, 17, -7],[ -5, 17,-12]],
      [[  7, 17, 17],[ 12, 17,  5]],
      [[ 17,  7, 17],[  5, 12, 17]],
      [[ 17, 17,  7],[ 17,  5, 12]],
      [[ -7,-17, 17],[-12,-17,  5]],
      [[-17, -7, 17],[ -5,-12, 17]],
      [[-17,-17,  7],[-17, -5, 12]],
      [[  7,-17,-17],[ 12,-17, -5]],
      [[ 17, -7,-17],[ 5, -12,-17]],
      [[ 17,-17, -7],[ 17, -5,-12]],
      [[ -7, 17,-17],[-12, 17, -5]],
      [[-17,  7,-17],[ -5, 12,-17]],
      [[-17, 17, -7],[-17,  5,-12]]],dtype='float'),
      'directions': np.array([
      [[  0,  1, -1],[  1,  1, -1]],
      [[ -1,  0,  1],[ -1,  1,  1]],
      [[  1, -1,  0],[  1, -1,  1]],
      [[  0, -1, -1],[ -1, -1, -1]],
      [[  1,  0,  1],[  1, -1,  1]],
      [[  1, -1,  0],[  1, -1, -1]],
      [[  0,  1, -1],[ -1,  1, -1]],
      [[  1,  0,  1],[  1,  1,  1]],
      [[ -1, -1,  0],[ -1, -1,  1]],
      [[  0, -1, -1],[  1, -1, -1]],
      [[ -1,  0,  1],[ -1, -1,  1]],
      [[ -1, -1,  0],[ -1, -1, -1]],
      [[  0, -1,  1],[  1, -1,  1]],
      [[  1,  0, -1],[  1,  1, -1]],
      [[ -1,  1,  0],[ -1,  1,  1]],
      [[  0,  1,  1],[ -1,  1,  1]],
      [[ -1,  0, -1],[ -1, -1, -1]],
      [[ -1,  1,  0],[ -1,  1, -1]],
      [[  0, -1,  1],[ -1, -1,  1]],
      [[ -1,  0, -1],[ -1,  1, -1]],
      [[  1,  1,  0],[  1,  1,  1]],
      [[  0,  1,  1],[  1,  1,  1]],
      [[  1,  0, -1],[  1, -1, -1]],
      [[  1,  1,  0],[  1,  1, -1]]],dtype='float')}

  # Nishiyama--Wassermann orientation relationship for fcc <-> bcc transformation
  # from H. Kitahara et al., Materials Characterization 54:378-386, 2005
  NW = {'mapping':{'fcc':0,'bcc':1},
      'planes': np.array([
      [[  1,  1,  1],[  0,  1,  1]],
      [[  1,  1,  1],[  0,  1,  1]],
      [[  1,  1,  1],[  0,  1,  1]],
      [[ -1,  1,  1],[  0,  1,  1]],
      [[ -1,  1,  1],[  0,  1,  1]],
      [[ -1,  1,  1],[  0,  1,  1]],
      [[  1, -1,  1],[  0,  1,  1]],
      [[  1, -1,  1],[  0,  1,  1]],
      [[  1, -1,  1],[  0,  1,  1]],
      [[ -1, -1,  1],[  0,  1,  1]],
      [[ -1, -1,  1],[  0,  1,  1]],
      [[ -1, -1,  1],[  0,  1,  1]]],dtype='float'),
      'directions': np.array([
      [[  2, -1, -1],[  0, -1,  1]],
      [[ -1,  2, -1],[  0, -1,  1]],
      [[ -1, -1,  2],[  0, -1,  1]],
      [[ -2, -1, -1],[  0, -1,  1]],
      [[  1,  2, -1],[  0, -1,  1]],
      [[  1, -1,  2],[  0, -1,  1]],
      [[  2,  1, -1],[  0, -1,  1]],
      [[ -1, -2, -1],[  0, -1,  1]],
      [[ -1,  1,  2],[  0, -1,  1]],
      [[  2, -1,  1],[  0, -1,  1]], #It is wrong in the paper, but matrix is correct
      [[ -1,  2,  1],[  0, -1,  1]],
      [[ -1, -1, -2],[  0, -1,  1]]],dtype='float')}

  # Pitsch orientation relationship for fcc <-> bcc transformation
  # from Y. He et al., Acta Materialia 53:1179-1190, 2005
  Pitsch = {'mapping':{'fcc':0,'bcc':1},
      'planes': np.array([
      [[  0,  1,  0],[ -1,  0,  1]],
      [[  0,  0,  1],[  1, -1,  0]],
      [[  1,  0,  0],[  0,  1, -1]],
      [[  1,  0,  0],[  0, -1, -1]],
      [[  0,  1,  0],[ -1,  0, -1]],
      [[  0,  0,  1],[ -1, -1,  0]],
      [[  0,  1,  0],[ -1,  0, -1]],
      [[  0,  0,  1],[ -1, -1,  0]],
      [[  1,  0,  0],[  0, -1, -1]],
      [[  1,  0,  0],[  0, -1,  1]],
      [[  0,  1,  0],[  1,  0, -1]],
      [[  0,  0,  1],[ -1,  1,  0]]],dtype='float'),
      'directions': np.array([
      [[  1,  0,  1],[  1, -1,  1]],
      [[  1,  1,  0],[  1,  1, -1]],
      [[  0,  1,  1],[ -1,  1,  1]],
      [[  0,  1, -1],[ -1,  1, -1]],
      [[ -1,  0,  1],[ -1, -1,  1]],
      [[  1, -1,  0],[  1, -1, -1]],
      [[  1,  0, -1],[  1, -1, -1]],
      [[ -1,  1,  0],[ -1,  1, -1]],
      [[  0, -1,  1],[ -1, -1,  1]],
      [[  0,  1,  1],[ -1,  1,  1]],
      [[  1,  0,  1],[  1, -1,  1]],
      [[  1,  1,  0],[  1,  1, -1]]],dtype='float')}

  # Bain orientation relationship for fcc <-> bcc transformation
  # from Y. He et al., Journal of Applied Crystallography 39:72-81, 2006
  Bain = {'mapping':{'fcc':0,'bcc':1},
      'planes': np.array([
      [[  1,  0,  0],[  1,  0,  0]],
      [[  0,  1,  0],[  0,  1,  0]],
      [[  0,  0,  1],[  0,  0,  1]]],dtype='float'),
      'directions': np.array([
      [[  0,  1,  0],[  0,  1,  1]],
      [[  0,  0,  1],[  1,  0,  1]],
      [[  1,  0,  0],[  1,  1,  0]]],dtype='float')}

  def relationOperations(self,model):
    """
    Crystallographic orientation relationships for phase transformations.

    References
    ----------
    S. Morito et al., Journal of Alloys and Compounds 577:s587-s592, 2013
    https://doi.org/10.1016/j.jallcom.2012.02.004

    K. Kitahara et al., Acta Materialia 54(5):1279-1288, 2006
    https://doi.org/10.1016/j.actamat.2005.11.001

    Y. He et al., Journal of Applied Crystallography 39:72-81, 2006
    https://doi.org/10.1107/S0021889805038276

    H. Kitahara et al., Materials Characterization 54(4-5):378-386, 2005
    https://doi.org/10.1016/j.matchar.2004.12.015

    Y. He et al., Acta Materialia 53(4):1179-1190, 2005
    https://doi.org/10.1016/j.actamat.2004.11.021

    """
    models={'KS':self.KS, 'GT':self.GT, 'GT_prime':self.GTprime,
            'NW':self.NW, 'Pitsch': self.Pitsch, 'Bain':self.Bain}
    try:
      relationship = models[model]
    except KeyError :
      raise KeyError('Orientation relationship "{}" is unknown'.format(model))

    if self.lattice not in relationship['mapping']:
      raise ValueError('Relationship "{}" not supported for lattice "{}"'.format(model,self.lattice))

    r = {'lattice':Lattice((set(relationship['mapping'])-{self.lattice}).pop()),                    # target lattice
         'rotations':[] }

    myPlane_id    = relationship['mapping'][self.lattice]
    otherPlane_id = (myPlane_id+1)%2
    myDir_id      = myPlane_id +2
    otherDir_id   = otherPlane_id +2

    for miller in np.hstack((relationship['planes'],relationship['directions'])):
      myPlane     = miller[myPlane_id]/    np.linalg.norm(miller[myPlane_id])
      myDir       = miller[myDir_id]/      np.linalg.norm(miller[myDir_id])
      myMatrix    = np.array([myDir,np.cross(myPlane,myDir),myPlane])

      otherPlane  = miller[otherPlane_id]/ np.linalg.norm(miller[otherPlane_id])
      otherDir    = miller[otherDir_id]/   np.linalg.norm(miller[otherDir_id])
      otherMatrix = np.array([otherDir,np.cross(otherPlane,otherDir),otherPlane])

      r['rotations'].append(Rotation.fromMatrix(np.dot(otherMatrix.T,myMatrix)))

    return r

####################################################################################################
# Code below available according to the following conditions on https://github.com/MarDiehl/3Drotations
####################################################################################################
# Copyright (c) 2017-2019, Martin Diehl/Max-Planck-Institut für Eisenforschung GmbH
# Copyright (c) 2013-2014, Marc De Graef/Carnegie Mellon University
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, are
# permitted provided that the following conditions are met:
#
#     - Redistributions of source code must retain the above copyright notice, this list
#        of conditions and the following disclaimer.
#     - Redistributions in binary form must reproduce the above copyright notice, this
#        list of conditions and the following disclaimer in the documentation and/or
#        other materials provided with the distribution.
#     - Neither the names of Marc De Graef, Carnegie Mellon University nor the names
#        of its contributors may be used to endorse or promote products derived from
#        this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE
# USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
####################################################################################################

def isone(a):
  return np.isclose(a,1.0,atol=1.0e-7,rtol=0.0)

def iszero(a):
  return np.isclose(a,0.0,atol=1.0e-12,rtol=0.0)

#---------- Quaternion ----------

def qu2om(qu):
  """Quaternion to rotation matrix."""
  qq = qu[0]**2-(qu[1]**2 + qu[2]**2 + qu[3]**2)
  om = np.diag(qq + 2.0*np.array([qu[1],qu[2],qu[3]])**2)

  om[1,0] = 2.0*(qu[2]*qu[1]+qu[0]*qu[3])
  om[0,1] = 2.0*(qu[1]*qu[2]-qu[0]*qu[3])
  om[2,1] = 2.0*(qu[3]*qu[2]+qu[0]*qu[1])
  om[1,2] = 2.0*(qu[2]*qu[3]-qu[0]*qu[1])
  om[0,2] = 2.0*(qu[1]*qu[3]+qu[0]*qu[2])
  om[2,0] = 2.0*(qu[3]*qu[1]-qu[0]*qu[2])
  return om if P > 0.0 else om.T


def qu2eu(qu):
  """Quaternion to Bunge-Euler angles."""
  q03 = qu[0]**2+qu[3]**2
  q12 = qu[1]**2+qu[2]**2
  chi = np.sqrt(q03*q12)

  if iszero(chi):
    eu = np.array([np.arctan2(-P*2.0*qu[0]*qu[3],qu[0]**2-qu[3]**2), 0.0,   0.0]) if iszero(q12) else \
         np.array([np.arctan2(2.0*qu[1]*qu[2],qu[1]**2-qu[2]**2),         np.pi, 0.0])
  else:
    eu = np.array([np.arctan2((-P*qu[0]*qu[2]+qu[1]*qu[3])*chi, (-P*qu[0]*qu[1]-qu[2]*qu[3])*chi ),
                   np.arctan2( 2.0*chi, q03-q12 ),
                   np.arctan2(( P*qu[0]*qu[2]+qu[1]*qu[3])*chi, (-P*qu[0]*qu[1]+qu[2]*qu[3])*chi )])

  # reduce Euler angles to definition range, i.e a lower limit of 0.0
  eu = np.where(eu<0, (eu+2.0*np.pi)%np.array([2.0*np.pi,np.pi,2.0*np.pi]),eu)
  return eu


def qu2ax(qu):
  """
  Quaternion to axis angle pair.

  Modified version of the original formulation, should be numerically more stable
  """
  if iszero(qu[1]**2+qu[2]**2+qu[3]**2):                                                            # set axis to [001] if the angle is 0/360
    ax = [ 0.0, 0.0, 1.0, 0.0 ]
  elif not iszero(qu[0]):
    s = np.sign(qu[0])/np.sqrt(qu[1]**2+qu[2]**2+qu[3]**2)
    omega = 2.0 * np.arccos(np.clip(qu[0],-1.0,1.0))
    ax = [ qu[1]*s, qu[2]*s, qu[3]*s, omega ]
  else:
    ax = [ qu[1], qu[2], qu[3], np.pi]

  return np.array(ax)


def qu2ro(qu):
  """Quaternion to Rodriques-Frank vector."""
  if iszero(qu[0]):
    ro = [qu[1], qu[2], qu[3], np.inf]
  else:
    s = np.linalg.norm([qu[1],qu[2],qu[3]])
    ro = [0.0,0.0,P,0.0] if iszero(s) else \
         [ qu[1]/s,  qu[2]/s,  qu[3]/s, np.tan(np.arccos(np.clip(qu[0],-1.0,1.0)))]                # avoid numerical difficulties

  return np.array(ro)


def qu2ho(qu):
  """Quaternion to homochoric vector."""
  omega = 2.0 * np.arccos(np.clip(qu[0],-1.0,1.0))                                                  # avoid numerical difficulties

  if iszero(omega):
    ho = np.array([ 0.0, 0.0, 0.0 ])
  else:
    ho = np.array([qu[1], qu[2], qu[3]])
    f  = 0.75 * ( omega - np.sin(omega) )
    ho = ho/np.linalg.norm(ho) * f**(1./3.)

  return ho


def qu2cu(qu):
  """Quaternion to cubochoric vector."""
  return ho2cu(qu2ho(qu))


#---------- Rotation matrix ----------

def om2qu(om):
  """
  Rotation matrix to quaternion.

  The original formulation (direct conversion) had (numerical?) issues
  """
  return eu2qu(om2eu(om))


def om2eu(om):
  """Rotation matrix to Bunge-Euler angles."""
  if abs(om[2,2]) < 1.0:
    zeta = 1.0/np.sqrt(1.0-om[2,2]**2)
    eu = np.array([np.arctan2(om[2,0]*zeta,-om[2,1]*zeta),
                   np.arccos(om[2,2]),
                   np.arctan2(om[0,2]*zeta, om[1,2]*zeta)])
  else:
    eu = np.array([np.arctan2( om[0,1],om[0,0]), np.pi*0.5*(1-om[2,2]),0.0])                        # following the paper, not the reference implementation

  # reduce Euler angles to definition range, i.e a lower limit of 0.0
  eu = np.where(eu<0, (eu+2.0*np.pi)%np.array([2.0*np.pi,np.pi,2.0*np.pi]),eu)
  return eu


def om2ax(om):
  """Rotation matrix to axis angle pair."""
  ax=np.empty(4)

  # first get the rotation angle
  t = 0.5*(om.trace() -1.0)
  ax[3] = np.arccos(np.clip(t,-1.0,1.0))

  if iszero(ax[3]):
    ax = [ 0.0, 0.0, 1.0, 0.0]
  else:
    w,vr = np.linalg.eig(om)
  # next, find the eigenvalue (1,0j)
    i = np.where(np.isclose(w,1.0+0.0j))[0][0]
    ax[0:3] = np.real(vr[0:3,i])
    diagDelta = np.array([om[1,2]-om[2,1],om[2,0]-om[0,2],om[0,1]-om[1,0]])
    ax[0:3] = np.where(iszero(diagDelta), ax[0:3],np.abs(ax[0:3])*np.sign(-P*diagDelta))

  return np.array(ax)


def om2ro(om):
  """Rotation matrix to Rodriques-Frank vector."""
  return eu2ro(om2eu(om))


def om2ho(om):
  """Rotation matrix to homochoric vector."""
  return ax2ho(om2ax(om))


def om2cu(om):
  """Rotation matrix to cubochoric vector."""
  return ho2cu(om2ho(om))


#---------- Bunge-Euler angles ----------

def eu2qu(eu):
  """Bunge-Euler angles to quaternion."""
  ee = 0.5*eu
  cPhi = np.cos(ee[1])
  sPhi = np.sin(ee[1])
  qu = np.array([     cPhi*np.cos(ee[0]+ee[2]),
                   -P*sPhi*np.cos(ee[0]-ee[2]),
                   -P*sPhi*np.sin(ee[0]-ee[2]),
                   -P*cPhi*np.sin(ee[0]+ee[2]) ])
  if qu[0] < 0.0: qu*=-1
  return qu


def eu2om(eu):
  """Bunge-Euler angles to rotation matrix."""
  c = np.cos(eu)
  s = np.sin(eu)

  om = np.array([[+c[0]*c[2]-s[0]*s[2]*c[1], +s[0]*c[2]+c[0]*s[2]*c[1], +s[2]*s[1]],
                 [-c[0]*s[2]-s[0]*c[2]*c[1], -s[0]*s[2]+c[0]*c[2]*c[1], +c[2]*s[1]],
                 [+s[0]*s[1],                -c[0]*s[1],                +c[1]     ]])

  om[np.where(iszero(om))] = 0.0
  return om


def eu2ax(eu):
  """Bunge-Euler angles to axis angle pair."""
  t = np.tan(eu[1]*0.5)
  sigma = 0.5*(eu[0]+eu[2])
  delta = 0.5*(eu[0]-eu[2])
  tau   = np.linalg.norm([t,np.sin(sigma)])
  alpha = np.pi if iszero(np.cos(sigma)) else \
          2.0*np.arctan(tau/np.cos(sigma))

  if iszero(alpha):
    ax = np.array([ 0.0, 0.0, 1.0, 0.0 ])
  else:
    ax = -P/tau * np.array([ t*np.cos(delta), t*np.sin(delta), np.sin(sigma) ])                     # passive axis angle pair so a minus sign in front
    ax = np.append(ax,alpha)
    if alpha < 0.0: ax *= -1.0                                                                      # ensure alpha is positive

  return ax


def eu2ro(eu):
  """Bunge-Euler angles to Rodriques-Frank vector."""
  ro = eu2ax(eu)                                                                                    # convert to axis angle pair representation
  if ro[3] >= np.pi:                                                                                # Differs from original implementation. check convention 5
    ro[3] = np.inf
  elif iszero(ro[3]):
    ro = np.array([ 0.0, 0.0, P, 0.0 ])
  else:
    ro[3] = np.tan(ro[3]*0.5)

  return ro


def eu2ho(eu):
  """Bunge-Euler angles to homochoric vector."""
  return ax2ho(eu2ax(eu))


def eu2cu(eu):
  """Bunge-Euler angles to cubochoric vector."""
  return ho2cu(eu2ho(eu))


#---------- Axis angle pair ----------

def ax2qu(ax):
  """Axis angle pair to quaternion."""
  if iszero(ax[3]):
    qu = np.array([ 1.0, 0.0, 0.0, 0.0 ])
  else:
    c = np.cos(ax[3]*0.5)
    s = np.sin(ax[3]*0.5)
    qu = np.array([ c, ax[0]*s, ax[1]*s, ax[2]*s ])

  return qu


def ax2om(ax):
  """Axis angle pair to rotation matrix."""
  c = np.cos(ax[3])
  s = np.sin(ax[3])
  omc = 1.0-c
  om=np.diag(ax[0:3]**2*omc + c)

  for idx in [[0,1,2],[1,2,0],[2,0,1]]:
    q = omc*ax[idx[0]] * ax[idx[1]]
    om[idx[0],idx[1]] = q + s*ax[idx[2]]
    om[idx[1],idx[0]] = q - s*ax[idx[2]]

  return om if P < 0.0 else om.T


def ax2eu(ax):
  """Rotation matrix to Bunge Euler angles."""
  return om2eu(ax2om(ax))


def ax2ro(ax):
  """Axis angle pair to Rodriques-Frank vector."""
  if iszero(ax[3]):
    ro = [ 0.0, 0.0, P, 0.0 ]
  else:
    ro = [ax[0], ax[1], ax[2]]
    # 180 degree case
    ro += [np.inf] if np.isclose(ax[3],np.pi,atol=1.0e-15,rtol=0.0) else \
          [np.tan(ax[3]*0.5)]

  return np.array(ro)


def ax2ho(ax):
  """Axis angle pair to homochoric vector."""
  f = (0.75 * ( ax[3] - np.sin(ax[3]) ))**(1.0/3.0)
  ho = ax[0:3] * f
  return ho


def ax2cu(ax):
  """Axis angle pair to cubochoric vector."""
  return ho2cu(ax2ho(ax))


#---------- Rodrigues-Frank vector ----------

def ro2qu(ro):
  """Rodriques-Frank vector to quaternion."""
  return ax2qu(ro2ax(ro))


def ro2om(ro):
 """Rodgrigues-Frank vector to rotation matrix."""
 return ax2om(ro2ax(ro))


def ro2eu(ro):
  """Rodriques-Frank vector to Bunge-Euler angles."""
  return om2eu(ro2om(ro))


def ro2ax(ro):
  """Rodriques-Frank vector to axis angle pair."""
  ta = ro[3]

  if iszero(ta):
    ax = [ 0.0, 0.0, 1.0, 0.0 ]
  elif not np.isfinite(ta):
    ax = [ ro[0], ro[1], ro[2], np.pi ]
  else:
    angle = 2.0*np.arctan(ta)
    ta = 1.0/np.linalg.norm(ro[0:3])
    ax = [ ro[0]/ta, ro[1]/ta, ro[2]/ta, angle ]

  return np.array(ax)


def ro2ho(ro):
  """Rodriques-Frank vector to homochoric vector."""
  if iszero(np.sum(ro[0:3]**2.0)):
    ho = [ 0.0, 0.0, 0.0 ]
  else:
    f = 2.0*np.arctan(ro[3]) -np.sin(2.0*np.arctan(ro[3])) if np.isfinite(ro[3]) else np.pi
    ho = ro[0:3] * (0.75*f)**(1.0/3.0)

  return np.array(ho)


def ro2cu(ro):
  """Rodriques-Frank vector to cubochoric vector."""
  return ho2cu(ro2ho(ro))


#---------- Homochoric vector----------

def ho2qu(ho):
  """Homochoric vector to quaternion."""
  return ax2qu(ho2ax(ho))


def ho2om(ho):
  """Homochoric vector to rotation matrix."""
  return ax2om(ho2ax(ho))


def ho2eu(ho):
  """Homochoric vector to Bunge-Euler angles."""
  return ax2eu(ho2ax(ho))


def ho2ax(ho):
  """Homochoric vector to axis angle pair."""
  tfit = np.array([+1.0000000000018852,      -0.5000000002194847,
                   -0.024999992127593126,    -0.003928701544781374,
                   -0.0008152701535450438,   -0.0002009500426119712,
                   -0.00002397986776071756,  -0.00008202868926605841,
                   +0.00012448715042090092,  -0.0001749114214822577,
                   +0.0001703481934140054,   -0.00012062065004116828,
                   +0.000059719705868660826, -0.00001980756723965647,
                   +0.000003953714684212874, -0.00000036555001439719544])
  # normalize h and store the magnitude
  hmag_squared = np.sum(ho**2.)
  if iszero(hmag_squared):
    ax = np.array([ 0.0, 0.0, 1.0, 0.0 ])
  else:
    hm = hmag_squared

  # convert the magnitude to the rotation angle
    s = tfit[0] + tfit[1] * hmag_squared
    for i in range(2,16):
      hm *= hmag_squared
      s  += tfit[i] * hm
    ax = np.append(ho/np.sqrt(hmag_squared),2.0*np.arccos(np.clip(s,-1.0,1.0)))
  return ax


def ho2ro(ho):
  """Axis angle pair to Rodriques-Frank vector."""
  return ax2ro(ho2ax(ho))


def ho2cu(ho):
  """Homochoric vector to cubochoric vector."""
  return  Lambert.BallToCube(ho)


#---------- Cubochoric ----------

def cu2qu(cu):
  """Cubochoric vector to quaternion."""
  return ho2qu(cu2ho(cu))


def cu2om(cu):
  """Cubochoric vector to rotation matrix."""
  return ho2om(cu2ho(cu))


def cu2eu(cu):
  """Cubochoric vector to Bunge-Euler angles."""
  return ho2eu(cu2ho(cu))


def cu2ax(cu):
  """Cubochoric vector to axis angle pair."""
  return ho2ax(cu2ho(cu))


def cu2ro(cu):
  """Cubochoric vector to Rodriques-Frank vector."""
  return ho2ro(cu2ho(cu))


def cu2ho(cu):
  """Cubochoric vector to homochoric vector."""
  return  Lambert.CubeToBall(cu)
