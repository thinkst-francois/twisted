"""
Tests for L{twisted.trial._dist.test.matchers}.
"""

from typing import Callable, List, Sequence, Tuple, Type

from hamcrest import anything, assert_that, contains, contains_string, equal_to, not_
from hamcrest.core.matcher import Matcher
from hamcrest.core.string_description import StringDescription
from hypothesis import given
from hypothesis.strategies import (
    binary,
    booleans,
    integers,
    just,
    lists,
    one_of,
    sampled_from,
    text,
    tuples,
)

from twisted.python.failure import Failure
from twisted.trial.unittest import SynchronousTestCase
from .matchers import HasSum, IsSequenceOf, S, isFailure, isTuple, similarFrame

Summer = Callable[[Sequence[S]], S]
concatInt = sum
concatStr = "".join
concatBytes = b"".join


class HasSumTests(SynchronousTestCase):
    """
    Tests for L{HasSum}.
    """

    summables = one_of(
        tuples(lists(integers()), just(concatInt)),
        tuples(lists(text()), just(concatStr)),
        tuples(lists(binary()), just(concatBytes)),
    )

    @given(summables)
    def test_matches(self, summable: Tuple[Sequence[S], Summer[S]]) -> None:
        """
        L{HasSum} matches a sequence if the elements sum to a value matched by
        the parameterized matcher.

        :param summable: A tuple of a sequence of values to try to match and a
            function which can compute the correct sum for that sequence.
        """
        seq, sumFunc = summable
        expected = sumFunc(seq)
        zero = sumFunc([])
        matcher = HasSum(equal_to(expected), zero)

        description = StringDescription()
        assert_that(matcher.matches(seq, description), equal_to(True))
        assert_that(str(description), equal_to(""))

    @given(summables)
    def test_mismatches(
        self,
        summable: Tuple[
            Sequence[S],
            Summer[S],
        ],
    ) -> None:
        """
        L{HasSum} does not match a sequence if the elements do not sum to a
        value matched by the parameterized matcher.

        :param summable: See L{test_matches}.
        """
        seq, sumFunc = summable
        zero = sumFunc([])
        # A matcher that never matches.
        sumMatcher: Matcher[S] = not_(anything())
        matcher = HasSum(sumMatcher, zero)

        actualDescription = StringDescription()
        assert_that(matcher.matches(seq, actualDescription), equal_to(False))

        sumMatcherDescription = StringDescription()
        sumMatcherDescription.append_description_of(sumMatcher)
        actualStr = str(actualDescription)
        assert_that(actualStr, contains_string("a sequence with sum"))
        assert_that(actualStr, contains_string(str(sumMatcherDescription)))


class IsSequenceOfTests(SynchronousTestCase):
    """
    Tests for L{IsSequenceOf}.
    """

    sequences = lists(booleans())

    @given(integers(min_value=0, max_value=1000))
    def test_matches(self, numItems: int) -> None:
        """
        L{IsSequenceOf} matches a sequence if all of the elements are
        matched by the parameterized matcher.

        :param numItems: The length of a sequence to try to match.
        """
        seq = [True] * numItems
        matcher = IsSequenceOf(equal_to(True))

        actualDescription = StringDescription()
        assert_that(matcher.matches(seq, actualDescription), equal_to(True))
        assert_that(str(actualDescription), equal_to(""))

    @given(integers(min_value=0, max_value=1000), integers(min_value=0, max_value=1000))
    def test_mismatches(self, numBefore: int, numAfter: int) -> None:
        """
        L{IsSequenceOf} does not match a sequence if any of the elements
        are not matched by the parameterized matcher.

        :param numBefore: In the sequence to try to match, the number of
            elements expected to match before an expected mismatch.

        :param numAfter: In the sequence to try to match, the number of
            elements expected expected to match after an expected mismatch.
        """
        # Hide the non-matching value somewhere in the sequence.
        seq = [True] * numBefore + [False] + [True] * numAfter
        matcher = IsSequenceOf(equal_to(True))

        actualDescription = StringDescription()
        assert_that(matcher.matches(seq, actualDescription), equal_to(False))
        actualStr = str(actualDescription)
        assert_that(actualStr, contains_string("a sequence containing only"))
        assert_that(
            actualStr, contains_string(f"not sequence with element #{numBefore}")
        )


class IsTupleTests(SynchronousTestCase):
    """
    Tests for L{isTuple}.
    """

    @given(lists(integers(), min_size=0, max_size=10))
    def test_matches(self, elements: List[int]) -> None:
        """
        L{isTuple} matches tuples if they have the same number of elements
        as the number of matchers given and each element is matched by the
        corresponding matcher.

        :param elements: The elements with which to populate the tuple to
            attempt to match with L{isTuple}.
        """
        matcher = isTuple(*(equal_to(e) for e in elements))
        actualDescription = StringDescription()
        assert_that(matcher.matches(tuple(elements), actualDescription), equal_to(True))
        assert_that(str(actualDescription), equal_to(""))

    @given(
        lists(integers(), min_size=0, max_size=10),
        integers(),
        lists(integers(), min_size=0, max_size=10),
    )
    def test_mismatch(self, before: List[int], mismatch: int, after: List[int]) -> None:
        """
        L{isTuple} does not match if any element is not matched.

        :param before: For the tuple to match, elements leading up to an
            expected mismatching element.

        :param mismatch: An element expected to mismatch.

        :param after: For the tuple to match, elements following an expected
            mismatching element.
        """
        matchers = [equal_to(e) for e in before]
        matchers.append(not_(anything()))
        matchers = [equal_to(e) for e in after]
        matcher = isTuple(*matchers)

        elements = tuple(before) + (mismatch,) + tuple(after)
        actualDescription = StringDescription()
        assert_that(matcher.matches(elements, actualDescription), equal_to(False))

    @given(
        one_of(
            lists(integers(), max_size=2),
            text(max_size=2),
            binary(max_size=2),
            integers(),
        ),
    )
    def test_mismatchOtherType(self, mismatch: object) -> None:
        """
        L{isTuple} does not match non-tuple values.

        :param mismatch: A value of a type other than tuple.
        """
        matcher = isTuple(anything())
        assert_that(matcher.matches(mismatch), equal_to(False))


class IsFailureTests(SynchronousTestCase):
    """
    Tests for L{isFailure}.
    """

    @given(sampled_from([ValueError, ZeroDivisionError, RuntimeError]))
    def test_matches(self, excType: Type[BaseException]) -> None:
        """
        L{isFailure} matches instances of L{Failure} with matching
        attributes.

        :param excType: An exception type to wrap in a L{Failure} to be
            matched against.
        """
        matcher = isFailure(type=equal_to(excType))
        failure = Failure(excType())
        assert_that(matcher.matches(failure), equal_to(True))

    @given(sampled_from([ValueError, ZeroDivisionError, RuntimeError]))
    def test_mismatches(self, excType: Type[BaseException]) -> None:
        """
        L{isFailure} does not match instances of L{Failure} with
        attributes that don't match.

        :param excType: An exception type to wrap in a L{Failure} to be
            matched against.
        """
        matcher = isFailure(type=equal_to(excType), other=not_(anything()))
        failure = Failure(excType())
        assert_that(matcher.matches(failure), equal_to(False))

    def test_frames(self):
        """
        The L{similarFrame} matcher matches elements of the C{frames} list
        of a L{Failure}.
        """
        try:
            raise ValueError("Oh no")
        except BaseException:
            f = Failure()

        actualDescription = StringDescription()
        matcher = isFailure(
            frames=contains(similarFrame("test_frames", "test_matchers"))
        )
        assert_that(
            matcher.matches(f, actualDescription),
            equal_to(True),
            actualDescription,
        )
