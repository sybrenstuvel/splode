"""Dependency cycles handling."""

import logging

log = logging.getLogger(__name__)


def find_cycles(user_map: dict) -> list:
    """Generator, yields dependency cycles."""

    log.info('Finding dependency cycles.')

    def chain(startid, chain_so_far=()):
        # log.debug('    - inspecting (%r, %r)', startid, chain_so_far)
        if startid in chain_so_far:
            # log.info('    - found cycle %r', chain_so_far)
            if len(chain_so_far) > 1:
                yield chain_so_far
            return

        for nextid in user_map[startid]:
            if nextid is startid:  # an idblock depending on itself is fine
                continue
            yield from chain(nextid, chain_so_far + (startid,))

    for idblock in user_map.keys():
        yield from chain(idblock)


def unify_cycles(cycles: list) -> set:
    """Unifies cycles, so that A→B, B→A and A→B→C are reported only once as A→B→C."""

    unified = set()

    for cycle in cycles:
        cycleset = frozenset(cycle)
        if cycleset in unified:
            continue

        # Search for a superset or subset of this cycle.
        for other in unified:
            assert isinstance(other, frozenset)
            if other.issuperset(cycleset):
                # A superset of this cycle is already known, so we don't have to report it.
                break
            if other.issubset(cycleset):
                # This cycle should replace the other, as it's a superset.
                unified.discard(other)
                unified.add(cycleset)
                break
        else:
            # We didn't break, so we found no superset nor subset.
            # This is a unique cycle (so far).
            unified.add(cycleset)

    return unified


def assert_disjoint(cycles: set):
    """Asserts that all cycles in the set are disjoint."""

    seen = {}  # mapping from the idblock to the cycle it was first seen in.
    for cycle in cycles:
        for idblock in cycle:
            assert idblock not in seen, \
                'idblock %r seen in cycles %r and %r' % (idblock, seen[idblock], cycle)
            seen[idblock] = cycle


def find_main_idblocks(cycles: set, type_order: dict) -> (set, set):
    """Find the main idblocks in a dependency cycle.

    Returns two sets. The first set contains the main objects for all cycles,
    the second set contains all other objects in the cycles.
    """

    main_idblocks = set()
    other_idblocks = set()

    def order(idblock) -> int:
        key = idblock.rna_type.name.upper()
        if key == 'OBJECT':
            altkey = 'OBJECT_%s' % idblock.type
            if altkey in type_order:
                key = altkey

        return type_order[key]

    for cycle in cycles:
        main_idblock = min(cycle, key=order)
        main_idblocks.add(main_idblock)
        other_idblocks.update(cycle - {main_idblock})

    return main_idblocks, other_idblocks


if __name__ == '__main__':
    # Some trivial testing
    import unittest


    class TestCycles(unittest.TestCase):
        def test_unify_cycles(self):
            uc = unify_cycles([
                ['A', 'B'],
                ['A', 'B', 'C'],
                ['B', 'A'],
                ['D', 'E'],
                ['E', 'D'],
            ])

            self.assertEqual({frozenset({'A', 'B', 'C'}), frozenset({'D', 'E'})}, uc)

        def test_assert_disjoint(self):
            assert_disjoint({frozenset({'A', 'B', 'C'}), frozenset({'D', 'E'})})
            assert_disjoint(set())

            self.assertRaises(AssertionError,
                              assert_disjoint,
                              {frozenset({'A', 'B', 'C'}), frozenset({'C', 'D', 'E'})})

    unittest.main()
