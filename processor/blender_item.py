import bpy
import sys
import os
from pathlib import Path

# دریافت آرگومان‌ها از بات
if len(sys.argv) < 5:
    print("Usage: blender --background --python blender_item.py -- <input_png> <output_glb>")
    sys.exit(1)

input_png = sys.argv[-2]
output_glb = sys.argv[-1]

print(f"Processing: {input_png} → {output_glb}")

# پاک کردن صحنه
bpy.ops.wm.read_factory_settings(use_empty=True)

# Import MCPrep logic (if available)
mcprep_path = os.path.join(os.path.dirname(__file__), "mcprep")
if os.path.exists(mcprep_path):
    sys.path.append(mcprep_path)
    try:
        from item import spawn_item_from_filepath
        print("MCPrep item module loaded")
        use_mcprep = True
    except:
        use_mcprep = False
        print("MCPrep not found, using fallback")
else:
    use_mcprep = False

# Fallback function if MCPrep not fully working
def create_minecraft_item(input_path, output_path):
    # Load image
    img = bpy.data.images.load(input_path)
    name = os.path.splitext(os.path.basename(input_path))[0]
    
    # Create grid (simple plane with subdivisions)
    bpy.ops.mesh.primitive_grid_add(
        x_subdivisions=img.size[1] + 1,
        y_subdivisions=img.size[0] + 1,
        size=2
    )
    obj = bpy.context.object
    obj.name = name
    
    # Scale to keep aspect ratio
    if img.size[0] > img.size[1]:
        obj.scale[1] = img.size[1] / img.size[0]
    else:
        obj.scale[0] = img.size[0] / img.size[1]
    
    bpy.ops.object.transform_apply(scale=True)
    
    # Add thickness
    mod = obj.modifiers.new(name="Solidify", type='SOLIDIFY')
    mod.thickness = 0.1
    mod.offset = 0
    
    # Material with image texture
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    
    for node in nodes:
        nodes.remove(node)
    
    tex_node = nodes.new('ShaderNodeTexImage')
    tex_node.image = img
    tex_node.interpolation = 'Closest'
    
    bsdf_node = nodes.new('ShaderNodeBsdfPrincipled')
    output_node = nodes.new('ShaderNodeOutputMaterial')
    
    links.new(tex_node.outputs[0], bsdf_node.inputs[0])
    links.new(bsdf_node.outputs[0], output_node.inputs[0])
    
    obj.data.materials.append(mat)
    
    # Export as GLB
    bpy.ops.export_scene.gltf(
        filepath=output_path,
        export_format='GLB',
        use_selection=True,
        export_yup=True
    )
    print(f"Exported: {output_path}")

# اجرا
try:
    create_minecraft_item(input_png, output_glb)
    print("✅ Success")
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)