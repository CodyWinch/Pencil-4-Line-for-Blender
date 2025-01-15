# SPDX-License-Identifier: GPL-2.0-or-later
# The Original Code is Copyright (C) P SOFTHOUSE Co., Ltd. All rights reserved.


if "bpy" in locals():
    import imp
    imp.reload(pencil4_render_session)
    imp.reload(pencil4_render_images)
    imp.reload(pencil4_viewport)
else:
    from . import pencil4_render_session
    from . import pencil4_render_images
    from . import pencil4_viewport

from .pencil4_render_session import Pencil4RenderSession as RenderSession
from .merge_helper import merge_helper
from .node_tree import PencilNodeTree

import bpy
import os
from bpy.app.handlers import persistent

__session: RenderSession = None

def append():
    bpy.app.handlers.render_pre.append(on_pre_render)
    bpy.app.handlers.render_cancel.append(on_render_cancel)
    bpy.app.handlers.render_complete.append(on_render_complete)
    bpy.app.handlers.frame_change_post.append(on_post_frame_change)
    bpy.app.handlers.save_pre.append(on_save_pre)
    bpy.app.handlers.save_post.append(on_save_post)
    bpy.app.handlers.load_post.append(on_load_post)
    bpy.app.handlers.depsgraph_update_pre.append(on_depsgraph_update_pre)

def remove():
    bpy.app.handlers.render_pre.remove(on_pre_render)
    bpy.app.handlers.render_cancel.remove(on_render_cancel)
    bpy.app.handlers.render_complete.remove(on_render_complete)
    bpy.app.handlers.frame_change_post.remove(on_post_frame_change)
    bpy.app.handlers.save_pre.remove(on_save_pre)
    bpy.app.handlers.save_post.remove(on_save_post)
    bpy.app.handlers.load_post.remove(on_load_post)
    bpy.app.handlers.depsgraph_update_pre.remove(on_depsgraph_update_pre)

def in_render_session() -> bool:
    return __session is not None

@persistent
def on_pre_render(scene: bpy.types.Scene):
    global __session
    if __session is None:
        __session = RenderSession()
        pencil4_viewport.ViewportLineRenderManager.in_render_session = True
        pencil4_render_images.correct_duplicated_output_images(scene)
        pencil4_render_images.setup_images(scene)
    else:
        __session.cleanup_frame()

@persistent
def on_render_cancel(scene: bpy.types.Scene):
    global __session
    if __session is not None:
        __session.cleanup_all()
        __session = None
        pencil4_viewport.ViewportLineRenderManager.in_render_session = False

@persistent
def on_render_complete(scene: bpy.types.Scene):
    global __session
    if __session is not None:
        __session.cleanup_all()
        __session = None
        pencil4_render_images.unpack_images(scene)
        pencil4_viewport.ViewportLineRenderManager.in_render_session = False

@persistent
def on_post_frame_change(scene: bpy.types.Scene, depsgraph: bpy.types.Depsgraph):
    global __session

    prefs = bpy.context.preferences.addons["goo-outputsetup"].preferences

    if prefs.output_lineart and scene.frame_end >= scene.frame_current >= scene.frame_start:
        render = bpy.context.scene.render

        og_perc = render.resolution_percentage
        og_format = render.image_settings.file_format
        og_mode = render.image_settings.color_mode
        og_depth = render.image_settings.color_depth

        render.resolution_percentage = 100
        render.image_settings.file_format = "PNG"
        render.image_settings.color_mode = "RGBA"
        render.image_settings.color_depth = "16"

        if __session is None:
            __session = RenderSession()
            pencil4_viewport.ViewportLineRenderManager.in_render_session = True
            pencil4_render_images.correct_duplicated_output_images(scene)

        __session.draw_line(depsgraph)
        pencil4_viewport.ViewportLineRenderManager.invalidate_objects_cache()

        __session.cleanup_all()
        __session = None
        pencil4_viewport.ViewportLineRenderManager.in_render_session = False

        for vl in scene.view_layers:
            if vl.pencil4_line_outputs.output.main is not None:
                out_fp = vl.pencil4_line_outputs.vector_output_base_path + vl.pencil4_line_outputs.vector_outputs[0].sub_path + ("%04d" % scene.frame_current) + '.png'
                print(str(os.path.normpath(bpy.path.abspath((out_fp)))))
                vl.pencil4_line_outputs.output.main.save_render(str(os.path.normpath(bpy.path.abspath((out_fp)))))

                # THIS WAS MODIFIED AND I LOST THE MODIFICATIONS
                # IT WOULD CHECK FOR IF THE EPS EXISTED AND THE TIF FILE DID NOT EXIST BEFORE RUNNING THE SAVE
                # IT ALSO USED TIFS INSTEAD OF PNGS
        
        render.resolution_percentage = og_perc
        render.image_settings.file_format = og_format
        render.image_settings.color_mode = og_mode
        render.image_settings.color_depth = og_depth

    else:

        if __session is not None:
            __session.draw_line(depsgraph)
        pencil4_viewport.ViewportLineRenderManager.invalidate_objects_cache()

@persistent
def on_save_pre(dummy):
    pencil4_viewport.on_save_pre()
    pencil4_render_images.ViewLayerLineOutputs.on_save_pre()
    merge_helper.link()
    PencilNodeTree.set_first_update_flag()

@persistent
def on_save_post(dummy):
    merge_helper.unlink()
    PencilNodeTree.clear_first_update_flag()

@persistent
def on_load_post(dummy):
    pencil4_viewport.on_load_post()
    pencil4_render_images.ViewLayerLineOutputs.on_load_post()
    merge_helper.unlink()
    PencilNodeTree.correct_curve_tree()
    PencilNodeTree.migrate_nodes()

@persistent
def on_depsgraph_update_pre(scene: bpy.types.Scene):
    pencil4_viewport.ViewportLineRenderManager.invalidate_objects_cache()
