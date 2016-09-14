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


def draw_info_header(self, context):
    layout = self.layout
    layout.operator(FILE_OT_splode.bl_idname, text='Splode')
    layout.operator('object.make_local', text='Make all local').type = 'ALL'


def register():
    bpy.utils.register_class(FILE_OT_splode)
    bpy.types.INFO_HT_header.append(draw_info_header)


def unregister():
    bpy.utils.unregister_class(FILE_OT_splode)
    bpy.types.INFO_HT_header.remove(draw_info_header)


if __name__ == "__main__":
    register()
