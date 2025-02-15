__all__ = ['Sampler', 'Fixed', 'Uniform', 'RandInt', 'Normal', 'LogNormal',
           'RandKFrom']

import random
import copy
import torch
from .utils.py import ensure_list


class Sampler:
    """
    Base class for random samplers, with a bunch of helpers.
    This class is for developers of new Sampler classes only.
    """

    def __init__(self, **theta):
        self.theta = theta

    @classmethod
    def make(cls, other):
        if isinstance(other, Sampler):
            return other
        elif isinstance(other, dict):
            return cls(**other)
        elif isinstance(other, tuple):
            return cls(*other)
        else:
            return cls(other)

    def _ensure_same_length(self, theta, nsamples=None):
        theta = dict(theta)
        if nsamples:
            for k, v in theta.items():
                theta[k] = ensure_list(theta[k], nsamples)
        elif any(isinstance(v, (list, tuple)) for v in theta.values()):
            nsamples = 0
            for k, v in theta.items():
                theta[k] = ensure_list(v)
                nsamples = max(nsamples, len(theta[k]))
            for k, v in theta.items():
                theta[k] = ensure_list(theta[k], nsamples)
        return theta

    @classmethod
    def map(cls, fn, *values, n=None):
        if n:
            values = tuple(ensure_list(v, n) for v in values)
        if isinstance(values[0], list):
            return [fn(*args) for args in zip(*values)]
        else:
            return fn(*values)

    def __getattr__(self, item):
        theta = self.__getattribute__('theta')
        if item in theta:
            theta = self._ensure_same_length(theta)
            return theta[item]
        raise AttributeError(item)

    def __setattr__(self, item, value):
        if item == 'theta':
            return super().__setattr__(item, value)
        if item in self.theta:
            self.theta[item] = value
        else:
            return super().__setattr__(item, value)

    def __call__(self, n=None, **backend):
        """
        Parameters
        ----------
        n : int or list[int]
            Number of values to sample

            - if `None`, return a scalar
            - if an `int`, return a list
            - if a `list`, return a tensor

        Returns
        -------
        sample : number or list[number] or tensor

        """
        raise NotImplementedError


class Fixed(Sampler):
    """Fixed value"""
    def __init__(self, value):
        """

        Parameters
        ----------
        value : number or sequence[number]
        """
        super().__init__(value=value)

    def __call__(self, n=None, **backend):
        if isinstance(n, (list, tuple)):
            return torch.full(n, self.value, **backend)
        return self.map(copy.deepcopy, self.value, n=n)


class Uniform(Sampler):
    """Continuous uniform sampler"""

    def __init__(self, *args, **kwargs):
        """
        ```python
        Uniform(max)
        Uniform(min, max)
        ```

        Parameters
        ----------
        min : float or sequence[float], default=0
            Lower bound (inclusive)
        max : float or sequence[float]
            Upper bound (inclusive or exclusive, depending on rounding)
        """
        min, max = 0, None
        if len(args) == 2:
            min, max = args
        elif len(args) == 1:
            max = args[0]
        if 'min' in kwargs:
            min = kwargs['min']
        if 'max' in kwargs:
            max = kwargs['max']
        if max is None:
            raise ValueError('Expected at least one argument')
        super().__init__(min=min, max=max)

    def __call__(self, n=None, **backend):
        if isinstance(n, (list, tuple)):
            return torch.rand(n, **backend).mul_(self.max - self.min).add_(self.min)
        return self.map(random.uniform, self.min, self.max, n=n)


class RandInt(Sampler):
    """Discrete uniform sampler"""

    def __init__(self, *args, **kwargs):
        """
        ```python
        RandInt(max)
        RandInt(min, max)
        ```

        Parameters
        ----------
        min : float or sequence[float], default=0
            Lower bound (inclusive)
        max : float or sequence[float]
            Upper bound (inclusive)
        """
        min, max = 0, None
        if len(args) == 2:
            min, max = args
        elif len(args) == 1:
            max = args[0]
        if 'min' in kwargs:
            min = kwargs['min']
        if 'max' in kwargs:
            max = kwargs['max']
        if max is None:
            raise ValueError('Expected at least one argument')
        super().__init__(min=min, max=max)

    def __call__(self, n=None, **backend):
        if isinstance(n, (list, tuple)):
            n = tuple(n)
            return torch.randint(1 + self.max - self.min, n, **backend).add_(self.min)
        return self.map(random.randint, self.min, self.max, n=n)


class RandKFrom(Sampler):
    """Discrete uniform sampler"""

    def __init__(self, range, k=None, replacement=False):
        """
        Parameters
        ----------
        range : sequence
            Values from which to sample
        k : int, default=None
            Number of values to sample.
            Sample random number if None.
        replacement : bool, default=False
            Whether to sample with replacement
        """
        super().__init__()
        range = list(range)
        if not replacement and k and k > len(range):
            raise ValueError('Cannot sample more element than available. '
                             'To sample with replacement, use `replacement=True`')
        self.range = range
        self.k = k
        self.replacement = replacement

    def __call__(self, n=None, **backend):
        k = self.k or (1 + RandInt(len(self.range))())
        if isinstance(n, (list, tuple)) or n:
            raise ValueError('RandKFrom cannot sample multiple elements')
        if not self.replacement:
            range = list(self.range)
            random.shuffle(range)
            return range[:k]
        else:
            index = RandInt(len(self.range))(k)
            return [self.range[i] for i in index]


class Normal(Sampler):
    """Gaussian sampler"""

    def __init__(self, mu=0, sigma=1):
        """
        Parameters
        ----------
        mu : float or sequence[float]
            Mean
        sigma : float or sequence[float]
            Standard deviation
        """
        super().__init__(mu=mu, sigma=sigma)

    def __call__(self, n=None, **backend):
        if isinstance(n, (list, tuple)):
            return torch.randn(n, **backend).mul_(self.sigma).add_(self.mu)
        return self.map(random.normalvariate, self.mu, self.sigma, n=n)


class LogNormal(Sampler):
    """LogNormal sampler"""

    def __init__(self, mu=0, sigma=1):
        """
        Parameters
        ----------
        mu : float or sequence[float]
            Mean of the log
        sigma : float or sequence[float]
            Standard deviation of the log
        """
        super().__init__(mu=mu, sigma=sigma)

    def __call__(self, n=None, **backend):
        if isinstance(n, (list, tuple)):
            return torch.randn(n, **backend).mul_(self.sigma).add_(self.mu).exp_()
        return self.map(random.lognormvariate, self.mu, self.sigma, n=n)


def sym_range(x):
    if not isinstance(x, Sampler):
        if isinstance(x, (list, tuple)):
            x = (tuple(-x1 for x1 in x), x)
        else:
            x = (-x, x)
    return x


def upper_range(x, min=0):
    if not isinstance(x, Sampler):
        x = (min, x)
    return x


def lower_range(x, max=0):
    if not isinstance(x, Sampler):
        x = (x, max)
    return x
