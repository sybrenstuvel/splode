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
        return context.object and context.object.type == 'MESH' \
            and '-libified' not in bpy.context.blend_data.filepath

    def execute(self, context):

        ob = context.object
        root = pathlib.Path(self.root)

        # Libify everything.
        libify_materials(ob.data.materials, root)
        libify_material_slots(ob.material_slots, root)
        libify_mesh(ob, 'data', root)
        libify_object(bpy.context.scene, ob, root)

        # Save the current file under a temp name, and reload it, to garbage-collect all unused datablocks.
        tmpname = bpy.context.blend_data.filepath.replace('.blend', '-libified.blend')
        bpy.ops.wm.save_as_mainfile(filepath=tmpname)
        bpy.ops.wm.open_mainfile(filepath=tmpname)

        # Make everything we libified local again.
        # bpy.ops.object.make_local(type='ALL')

        return {'FINISHED'}


def mkdirs(path: pathlib.Path):
    os.makedirs(bpy.path.abspath(str(path)), exist_ok=True)


def libify(obj: bpy.types.ID, path: pathlib.Path):
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

        replacement = next((ob for ob in data_to_subset if ob.name == obj.name), None)
        if replacement is None:
            log.warning('    - no imported object is named %s; not replacing.',
                        obj.name)
        log.info('    - chose %s.%s from %s', attr, replacement.name, linked_in)

    assert replacement.library is not None
    replacement.library.name = '%s-%s' % (obj.rna_type.name.lower(), obj.name)
    obj.user_remap(replacement)


def libify_materials(materials, blendpath: pathlib.Path):
    log.info('Libifying materials')
    for mat_idx, mat in enumerate(materials):
        libify(mat, blendpath / '_materials')


def libify_material_slots(mslots, blendpath: pathlib.Path):
    log.info('Libifying material slots')
    for slot in mslots:
        if not slot.material: continue
        libify(slot.material, blendpath / '_materials')


def libify_mesh(owner, propname: str, blendpath: pathlib.Path):
    log.info('Libifying mesh %s', str)
    mesh = getattr(owner, propname)
    libify(mesh, blendpath / '_meshes')


def libify_object(scene, ob, blendpath: pathlib.Path):
    log.info('Libifying object %s', ob)
    libify(ob, blendpath / '_objects')


def draw_info_header(self, context):
    layout = self.layout
    layout.operator(OBJECT_OT_splode.bl_idname, text='Splode')
    layout.operator('object.make_local', text='Make all local').type='ALL'


def register():
    bpy.utils.register_class(OBJECT_OT_splode)
    bpy.types.INFO_HT_header.append(draw_info_header)


def unregister():
    bpy.utils.unregister_class(OBJECT_OT_splode)
    bpy.types.INFO_HT_header.remove(draw_info_header)


if __name__ == "__main__":
    register()
