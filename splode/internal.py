import logging
import os
import pathlib
from enum import Enum
import collections

import bpy

log = logging.getLogger(__name__)

# A set of all ID types.
# Taken from https://www.blender.org/api/blender_python_api_master/bpy.types.KeyingSetPath.html#bpy.types.KeyingSetPath.id_type
ID_TYPES = {'ACTION', 'ARMATURE', 'BRUSH', 'CAMERA', 'CACHEFILE', 'CURVE', 'FONT', 'GREASEPENCIL',
            'GROUP', 'IMAGE', 'KEY', 'LAMP', 'LIBRARY', 'LINESTYLE', 'LATTICE', 'MASK', 'MATERIAL',
            'META', 'MESH', 'MOVIECLIP', 'NODETREE', 'OBJECT', 'PAINTCURVE', 'PALETTE', 'PARTICLE',
            'SCENE', 'SCREEN', 'SOUND', 'SPEAKER', 'TEXT', 'TEXTURE', 'WINDOWMANAGER', 'WORLD'}

# We don't libify all ID types, just the ones in SPLODE_ID_TYPES.
# The scene shouldn't be libified, otherwise every blendfile that uses scene Scene will link
# to the same scene object.
SPLODE_ID_TYPES = frozenset(ID_TYPES - {'BRUSH', 'CACHEFILE', 'LIBRARY', 'SCENE', 'SCREEN',
                                        'WINDOWMANAGER'})

# Ordering of ID types for cyclic dependency handling. When a set of ID blocks have cyclic
# dependencies, the entire dependency chain will be saved to a single blendfile. The
# ID block with the lowest value in the SPLODE_ID_TYPE_ORDER dict will determine the filename
# of that blendfile. Objects are noted in 'OBJECT_{object.type}' notatation; if these don't
# exist for the particular object type, 'OBJECT' is used.
SPLODE_ID_TYPE_ORDER = collections.defaultdict(
    int,  # so the default value for unlisted types is 0.
    OBJECT_ARMATURE=-20,
    OBJECT=-10,
    OBJECT_EMPTY=-5,
)


class BlenderExitCodes(Enum):
    OK = 0
    ERROR_SINGLE_THINGY_NOT_FOUND = 7
    ERROR_NOT_IMPLEMENTED_YET = 13


class SingularPluralDict(dict):
    def __getitem__(self, key):
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return '%ss' % key


singular_to_plural = SingularPluralDict({
    'mesh': 'meshes',
})


def splode(root_path: pathlib.Path):
    """Main function, explodes the blendfile into single-thingy blendfiles.

    The single-thingy blendfiles may contain more than one thingy; in case of
    dependency cycles the entire cycle is stored in one blendfile.
    Also see SPLODE_ID_TYPE_ORDER.
    """

    from . import depcycles

    user_map = selective_user_map()

    cycle_list = depcycles.find_cycles(user_map)
    to_embed = set()
    if cycle_list:
        cycles = depcycles.unify_cycles(cycle_list)
        depcycles.assert_disjoint(cycles)
        log.info('Found %i disjoint cycles: %s', len(cycles), cycles)

        # For each cycle, determine which object is going to be saved.
        # Blender will automatically save the rest of the cycle in that file.
        to_save, to_embed = depcycles.find_main_idblocks(cycles, SPLODE_ID_TYPE_ORDER)
        log.info('    - going to save: %r', to_save)
        log.info('    - going to embed: %r', to_embed)

    for idblock in bottom_up(user_map):
        if idblock in to_embed:
            log.info("Skipping libification of %r, it'll be part of another file.", idblock)
        else:
            libify(idblock, root_path)


def mkdirs(path: pathlib.Path):
    os.makedirs(bpy.path.abspath(str(path)), exist_ok=True)


def libify(idblock: bpy.types.ID, root_path: pathlib.Path, *, write_idblock=True):
    log.info('Libifying %r', idblock)

    fname = blendfile_for_idblock(idblock, root_path)

    if idblock.library:
        log.info('    - already libified in %s, skipping.', idblock.library.filepath)
        return None

    mkdirs(fname.parent)

    if write_idblock:
        log.info('    - saving to %s', fname)
        bpy.data.libraries.write(str(fname), {idblock}, relative_remap=True)

    log.info('    - linking from %s', fname)
    linked_in = []
    with bpy.data.libraries.load(str(fname), link=True, relative=True) as (data_from, data_to):
        # Link everything.
        for attr in dir(data_to):
            to_import = getattr(data_from, attr)
            if not to_import:
                log.debug('    - skipping %i %s', len(to_import), attr)
                continue

            log.info('    - importing %i %s', len(to_import), attr)
            setattr(data_to, attr, to_import)
            linked_in.extend((attr, name) for name in to_import)

    # Replace every idblock with the linked-in version.
    # have_set_libname = False
    for attr in dir(data_to):
        linked_in = getattr(data_to, attr)
        try:
            local_idblocks = getattr(bpy.data, attr)
        except AttributeError:
            if linked_in:
                log.warning('Skipping replacement of linked in objects for: %s', linked_in)
            continue

        for replacement in linked_in:
            # if not have_set_libname:
            #     assert replacement.library is not None
            #     replacement.library.name = '%s-%s' % (idblock.rna_type.name.lower(), idblock.name)
            #     have_set_libname = True
            local_idblock = local_idblocks[replacement.name]
            log.info('    - replacing %r with linked-in %r from %r',
                     local_idblock, replacement, replacement.library.filepath)
            local_idblock.user_remap(replacement)


def blendfile_for_idblock(idblock: bpy.types.ID, root_path: pathlib.Path) -> pathlib.Path:
    """Returns the filename for the single-thingy blendfile containing this idblock."""

    dirname = '_' + singular_to_plural[idblock.rna_type.name.lower()]
    path = root_path / dirname
    return path / ('%s.blend' % idblock.name)


def bottom_up(user_map: dict):
    """Generator, yields datablocks from the bottom (i.e. uses nothing) upward.

    Stupid in that it doesn't detect cycles yet.

    :param user_map: result from `selective_user_map()`.
    """

    # Reverse the user_map() mapping, so we have idblock -> {set of idblocks it uses}
    reversed_map = collections.defaultdict(set)
    for idblock, users in user_map.items():
        if users:
            for user in users:
                reversed_map[user].add(idblock)
        else:
            # We can yield unused blocks immediately, and be done with them.
            if idblock.use_fake_user:
                yield idblock

    to_visit = set(user_map.keys())

    def visit(idblock):
        to_visit.discard(idblock)

        dependencies = reversed_map[idblock]
        for dep in dependencies:
            if dep in to_visit:
                yield from visit(dep)

        yield idblock

    while to_visit:
        # At the top level it doesn't matter which object we visit first.
        yield from visit(to_visit.pop())


def selective_user_map(id_types: set = SPLODE_ID_TYPES) -> dict:
    """Returns bpy.data.user_map(key_types=id_types, value_types=id_types)"""

    id_types = set(id_types)  # convert from frozenset to set
    user_map = bpy.data.user_map(key_types=id_types, value_types=id_types)

    import pprint
    log.info('User map:\n%s', pprint.pformat(user_map))

    return user_map
