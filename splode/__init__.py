bl_info = {
    "name": "Splode",
    "author": "Sybren A. Stüvel <sybren@blender.studio>",
    "version": (0, 1),
    "blender": (2, 78, 0),
    "location": "Je moeder",
    "description": "Explodes the current blendfile",
    "warning": "Explodes",
    "category": "System",
}

import pathlib
import os
import logging
from enum import Enum

import bpy

log = logging.getLogger('splode')

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


# bpy.data.libraries.write is documented at:
# https://www.blender.org/api/blender_python_api_2_77_3/bpy.types.BlendDataLibraries.html#bpy.types.BlendDataLibraries.write

class OBJECT_OT_splode(bpy.types.Operator):
    """Explode the object"""

    bl_idname = "object.splode"
    bl_label = "Splode the current object"
    bl_options = {'REGISTER', 'UNDO'}

    root = bpy.props.StringProperty(
        name='root',
        default='//',
        subtype='FILE_PATH',
        description="Root path to explode stuff to",
    )

    @classmethod
    def poll(cls, context):
        return '-libified' not in bpy.context.blend_data.filepath

    def execute(self, context):
        root = pathlib.Path(self.root)

        user_map = selective_user_map()

        for idblock in bottom_up(user_map):
            libify(idblock, root)

        # Handle cycles; this uses a name-based approach, so we can use the
        # same user_map (which still refers to pre-sploding objects).

        # FIXME: This creates cyclic links between Blender libraries, which isn't supported yet.
        # mont29 sees possibilities to make it work using placeholder datablocks, and then making
        # everything local when loading, but this requires too much Blender code change to
        # invest time in at the moment.
        cycles = find_cycles(user_map)
        if cycles:
            idblocks = {idblock for cycle in cycles for idblock in cycle}
            log.warning('Going to re-link the following: %s', idblocks)
            for idblock in idblocks:
                fname = blendfile_for_idblock(idblock, root)
                absfname = bpy.path.abspath(str(fname))
                rna_type_name = idblock.rna_type.name

                run_blender([
                    '--background', absfname,
                    '--python-expr',
                    'import splode; splode.relink_all_except(%r, %r)' %
                        (rna_type_name, idblock.name)
                ])

        return {'FINISHED'}


def run_blender(cli_args: list):
    import subprocess

    args = [bpy.app.binary_path] + cli_args
    log.info('Running %s', args)
    blender = subprocess.Popen(args)
    try:
        blender.communicate(timeout=300)  # Should be easily done in 5 minutes
    except subprocess.TimeoutExpired:
        blender.kill()
        blender.communicate()  # flush & close buffers
        raise

    returncode = BlenderExitCodes(blender.returncode)
    if returncode is not BlenderExitCodes.OK:
        log.error('Blender returned an error code: %r', returncode)
        raise RuntimeError('Blender returned an error code: %r' % returncode)


def mkdirs(path: pathlib.Path):
    os.makedirs(bpy.path.abspath(str(path)), exist_ok=True)


def relink_all_except(rna_type_name: str, idblock_name: str):
    """Re-link all objects except the named idblock.

    Assumes the current file should be a single-thingy file, and saves to root_path='//../x/y.blend'

    WARNING: THIS FUNCTION QUITS BLENDER BY CALLING SYS.EXIT(n). It is meant to be
    called in a Blender subprocess.
    """

    import sys

    single_thingy_fmtname = '<%s %s>' % (rna_type_name, idblock_name)
    root = pathlib.Path('//..')
    log.info('Relinking all except %s, root=%s', single_thingy_fmtname, root)

    # Libify everything except for one idblock.
    this_single_thingy = None
    user_map = selective_user_map()
    for idblock in bottom_up(user_map):
        if idblock.name == idblock_name and rna_type_name == idblock.rna_type.name:
            log.info('Skipping %r', idblock)
            this_single_thingy = idblock
            continue
        libify(idblock, root, write_idblock=False)

    log.info('Done relinking all except %s', single_thingy_fmtname)

    # Complain if we couldn't find the single thingy
    if this_single_thingy is None:
        log.error('Did not find %s in %s, but it should be!',
                  single_thingy_fmtname, bpy.data.filepath)
        sys.exit(BlenderExitCodes.ERROR_SINGLE_THINGY_NOT_FOUND)

    # Write the single thingy again to the current blend file
    # FIXME: (well, to another one for dev purposes).
    outpath = bpy.data.filepath.replace('.blend', '-relinked.blend')
    log.info('Saving %s to %s', single_thingy_fmtname, outpath)
    bpy.data.libraries.write(outpath, {this_single_thingy}, relative_remap=True)

    log.info('Exiting Blender')
    sys.exit(0)


def libify(idblock: bpy.types.ID, root_path: pathlib.Path, *, write_idblock=True):
    from . import first

    log.info('Libifying %s', idblock)

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
        # Append everything.
        for attr in dir(data_to):
            to_import = getattr(data_from, attr)
            if not to_import:
                log.debug('    - skipping %i %s', len(to_import), attr)
                continue

            log.info('    - importing %i %s', len(to_import), attr)
            setattr(data_to, attr, to_import)
            linked_in.extend((attr, name) for name in to_import)

    if len(linked_in) == 1:
        (attr, name) = linked_in[0]
        replacement = getattr(data_to, attr)[0]
    else:
        log.info('    - imported %i IDs from %s, guessing which one which replaces %s',
                 len(linked_in), fname, idblock.name)

        attr = singular_to_plural[idblock.rna_type.name.lower()]
        data_to_subset = getattr(data_to, attr)

        replacement = first.first(data_to_subset, key=lambda ob: ob.name == idblock.name)
        if replacement is None:
            log.warning('    - no imported object is named %s; not replacing.',
                        idblock.name)
        log.info('    - chose %s.%s from %s', attr, replacement.name, linked_in)

    assert replacement.library is not None
    replacement.library.name = '%s-%s' % (idblock.rna_type.name.lower(), idblock.name)
    idblock.user_remap(replacement)


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

    import collections

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


def find_cycles(user_map: dict) -> list:
    """Returns dependency cycles."""

    log.info('Finding dependency cycles.')

    cycles = []

    def chain(startid, chain_so_far=()):
        log.debug('    - inspecting (%r, %r)', startid, chain_so_far)
        if startid in chain_so_far:
            log.info('    - found cycle %r', chain_so_far)
            cycles.append(chain_so_far)
            return

        for nextid in user_map[startid]:
            chain(nextid, chain_so_far + (startid,))

    for idblock in user_map.keys():
        chain(idblock)

    log.info('Found %i cycles.', len(cycles))
    return cycles


def draw_info_header(self, context):
    layout = self.layout
    layout.operator(OBJECT_OT_splode.bl_idname, text='Splode')
    layout.operator('object.make_local', text='Make all local').type = 'ALL'


def register():
    bpy.utils.register_class(OBJECT_OT_splode)
    bpy.types.INFO_HT_header.append(draw_info_header)


def unregister():
    bpy.utils.unregister_class(OBJECT_OT_splode)
    bpy.types.INFO_HT_header.remove(draw_info_header)


if __name__ == "__main__":
    register()
