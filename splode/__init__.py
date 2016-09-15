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

if 'bpy' in locals():
    import importlib
    import splode.internal, splode.depcycles

    importlib.reload(splode.internal)
    importlib.reload(splode.depcycles)

import bpy


class FILE_OT_splode(bpy.types.Operator):
    """Explode the object"""

    bl_idname = 'file.splode'
    bl_label = 'Splode the current blendfile'
    bl_options = {'REGISTER'}

    root = bpy.props.StringProperty(
        name='root',
        default='//',
        subtype='FILE_PATH',
        description="Root path to explode stuff to",
    )

    def execute(self, context):
        import pathlib
        from . import internal

        internal.splode(pathlib.Path(self.root))

        return {'FINISHED'}


class SPLODE_OT_find_cycles(bpy.types.Operator):
    bl_idname = 'splode.find_cycles'
    bl_label = 'Find cycles'
    bl_options = {'REGISTER'}

    def execute(self, context):
        import itertools
        import logging
        from . import internal, depcycles

        log = logging.getLogger('%s.find_cycles' % __name__)
        user_map = internal.selective_user_map()

        cycle_gen = depcycles.find_cycles(user_map)
        cycles = depcycles.unify_cycles(cycle_gen)

        if cycles:
            log.info('Found %i cycles:', len(cycles))
            for cycle in itertools.islice(cycles, 10):
                log.info('   - %s', cycle)
            depcycles.assert_disjoint(cycles)
        else:
            log.info('Found no cycles')

        return {'FINISHED'}


def draw_info_header(self, context):
    layout = self.layout
    layout.operator(FILE_OT_splode.bl_idname, text='Splode')
    layout.operator(SPLODE_OT_find_cycles.bl_idname)
    layout.operator('object.make_local', text='Make all local').type = 'ALL'


def register():
    bpy.utils.register_class(FILE_OT_splode)
    bpy.utils.register_class(SPLODE_OT_find_cycles)
    bpy.types.VIEW3D_HT_header.append(draw_info_header)


def unregister():
    bpy.utils.unregister_class(FILE_OT_splode)
    bpy.utils.unregister_class(SPLODE_OT_find_cycles)
    bpy.types.VIEW3D_HT_header.remove(draw_info_header)


if __name__ == "__main__":
    register()
