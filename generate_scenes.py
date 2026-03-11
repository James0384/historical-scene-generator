# =============================================================================
# HISTORICAL SCENE GENERATOR ADD-ON - v1.7.17 (Blender 4.2+ / 4.5)
# FIXED: Trees now constrained to stay within ground plane bounds (-40..40)
#       Strong fence buffer (5.5 units), safe scene clearing, user camera
# =============================================================================
bl_info = {
    "name": "Historical Scene Generator",
    "author": "James Miller",
    "version": (1, 7, 17),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Historical Synth",
    "description": "Custom mesh templates + batch RGB + Depth render for AI training",
    "category": "3D View",
}

import random
import os
import bpy
import glob
from mathutils import Matrix, Vector
from bpy.props import StringProperty, IntProperty, FloatProperty

# ====================== HELPERS ======================
def origin_to_bottom(ob):
    if ob.type != 'MESH': return
    me = ob.data
    mw = ob.matrix_world
    local_verts = [mw @ Vector(v[:]) for v in ob.bound_box]
    center = sum(local_verts, Vector()) / 8
    lowest_z = min(v.z for v in local_verts)
    center.z = lowest_z
    local_center = mw.inverted() @ center
    me.transform(Matrix.Translation(-local_center))
    ob.matrix_world.translation = ob.matrix_world @ local_center

def frange(start, stop, step):
    x = start
    while (step > 0 and x <= stop + 1e-6) or (step < 0 and x >= stop - 1e-6):
        yield x
        x += step
    if abs((x - step) - stop) > 1e-6:
        yield stop

def add_and_set_camera(scene):
    props = scene.historical_props
    user_cam_name = props.camera_name
    user_cam = bpy.data.objects.get(user_cam_name)
    
    if user_cam and user_cam.type == 'CAMERA':
        scene.camera = user_cam
        print(f"Using user-selected camera: {user_cam_name}")
        return
    
    print("No valid user camera – creating default")
    for obj in list(scene.objects):
        if obj.type == 'CAMERA':
            bpy.data.objects.remove(obj, do_unlink=True)
    
    bpy.ops.object.camera_add(location=(30, -50, 25))
    cam = bpy.context.object
    
    target = Vector((0, 0, 4))
    direction = target - cam.location
    rot_quat = direction.to_track_quat('-Z', 'Y')
    cam.rotation_euler = rot_quat.to_euler()
    
    cam.data.lens = 50
    cam.data.sensor_width = 36
    cam.data.clip_start = 0.1
    cam.data.clip_end = 300.0
    
    scene.camera = cam

# ====================== UI ======================
class HISTORICAL_PT_Panel(bpy.types.Panel):
    bl_label = "Historical Scene Generator"
    bl_idname = "HISTORICAL_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Historical Synth"

    def draw(self, context):
        layout = self.layout
        props = context.scene.historical_props
        
        row = layout.row(align=True)
        row.prop_search(props, "building_name", bpy.data, "objects", text="Building Mesh")
        row.operator("historical.use_active_building", text="", icon='EYEDROPPER')
        
        row = layout.row(align=True)
        row.prop_search(props, "tree_name", bpy.data, "objects", text="Tree Mesh")
        row.operator("historical.use_active_tree", text="", icon='EYEDROPPER')
        
        row = layout.row(align=True)
        row.prop_search(props, "camera_name", bpy.data, "objects", text="Camera")
        row.operator("historical.use_active_camera", text="", icon='EYEDROPPER')
        
        layout.prop_search(props, "fence_material_name", bpy.data, "materials", text="Fence Material")
        layout.separator()
        layout.prop(props, "batch_size")
        layout.prop(props, "output_folder")
        layout.prop(props, "depth_far_plane", text="Depth Far (m)")
        layout.separator()
        layout.operator("historical.generate_batch", text="Generate Batch Scenes", icon='RENDER_STILL')

class HistoricalProperties(bpy.types.PropertyGroup):
    building_name: StringProperty(name="Building Mesh", default="")
    tree_name: StringProperty(name="Tree Mesh", default="")
    camera_name: StringProperty(name="Camera", default="")
    fence_material_name: StringProperty(name="Fence Material", default="")
    batch_size: IntProperty(name="Batch Size", default=3, min=1)
    output_folder: StringProperty(name="Output Folder", subtype='DIR_PATH', default="//training_data/")
    depth_far_plane: FloatProperty(name="Depth Far Plane", default=100.0, min=10.0)

# ====================== USE ACTIVE OPERATORS ======================
class HISTORICAL_OT_UseActiveBuilding(bpy.types.Operator):
    bl_idname = "historical.use_active_building"
    bl_label = "Use Active"

    def execute(self, context):
        obj = context.active_object
        if obj and obj.type == 'MESH':
            context.scene.historical_props.building_name = obj.name
            self.report({'INFO'}, f"Building set: {obj.name}")
        else:
            self.report({'WARNING'}, "Select a mesh first")
        return {'FINISHED'}

class HISTORICAL_OT_UseActiveTree(bpy.types.Operator):
    bl_idname = "historical.use_active_tree"
    bl_label = "Use Active"

    def execute(self, context):
        obj = context.active_object
        if obj and obj.type == 'MESH':
            context.scene.historical_props.tree_name = obj.name
            self.report({'INFO'}, f"Tree set: {obj.name}")
        else:
            self.report({'WARNING'}, "Select a mesh first")
        return {'FINISHED'}

class HISTORICAL_OT_UseActiveCamera(bpy.types.Operator):
    bl_idname = "historical.use_active_camera"
    bl_label = "Use Active Camera"

    def execute(self, context):
        obj = context.active_object
        if obj and obj.type == 'CAMERA':
            context.scene.historical_props.camera_name = obj.name
            self.report({'INFO'}, f"Camera set: {obj.name}")
        else:
            self.report({'WARNING'}, "Select a camera object first")
        return {'FINISHED'}

# ====================== BATCH OPERATOR ======================
class HISTORICAL_OT_GenerateBatch(bpy.types.Operator):
    bl_idname = "historical.generate_batch"
    bl_label = "Generate Batch Scenes"

    def execute(self, context):
        props = context.scene.historical_props
        building_obj = bpy.data.objects.get(props.building_name)
        tree_obj = bpy.data.objects.get(props.tree_name)
        fence_mat = bpy.data.materials.get(props.fence_material_name)

        if not building_obj or not tree_obj or not fence_mat:
            self.report({'ERROR'}, "Please select Building, Tree, and Fence Material")
            return {'CANCELLED'}

        output_dir = bpy.path.abspath(props.output_folder)
        os.makedirs(output_dir, exist_ok=True)

        scene = context.scene
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
        scene.render.use_compositing = True
        scene.use_nodes = True

        for i in range(props.batch_size):
            base_name = f"scene_{i:03d}"
            print(f"→ Rendering {base_name}...")

            # === SAFE SCENE CLEAR ===
            source_names = {props.building_name, props.tree_name}
            if props.camera_name:
                source_names.add(props.camera_name)

            to_remove = [obj for obj in scene.objects if obj.name not in source_names]

            for obj in to_remove:
                for coll in list(obj.users_collection):
                    coll.objects.unlink(obj)

            for obj in to_remove:
                bpy.data.objects.remove(obj, do_unlink=True)

            if context.view_layer.objects.active:
                context.view_layer.objects.active = None
            bpy.ops.object.select_all(action='DESELECT')

            context.view_layer.update()
            bpy.context.evaluated_depsgraph_get().update()

            # === GROUND ===
            bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, 0))
            ground = bpy.context.object
            ground_mat = bpy.data.materials.new("Ground_Grass")
            ground_mat.use_nodes = True
            bsdf = ground_mat.node_tree.nodes.get("Principled BSDF")
            if bsdf: bsdf.inputs[0].default_value = (0.15, 0.35, 0.1, 1.0)
            ground.data.materials.append(ground_mat)

            # === FENCE ===
            half_l = 18.0
            half_w = 13.0
            fence_height = 1.8
            spacing = 2.5
            posts = []
            fence_sides = [
                (lambda x: (x, half_w, 0), -half_l, half_l, spacing),
                (lambda y: (half_l, y, 0), half_w, -half_w, -spacing),
                (lambda x: (x, -half_w, 0), half_l, -half_l, -spacing),
                (lambda y: (-half_l, y, 0), -half_w, half_w, spacing)
            ]
            for pos_func, start, stop, step in fence_sides:
                for val in frange(start, stop, step):
                    bpy.ops.mesh.primitive_cube_add(size=1, location=pos_func(val))
                    post = bpy.context.object
                    post.scale = (0.15, 0.15, fence_height)
                    bpy.ops.object.transform_apply(scale=True)
                    origin_to_bottom(post)
                    post.location.z = 0
                    post.data.materials.append(fence_mat)
                    posts.append(post)

            for idx in range(len(posts)):
                p1 = posts[idx].location
                p2 = posts[(idx + 1) % len(posts)].location
                length = (p1 - p2).length - 0.18
                if length <= 0: continue
                mid = (p1 + p2) / 2
                rot = 1.5708 if abs(p2.y - p1.y) > abs(p2.x - p1.x) else 0.0
                for z in [0.4, fence_height - 0.3]:
                    bpy.ops.mesh.primitive_cube_add(size=1, location=(mid.x, mid.y, z))
                    rail = bpy.context.object
                    rail.scale = (length, 0.07, 0.07)
                    rail.rotation_euler.z = rot
                    bpy.ops.object.transform_apply(scale=True, rotation=True)
                    rail.data.materials.append(fence_mat)

            # === BUILDING ===
            building_copy = building_obj.copy()
            building_copy.data = building_obj.data.copy()
            scene.collection.objects.link(building_copy)
            building_copy.scale = (15, 10, 6)
            bpy.context.view_layer.objects.active = building_copy
            bpy.ops.object.transform_apply(scale=True)
            origin_to_bottom(building_copy)
            building_copy.location = (0, 0, 0)

            # === TREES – constrained to ground plane + strong fence buffer ===
            num_trees = random.randint(15, 25)
            placed = 0
            attempts = 0
            max_attempts = 600

            BUFFER = 5.5  # fence buffer distance

            fence_min_x = -half_l
            fence_max_x = half_l
            fence_min_y = -half_w
            fence_max_y = half_w

            excl_min_x = fence_min_x + BUFFER
            excl_max_x = fence_max_x - BUFFER
            excl_min_y = fence_min_y + BUFFER
            excl_max_y = fence_max_y - BUFFER

            inside_count = 0

            # Ground plane bounds (size=80 → -40 to +40)
            ground_min = -40.0
            ground_max = 40.0

            while placed < num_trees and attempts < max_attempts:
                attempts += 1
                x = random.uniform(ground_min, ground_max)
                y = random.uniform(ground_min, ground_max)
                
                # Reject if inside buffered fence rectangle
                if excl_min_x < x < excl_max_x and excl_min_y < y < excl_max_y:
                    inside_count += 1
                    continue
                
                # Extra circular safety near center
                dist_to_center = (x**2 + y**2)**0.5
                if dist_to_center < 19.0:  # slightly larger than fence half-diagonal
                    inside_count += 1
                    continue
                
                tree_copy = tree_obj.copy()
                tree_copy.data = tree_obj.data.copy()
                scene.collection.objects.link(tree_copy)
                origin_to_bottom(tree_copy)
                tree_copy.location = (x, y, 0)
                tree_copy.rotation_euler.z = random.uniform(0, 6.28)
                tree_copy.scale = (random.uniform(0.8, 1.4),) * 3
                placed += 1

            print(f"Placed {placed}/{num_trees} trees after {attempts} attempts")
            print(f"Rejected {inside_count} trees as inside buffered fence (buffer={BUFFER})")

            add_and_set_camera(scene)

            vl = context.view_layer
            vl.use_pass_z = True
            vl.update()

            # ====================== COMPOSITOR SETUP ======================
            tree = scene.node_tree
            nodes = tree.nodes
            links = tree.links
            nodes.clear()

            rl = nodes.new('CompositorNodeRLayers')

            comp = nodes.new('CompositorNodeComposite')
            links.new(rl.outputs['Image'], comp.inputs['Image'])

            rgb_node = nodes.new('CompositorNodeOutputFile')
            rgb_node.base_path = output_dir
            rgb_node.format.file_format = 'PNG'
            rgb_node.file_slots[0].path = f"{base_name}_rgb"

            links.new(rl.outputs['Image'], rgb_node.inputs[0])

            math_node = nodes.new('CompositorNodeMath')
            math_node.operation = 'DIVIDE'
            math_node.inputs[1].default_value = props.depth_far_plane

            norm_node = nodes.new('CompositorNodeNormalize')

            depth_node = nodes.new('CompositorNodeOutputFile')
            depth_node.base_path = output_dir
            depth_node.format.file_format = 'OPEN_EXR'
            depth_node.format.color_depth = '32'
            depth_node.file_slots[0].path = f"{base_name}_depth"

            links.new(rl.outputs['Depth'], math_node.inputs[0])
            links.new(math_node.outputs[0], norm_node.inputs[0])
            links.new(norm_node.outputs[0], depth_node.inputs[0])

            scene.render.filepath = os.path.join(output_dir, "no_write_here/")

            bpy.context.evaluated_depsgraph_get().update()
            bpy.ops.render.render(write_still=True)

            for suffix, ext in [("_rgb", ".png"), ("_depth", ".exr")]:
                pattern = os.path.join(output_dir, f"{base_name}{suffix}*0001{ext}")
                for old_file in glob.glob(pattern):
                    new_file = old_file.replace("0001", "")
                    if os.path.exists(new_file):
                        os.remove(new_file)
                    os.rename(old_file, new_file)
                    print(f"  Renamed: {old_file} → {new_file}")

            print(f"   Saved: {base_name}_rgb.png + {base_name}_depth.exr")

        self.report({'INFO'}, f"Batch complete! {props.batch_size} scenes saved to {output_dir}")
        return {'FINISHED'}

# ====================== REGISTER ======================
classes = (
    HistoricalProperties,
    HISTORICAL_PT_Panel,
    HISTORICAL_OT_UseActiveBuilding,
    HISTORICAL_OT_UseActiveTree,
    HISTORICAL_OT_UseActiveCamera,
    HISTORICAL_OT_GenerateBatch
)

def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.historical_props = bpy.props.PointerProperty(type=HistoricalProperties)

def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
    del bpy.types.Scene.historical_props

if __name__ == "__main__":
    register()