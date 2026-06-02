import bpy
import sys
import os

if len(sys.argv) < 5:
    print("Usage: blender --background --python blender_item.py -- <input_png> <output_glb>")
    sys.exit(1)

input_png = sys.argv[-2]
output_glb = sys.argv[-1]

print(f"Processing: {input_png} → {output_glb}")

# پاک کردن صحنه
bpy.ops.wm.read_factory_settings(use_empty=True)

# لود تصویر
img = bpy.data.images.load(input_png)
name = os.path.splitext(os.path.basename(input_png))[0]

# ایجاد Plane با subdivision دقیق
bpy.ops.mesh.primitive_grid_add(
    x_subdivisions=img.size[1],
    y_subdivisions=img.size[0],
    size=2
)

obj = bpy.context.active_object
obj.name = name

# حفظ نسبت تصویر
if img.size[0] != img.size[1]:
    if img.size[0] > img.size[1]:
        obj.scale[1] = img.size[1] / img.size[0]
    else:
        obj.scale[0] = img.size[0] / img.size[1]
    bpy.ops.object.transform_apply(scale=True)

# Extrude (ضخامت)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.extrude_region_move(TRANSFORM_OT_translate={"value": (0, 0, 0.6)})
bpy.ops.object.mode_set(mode='OBJECT')

# Solidify برای ضخامت یکنواخت
mod = obj.modifiers.new(name="Solidify", type='SOLIDIFY')
mod.thickness = 0.6
mod.offset = 0

# متریال + تکسچر
mat = bpy.data.materials.new(name=name)
mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links
nodes.clear()

tex_node = nodes.new('ShaderNodeTexImage')
tex_node.image = img
tex_node.interpolation = 'Closest'

bsdf_node = nodes.new('ShaderNodeBsdfPrincipled')
output_node = nodes.new('ShaderNodeOutputMaterial')

links.new(tex_node.outputs[0], bsdf_node.inputs[0])
links.new(bsdf_node.outputs[0], output_node.inputs[0])

obj.data.materials.append(mat)

# Export GLB
bpy.ops.export_scene.gltf(
    filepath=output_glb,
    export_format='GLB',
    use_selection=True,
    export_apply=True,
    export_yup=True
)

print(f"✅ Successfully exported: {output_glb}")
