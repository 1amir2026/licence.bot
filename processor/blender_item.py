import bpy
import sys
import os

# دریافت آرگومان‌ها
if len(sys.argv) < 5:
    print("❌ Usage: blender --background --python blender_item.py -- <input_png> <output_glb>")
    sys.exit(1)

input_png = sys.argv[-2]
output_glb = sys.argv[-1]

print(f"🚀 Processing: {input_png} → {output_glb}")

# پاک کردن صحنه
bpy.ops.wm.read_factory_settings(use_empty=True)

# لود MCPrep (نسخه اصلاح شده)
addon_path = os.path.join(os.path.dirname(__file__), "..", "mcprep")
if os.path.exists(addon_path):
    try:
        bpy.ops.preferences.addon_enable(module="mcprep")
        print("✅ MCPrep addon enabled")
    except Exception as e:
        print(f"⚠️ MCPrep enable warning: {e}")

# تابع ساده و مطمئن برای ساخت آیتم
def create_minecraft_item(input_path, output_path):
    try:
        # لود تصویر
        img = bpy.data.images.load(input_path, check_existing=True)
        name = os.path.splitext(os.path.basename(input_path))[0]

        # ایجاد مش با subdivision
        bpy.ops.mesh.primitive_grid_add(
            x_subdivisions=img.size[1],
            y_subdivisions=img.size[0],
            size=2.0
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

        # Solidify (ضخامت)
        mod = obj.modifiers.new("Solidify", 'SOLIDIFY')
        mod.thickness = 0.08
        mod.offset = 0

        # متریال
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()

        tex_node = nodes.new('ShaderNodeTexImage')
        tex_node.image = img
        tex_node.interpolation = 'Closest'
        tex_node.location = (-400, 0)

        bsdf_node = nodes.new('ShaderNodeBsdfPrincipled')
        bsdf_node.location = (-100, 0)

        output_node = nodes.new('ShaderNodeOutputMaterial')
        output_node.location = (200, 0)

        links.new(tex_node.outputs[0], bsdf_node.inputs[0])
        links.new(bsdf_node.outputs[0], output_node.inputs[0])

        obj.data.materials.append(mat)

        # اکسپورت GLB
        bpy.ops.export_scene.gltf(
            filepath=output_path,
            export_format='GLB',
            use_selection=True,
            export_yup=True,
            export_apply=True
        )
        print(f"✅ Successfully exported: {output_path}")
        return True

    except Exception as e:
        print(f"❌ Error in create_minecraft_item: {e}")
        raise

# اجرا
try:
    create_minecraft_item(input_png, output_glb)
    print("🎉 Process completed successfully")
except Exception as e:
    print(f"💥 Fatal error: {e}")
    sys.exit(1)
