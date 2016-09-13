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

import bpy

log = logging.getLogger('splode')

# A set of all ID types.
# Taken from https://www.blender.org/api/blender_python_api_master/bpy.types.KeyingSetPath.html#bpy.types.KeyingSetPath.id_type
ID_TYPES = {'ACTION', 'ARMATURE', 'BRUSH', 'CAMERA', 'CACHEFILE', 'CURVE', 'FONT', 'GREASEPENCIL',
            'GROUP', 'IMAGE', 'KEY', 'LAMP', 'LIBRARY', 'LINESTYLE', 'LATTICE', 'MASK', 'MATERIAL',
            'META', 'MESH', 'MOVIECLIP', 'NODETREE', 'OBJECT', 'PAINTCURVE', 'PALETTE', 'PARTICLE',
            'SCENE', 'SCREEN', 'SOUND', 'SPEAKER', 'TEXT', 'TEXTURE', 'WINDOWMANAGER', 'WORLD'}

# We don't libify all ID types, just the ones in SPLODE_ID_TYPES.
SPLODE_ID_TYPES = frozenset(ID_TYPES - {'BRUSH', 'CACHEFILE', 'LIBRARY', 'SCREEN', 'WINDOWMANAGER'})


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
# https://www.blender.org/api/blender_python_api_2_77_3/bpy.types.BlendDataLibraries.html#bpy.types.BlendDataLibraries.load

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

        for idblock in bottom_up():
            dirname = '_' + singular_to_plural[idblock.rna_type.name.lower()]
            path = root / dirname
            libify(idblock, path)

        return {'FINISHED'}


def mkdirs(path: pathlib.Path):
    os.makedirs(bpy.path.abspath(str(path)), exist_ok=True)


def libify(obj: bpy.types.ID, path: pathlib.Path):
    from . import first

    log.info('Libifying %s', obj)

    if obj.library:
        log.info('    - already libified, skipping.')
        return None

    mkdirs(path)
    fname = str(path / ('%s.blend' % obj.name))
    log.info('    - saving to %s' % fname)

    bpy.data.libraries.write(fname, {obj}, relative_remap=True)

    linked_in = []
    with bpy.data.libraries.load(fname, link=True, relative=True) as (data_from, data_to):
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
                 len(linked_in), fname, obj.name)

        attr = singular_to_plural[obj.rna_type.name.lower()]
        data_to_subset = getattr(data_to, attr)

        replacement = first.first(data_to_subset, key=lambda ob: ob.name == obj.name)
        if replacement is None:
            log.warning('    - no imported object is named %s; not replacing.',
                        obj.name)
        log.info('    - chose %s.%s from %s', attr, replacement.name, linked_in)

    assert replacement.library is not None
    replacement.library.name = '%s-%s' % (obj.rna_type.name.lower(), obj.name)
    obj.user_remap(replacement)


def bottom_up(id_types: set = SPLODE_ID_TYPES):
    """Generator, yields datablocks from the bottom (i.e. uses nothing) upward.

    Stupid in that it doesn't detect cycles yet.
    """

    import collections

    id_types = set(id_types)  # convert from frozenset to set
    user_map = bpy.data.user_map(key_types=id_types, value_types=id_types)

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

    to_visit = set(reversed_map.keys())

    def visit(idblock):
        to_visit.discard(idblock)

        dependencies = reversed_map[idblock]
        for dep in dependencies:
            if dep in to_visit:
                yield from visit(dep)

        yield idblock

    while to_visit:
        yield from visit(to_visit.pop())


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
