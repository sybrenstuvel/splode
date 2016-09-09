# Splode User Stories

## Scope

These are now-likely-doable userstories, not a description of our vision on
the final functionality.

## Terminology

*thingy*: thing we want to manage with Splode, such as an object, a mesh,
a material, armature, action, etc.

*single-thingy blendfile*: a blendfile that contains a single thingy, such
as an object, a mesh, or a material.

*to libify*: to export a single datablock into a single-thingy blendfile, then
load that blendfile as a library and link the single thingy back in. This
thus replaces the local thingy with a library link.

## 1. Initial import of a model

1. Artist creates model, consisting of object, mesh, materials and textures.
2. Artist saves as one monolythic blendfile.
3. Artist presses "Splode to SVN" button.
4. Blender defines a filesystem path (relative to SVN root?) for each datablock
   that will be exploded (see next point), and stores that path in a custom
   property<sup>1</sup>.
5. Blender *libifies* all the thingies in the current file.
6. Blender saves the blendfile?<sup>2</sup>
7. Artist commits whichever single-thingy blendfile(s) she wants to.
8. Artist commits the master blendfile (which now only contains links)
   as a task file (see next user story).


## 3. Preparing a blendfile for a task

1. Preparateur links relevant thingies into a blendfile.
2. Preparateur saves the blendfile and stores it so that it is available to artists.
   This could be in SVN, but could also be as a download from Attract.


## 2. Performing a task

1. Artist opens the prepared blendfile (see previous user story).
2. Artist presses the "implode" button, which makes everything local to the file.<sup>3</sup>
3. Artist performs work.
4. Artist presses the "Splode to SVN" button.
5. Blender defines a filesystem path (relative to SVN root?) for each datablock
   that will be exploded (see next point).
6. Blender handles renames:
    - compares that path to what was stored previously in the custom property;
    - renames the single-thingy blendfile (in an SVN-aware way);
    - stores the new path in the custom property.
7. Blender *libifies* all the thingies in the current file.
8. Blender saves the blendfile?<sup>2</sup>
9. Artist commits whichever single-thingy blendfile(s) she wants to.


## Footnotes

1. This allows us to track renames in Blender, so we can rename single-thingy
blendfiles when the thingy is renamed in Blender.
2. To be discussed whether this is done by Blender or the artist, and whether
this would overwrite the existing blendfile or be saved next to it under a
different name.
3. This could possibly be performed by an addon too, so that the artist doesn't
have to remember this.

## Forseen issues

Note that this is not an exhaustive list.

1. Circular dependencies.
2. Missing support for certain datablock types, resulting in too many thingies
   being written into what should be a single-thingy blendfile.
3. Indirectly linked datablocks (i.e. libraries used by libraries).
4. Overrides.
