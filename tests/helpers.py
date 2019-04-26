""" Test utilities. """

from functools import partial
import itertools
import random
import string
import numpy as np
import pytest


__author__ = "Vince Reuter"
__email__ = "vreuter@virginia.edu"


LETTERS_AND_DIGITS = string.ascii_letters + string.digits


def assert_entirely_equal(observed, expected):
    """ Accommodate equality assertion for varied data, including NaN. """
    try:
        assert observed == expected
    except AssertionError:
        assert np.isnan(observed) and np.isnan(expected)
    except ValueError:
        assert (observed == expected).all()


def named_param(argnames, argvalues):
    """
    Parameterize a test case and automatically name/label by value

    :param str argnames: Single parameter name; this is only named in the
        plural for concordance with the pytest parameter to which it maps.
    :param Iterable[object] argvalues: Collection of arguments to the
        indicated parameter (argnames)
    :return functools.partial: Wrapped version of the call to the pytest
        test case parameterization function, for use as decorator.
    """
    return partial(pytest.mark.parametrize(argnames, argvalues,
                   ids=lambda arg: "{}={}".format(argnames, arg)))


def powerset(items, min_items=0, include_full_pop=True):
    """
    Build the powerset of a collection of items.

    :param Iterable[object] items: "Pool" of all items, the population for
        which to build the power set.
    :param int min_items: Minimum number of individuals from the population
        to allow in any given subset.
    :param bool include_full_pop: Whether to include the full population in
        the powerset (default True to accord with genuine definition)
    :return list[object]: Sequence of subsets of the population, in
        nondecreasing size order
    """
    items = list(items)    # Account for iterable burn possibility.
    max_items = len(items) + 1 if include_full_pop else len(items)
    min_items = min_items or 0
    return list(itertools.chain.from_iterable(
            itertools.combinations(items, k)
            for k in range(min_items, max_items)))


def randstr(pool, size):
    """
    Generate random string of given size/length.

    :param Iterable[str] pool: collection of characters from which to sample
        (with replacement)
    :param int size: nunber of characters
    :return str: string built by concatenating randomly sampled characters
    :raise ValueError: if size is not a positive integer
    """
    if size < 1:
        raise ValueError("Must build string of positive integral length; got "
                         "{}".format(size))
    return "".join(random.choice(pool) for _ in range(size))


def randconf(ext=".yaml"):
    """
    Randomly generate config filename.

    :param str ext: filename extension
    :return str: randomly generated string to function as filename
    """
    return randstr(LETTERS_AND_DIGITS, 15) + ext


nonempty_powerset = partial(powerset, min_items=1)
