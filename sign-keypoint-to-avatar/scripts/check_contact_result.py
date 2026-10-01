"""Read-only comparison of saved original and contact-corrected animations."""
import bpy,json,math
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
root=Path(__file__).resolve().parents[1]
results=[]
for filename in ('love_Model_M10_hands_aligned_color_v1.blend','love_Model_M10_contact_v1.blend'):
    bpy.ops.wm.open_mainfile(filepath=str(root/'output'/filename))
    scene=bpy.context.scene
    arm=max((o for o in scene.objects if o.type=='ARMATURE'),key=lambda a:sum(m.type=='ARMATURE' and m.object==a for o in scene.objects for m in o.modifiers))
    points={s:[] for s in ('L','R')}
    rotations={s:[] for s in points}
    for f in range(scene.frame_start,scene.frame_end+1):
        scene.frame_set(f)
        for s in points:
            pb=arm.pose.bones['J_Bip_'+s+'_Hand']
            points[s].append(pb.head.copy())
            rotations[s].append(pb.matrix.to_quaternion())
        for p in arm.pose.bones:
            assert all(math.isfinite(x) for x in p.matrix.translation)
            assert all(abs(x-1)<1e-4 for x in p.scale)
    mesh_intersections={}
    for f in (0,17,34,51,67,180,190,200,203,210,220):
        scene.frame_set(f)
        vertices={'L':[],'R':[]}; triangles={'L':[],'R':[]}
        for obj in scene.objects:
            if obj.type!='MESH' or not any(m.type=='ARMATURE' and m.object==arm for m in obj.modifiers):continue
            group_names={g.index:g.name for g in obj.vertex_groups}
            labels={}
            for v in obj.data.vertices:
                for side in vertices:
                    weight=sum(g.weight for g in v.groups if group_names[g.group].startswith('J_Bip_'+side+'_') and any(word in group_names[g.group] for word in ('Hand','Thumb','Index','Middle','Ring','Little')))
                    if weight>.5:labels[v.index]=side
            evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
            mesh=evaluated.to_mesh()
            assert len(mesh.vertices)==len(obj.data.vertices),'Topology changed; cannot compare vertex labels'
            mesh.calc_loop_triangles()
            for side in vertices:
                offset=len(vertices[side])
                vertices[side].extend(obj.matrix_world @ v.co for v in mesh.vertices)
                triangles[side].extend(tuple(offset+i for i in t.vertices) for t in mesh.loop_triangles if all(labels.get(i)==side for i in t.vertices))
            evaluated.to_mesh_clear()
        trees={s:BVHTree.FromPolygons(vertices[s],triangles[s],all_triangles=True) for s in vertices}
        mesh_intersections[f]=len(trees['L'].overlap(trees['R']))
    stats={}
    for s in points:
        pp=points[s]; qq=rotations[s]
        acc=[(pp[i+1]-pp[i]*2+pp[i-1]).length for i in range(1,len(pp)-1)]
        # Report active signing region separately from the long idle segment.
        stats[s]={'mean_wrist_acceleration_m_per_frame2':sum(acc)/len(acc),'max_wrist_acceleration':max(acc),'active_mean_acceleration':sum(acc[174:219])/45,'max_world_rotation_step_degrees':max(math.degrees(qq[i].rotation_difference(qq[i-1]).angle) for i in range(1,len(qq)))}
    results.append({'file':filename,'hands':stats,'hand_surface_triangle_intersections':mesh_intersections,'material_names':sorted({slot.material.name for o in scene.objects if o.type=='MESH' for slot in o.material_slots if slot.material})})
assert results[0]['material_names']==results[1]['material_names']
target=root/'diagnostics/love_Model_M10_contact_v1/saved_comparison.json'
target.write_text(json.dumps(results,indent=2),encoding='utf8')
print(json.dumps(results,indent=2))
