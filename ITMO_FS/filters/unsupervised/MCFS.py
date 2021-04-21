import numpy as np
from sklearn.neighbors import NearestNeighbors
from sklearn.metrics.pairwise import pairwise_distances
from sklearn.linear_model import Lars
from scipy.linalg import eigh
from ...utils import BaseTransformer


class MCFS(BaseTransformer):
    """
        Performs the Unsupervised Feature Selection for Multi-Cluster Data algorithm.

        Parameters
        ----------
        n_features : int
            Number of features to select.
        k : int
            Amount of clusters to find.
        p : int
            Amount of nearest neighbors to use while building the graph.
        scheme : str, either '0-1', 'heat' or 'dot'
            Weighting scheme to use while building the graph.
        sigma : float
            Parameter for heat weighting scheme. Ignored if scheme is not 'heat'.
        full_graph : boolean
            If True, connect all vertices in the graph to each other instead of
            running the k-nearest neighbors algorithm. Use with 'heat' or 'dot'
            schemes.

        Notes
        -----
        For more details see `this paper
        <http://www.cad.zju.edu.cn/home/dengcai/Publication/Conference/2010_KDD-MCFS.pdf/>`_.

        Examples
        --------
        >>> from ITMO_FS.filters.unsupervised import MCFS
        >>> from sklearn.datasets import make_classification
        >>> import numpy as np
        >>> dataset = make_classification(n_samples=500, n_features=100, \
            n_informative=5, n_redundant=0, random_state=42, \
            shuffle=False)
        >>> X, y = np.array(dataset[0]), np.array(dataset[1])
        >>> model = MCFS(5).fit(X)
        >>> model.selected_features_
        array([0, 2, 4, 1, 3], dtype=int64)
    """

    def __init__(self, n_features, k=2, p=3, scheme='dot', sigma=1, full_graph=False):
        self.n_features = n_features
        self.k = k
        self.p = p
        self.scheme = scheme
        self.sigma = sigma
        self.full_graph = full_graph

    def __scheme_01(self, x1, x2):
        return 1

    def __scheme_heat(self, x1, x2):
        return np.exp(-np.linalg.norm(x1 - x2) ** 2 / self.sigma)

    def __scheme_dot(self, x1, x2):
        return (x1 / np.linalg.norm(x1 + 1e-10)).dot(x2 / np.linalg.norm(x2 + 1e-10))

    def _fit(self, X, y):
        """
            Fits filter

            Parameters
            ----------
            X : numpy array, shape (n_samples, n_features)
                The training input samples.
            y : numpy array
                The target values (ignored).

            Returns
            ----------
            None
        """

        if self.scheme not in ['0-1', 'heat', 'dot']:
            raise KeyError('scheme should be either 0-1, heat or dot; %r passed' % self.scheme)
        if self.scheme == '0-1':
            scheme = self.__scheme_01
        elif self.scheme == 'heat':
            scheme = self.__scheme_heat
        else:
            scheme = self.__scheme_dot

        if self.n_features > self.n_features_:
            raise ValueError("Cannot select %d features with n_features = %d" % (self.n_features, self.n_features_))

        n_samples = X.shape[0]

        if self.k > n_samples:
            raise ValueError("Cannot find %d clusters with n_samples = %d" % (self.k, n_samples))

        if self.p >= n_samples:
            raise ValueError("Cannot select %d nearest neighbors with n_samples = %d" % (self.p, n_samples))

        if self.full_graph:
            graph = np.ones((n_samples, n_samples))
        else:
            graph = NearestNeighbors(n_neighbors=self.p, algorithm='ball_tree').fit(X).kneighbors_graph().toarray()
            graph = np.minimum(1, graph + graph.T)

        W = graph * pairwise_distances(X, metric=lambda x, y: scheme(x, y))
        D = np.diag(W.sum(axis=0))
        L = D - W
        eigvals, Y = eigh(type=1, a=L, b=D, subset_by_index=[1, self.k])

        weights = np.zeros((self.n_features_, self.k))
        for i in range(self.k):
            clf = Lars(n_nonzero_coefs=self.n_features)
            clf.fit(X, Y[:, i])
            weights[:, i] = np.abs(clf.coef_)

        mcfs_score = weights.max(axis=1)
        ranking = np.argsort(mcfs_score)[::-1]
        self.selected_features_ = ranking[:self.n_features]
