/**
 * json_to_obj.mjs
 * Minecraft JSON Model → OBJ + MTL converter
 *
 * پشتیبانی از:
 *   • Bedrock Edition (geometry.json  با  "minecraft:geometry" یا فرمت قدیمی "geometry.xxx")
 *   • Java Edition (block/item model با "elements" و "textures")
 *   • Resource Pack مستقل (هر دو فرمت)
 *
 * خروجی:
 *   • model.obj  — مش کامل با UV دقیق
 *   • model.mtl  — تعریف متریال
 *
 * استفاده:
 *   node json_to_obj.mjs  input.json  output.obj
 */

import fs   from "fs";
import path from "path";

// ─── ورودی‌ها ────────────────────────────────────────────────────────────────
const [,, jsonFile, objFile] = process.argv;
if (!jsonFile || !objFile) {
  console.error("Usage: node json_to_obj.mjs <input.json> <output.obj>");
  process.exit(1);
}

const raw  = fs.readFileSync(jsonFile, "utf-8");
const data = JSON.parse(raw);

const outDir  = path.dirname(objFile);
const baseName = path.basename(objFile, ".obj");
const mtlFile  = path.join(outDir, baseName + ".mtl");

fs.mkdirSync(outDir, { recursive: true });

// ─── تشخیص فرمت ──────────────────────────────────────────────────────────────
function detectFormat(d) {
  if (d["minecraft:geometry"] || Array.isArray(d.geometry)) return "bedrock";
  if (d.elements)                                            return "java";
  // فرمت قدیمی Bedrock: کلیدهایی مثل "geometry.humanoid"
  const keys = Object.keys(d);
  if (keys.some(k => k.startsWith("geometry.")))            return "bedrock_legacy";
  return "unknown";
}

const fmt = detectFormat(data);
if (fmt === "unknown") {
  console.error("❌ فرمت JSON ناشناخته است. باید Bedrock یا Java باشد.");
  process.exit(1);
}

console.log(`✅ فرمت شناسایی شد: ${fmt}`);

// ─── ابزارهای هندسی ──────────────────────────────────────────────────────────

/** محاسبه UV برای هر فیس باکس با رویکرد pixel-perfect */
function boxUVFaces(x, y, z, sx, sy, sz, uOffset, vOffset, textureW, textureH) {
  /**
   * چیدمان استاندارد Bedrock UV برای یک cube:
   *
   *          [top]
   *  [west][north][east][south]
   *         [bottom]
   *
   *  uOffset, vOffset = گوشه بالا-چپ باکس UV در atlas
   */
  const tw = textureW, th = textureH;
  const u0 = uOffset, v0 = vOffset;

  // ابعاد فیس‌ها (pixel)
  // north/south: sx × sy   east/west: sz × sy   top/bottom: sx × sz
  const faces = {
    //          u1                v1                u2                v2
    bottom: [u0 + sz,           v0,                u0 + sz + sx,     v0 + sz        ],
    top:    [u0 + sz + sx,      v0,                u0 + sz + sx*2,   v0 + sz        ],
    north:  [u0 + sz,           v0 + sz,           u0 + sz + sx,     v0 + sz + sy   ],
    south:  [u0 + sz + sx + sz, v0 + sz,           u0 + sz*2 + sx*2, v0 + sz + sy   ],
    west:   [u0,                v0 + sz,           u0 + sz,          v0 + sz + sy   ],
    east:   [u0 + sz + sx,      v0 + sz,           u0 + sz*2 + sx,   v0 + sz + sy   ],
  };

  // تبدیل به 0..1 نرمال
  const norm = {};
  for (const [face, [fu1, fv1, fu2, fv2]] of Object.entries(faces)) {
    norm[face] = [fu1/tw, 1 - fv2/th, fu2/tw, 1 - fv1/th];
  }
  return norm;
}

/** UV دلخواه per-face (Java Edition) */
function javaFaceUV(uvArray, textureW, textureH, rotation = 0) {
  let [u1, v1, u2, v2] = uvArray;
  // نرمال‌سازی
  u1 /= 16; v1 /= 16; u2 /= 16; v2 /= 16;
  // چرخش UV (rotation های ۰، ۹۰، ۱۸۰، ۲۷۰ درجه)
  // خروجی: آرایه چهار جفت [u,v] برای چهار گوشه فیس (bl, br, tr, tl)
  const corners = [
    [u1, 1 - v2],
    [u2, 1 - v2],
    [u2, 1 - v1],
    [u1, 1 - v1],
  ];
  const rot = ((rotation % 360) + 360) % 360;
  const steps = rot / 90;
  const rotated = [];
  for (let i = 0; i < 4; i++) {
    rotated.push(corners[(i + steps) % 4]);
  }
  return rotated; // [bl, br, tr, tl]
}

// ─── OBJ builder ─────────────────────────────────────────────────────────────

const vertices  = [];   // [x, y, z]
const uvCoords  = [];   // [u, v]
const normals   = [];   // [nx, ny, nz]
const faces_out = [];   // strings مستقیم OBJ
let   vOffset_v = 0;    // offset شمارنده vertex
let   vOffset_u = 0;    // offset شمارنده uv
let   vOffset_n = 0;    // offset شمارنده normal

// نرمال‌های استاندارد ۶ جهت
const STD_NORMALS = [
  [ 0,  0,  1],  // south  (1)
  [ 0,  0, -1],  // north  (2)
  [ 1,  0,  0],  // east   (3)
  [-1,  0,  0],  // west   (4)
  [ 0,  1,  0],  // up     (5)
  [ 0, -1,  0],  // down   (6)
];
STD_NORMALS.forEach(n => normals.push(n));
vOffset_n = 6;

const NORMAL_IDX = { south:1, north:2, east:3, west:4, up:5, down:6,
                     bottom:6, top:5 };

// شمارنده گروه برای پارت‌ها
let groupCounter = 0;

/**
 * افزودن یک cube به OBJ
 * @param {number[]} origin  [x, y, z] گوشه کوچک
 * @param {number[]} size    [sx, sy, sz]
 * @param {object}  uvData  { north, south, east, west, top, bottom }
 *                           هر فیس: [u1, v1, u2, v2] نرمال‌شده 0..1
 *                           یا null برای حذف فیس
 * @param {number[][]} rot   ماتریس چرخش ۳×۳ (اختیاری)
 * @param {number[]}   pivot مرکز چرخش (اختیاری)
 * @param {string}     groupName
 * @param {string}     materialName
 */
function addCube(origin, size, uvData, rot3x3, pivot, groupName, materialName) {
  const [ox, oy, oz] = origin;
  const [sx, sy, sz] = size;

  // ۸ راس cube (ترتیب ثابت)
  const rawVerts = [
    [ox,      oy,      oz     ],  // 0 ---
    [ox + sx, oy,      oz     ],  // 1 +--
    [ox + sx, oy + sy, oz     ],  // 2 ++-
    [ox,      oy + sy, oz     ],  // 3 -+-
    [ox,      oy,      oz + sz],  // 4 --+
    [ox + sx, oy,      oz + sz],  // 5 +-+
    [ox + sx, oy + sy, oz + sz],  // 6 +++
    [ox,      oy + sy, oz + sz],  // 7 -++
  ];

  // اعمال چرخش
  const finalVerts = rawVerts.map(v => {
    if (!rot3x3) return v;
    const [px, py, pz] = pivot || [0, 0, 0];
    const dx = v[0] - px, dy = v[1] - py, dz = v[2] - pz;
    const r = rot3x3;
    return [
      r[0][0]*dx + r[0][1]*dy + r[0][2]*dz + px,
      r[1][0]*dx + r[1][1]*dy + r[1][2]*dz + py,
      r[2][0]*dx + r[2][1]*dy + r[2][2]*dz + pz,
    ];
  });

  const vBase = vOffset_v + 1;
  finalVerts.forEach(([x, y, z]) => vertices.push([x, y, z]));
  vOffset_v += 8;

  // تعریف هر فیس: [i0,i1,i2,i3] از ۸ راس + کدام نرمال + کلید UV
  const FACE_DEFS = [
    { key: "north",  vi: [3, 2, 1, 0], nk: "north"  },  // -Z
    { key: "south",  vi: [4, 5, 6, 7], nk: "south"  },  // +Z
    { key: "west",   vi: [0, 4, 7, 3], nk: "west"   },  // -X
    { key: "east",   vi: [1, 2, 6, 5], nk: "east"   },  // +X  ← اصلاح ترتیب
    { key: "down",   vi: [0, 1, 5, 4], nk: "down"   },  // -Y
    { key: "up",     vi: [3, 7, 6, 2], nk: "up"     },  // +Y
    // نام‌های جایگزین برای UV
    { key: "bottom", vi: [0, 1, 5, 4], nk: "down"   },
    { key: "top",    vi: [3, 7, 6, 2], nk: "up"     },
  ];

  // فیلتر تکراری
  const seenKeys = new Set();
  const filteredFaces = FACE_DEFS.filter(f => {
    if (seenKeys.has(f.nk)) return false;
    seenKeys.add(f.nk);
    return true;
  });

  faces_out.push(`g ${groupName || "cube_" + groupCounter++}`);
  faces_out.push(`usemtl ${materialName || "mat_default"}`);

  filteredFaces.forEach(({ key, vi, nk }) => {
    const uv = uvData[key] || uvData[nk];
    if (!uv) return;  // فیس حذف شده

    let uvCorners;
    if (Array.isArray(uv[0])) {
      // حالت Java: آرایه ۴ جفت [u,v]
      uvCorners = uv;
    } else {
      // حالت Bedrock: [u1, v1, u2, v2]
      const [u1, v1, u2, v2] = uv;
      uvCorners = [
        [u1, v1],
        [u2, v1],
        [u2, v2],
        [u1, v2],
      ];
    }

    const uBase = vOffset_u + 1;
    uvCorners.forEach(([u, v]) => uvCoords.push([u, v]));
    vOffset_u += 4;

    const nIdx = NORMAL_IDX[nk] || 1;
    const [i0, i1, i2, i3] = vi.map(i => vBase + i);
    const [t0, t1, t2, t3] = [uBase, uBase+1, uBase+2, uBase+3];

    // quad → دو مثلث
    faces_out.push(`f ${i0}/${t0}/${nIdx} ${i1}/${t1}/${nIdx} ${i2}/${t2}/${nIdx}`);
    faces_out.push(`f ${i0}/${t0}/${nIdx} ${i2}/${t2}/${nIdx} ${i3}/${t3}/${nIdx}`);
  });
}

// ─── تبدیل زاویه به ماتریس چرخش ─────────────────────────────────────────────

function rotationMatrix(axis, angleDeg) {
  const a = (angleDeg * Math.PI) / 180;
  const c = Math.cos(a), s = Math.sin(a);
  if (axis === "x") return [[1,0,0],[0,c,-s],[0,s,c]];
  if (axis === "y") return [[c,0,s],[0,1,0],[-s,0,c]];
  if (axis === "z") return [[c,-s,0],[s,c,0],[0,0,1]];
  return [[1,0,0],[0,1,0],[0,0,1]];
}

function multiplyMat(A, B) {
  const R = [[0,0,0],[0,0,0],[0,0,0]];
  for (let i=0;i<3;i++) for (let j=0;j<3;j++)
    for (let k=0;k<3;k++) R[i][j] += A[i][k]*B[k][j];
  return R;
}

// ─── پارسر Bedrock ───────────────────────────────────────────────────────────

function parseBedrock(d) {
  // پشتیبانی از هر دو فرمت جدید و قدیمی
  let geos = [];
  if (d["minecraft:geometry"]) {
    const mg = d["minecraft:geometry"];
    geos = Array.isArray(mg) ? mg : [mg];
  } else if (Array.isArray(d.geometry)) {
    geos = d.geometry;
  } else {
    // فرمت قدیمی
    for (const [k, v] of Object.entries(d)) {
      if (k.startsWith("geometry.")) geos.push({ description: { identifier: k }, ...v });
    }
  }

  // تکسچر پیش‌فرض ۱۶×۱۶
  let texW = 64, texH = 64;

  geos.forEach((geo, gi) => {
    const desc = geo.description || geo;
    texW = desc.texture_width  || desc.texturewidth  || 64;
    texH = desc.texture_height || desc.textureheight || 64;

    const bones = geo.bones || [];
    bones.forEach((bone, bi) => {
      const boneName = bone.name || `bone_${bi}`;
      const pivot    = bone.pivot || [0, 0, 0];
      const cubes    = bone.cubes || [];

      // چرخش استخوان
      let boneMat = null;
      if (bone.rotation) {
        const [rx, ry, rz] = bone.rotation;
        boneMat = multiplyMat(multiplyMat(rotationMatrix("y", ry), rotationMatrix("x", rx)), rotationMatrix("z", rz));
      }

      cubes.forEach((cube, ci) => {
        const origin = cube.origin || [0, 0, 0];
        const size   = cube.size   || [1, 1, 1];
        const inflate = cube.inflate || 0;

        // اعمال inflate
        const inflatedOrigin = [origin[0]-inflate, origin[1]-inflate, origin[2]-inflate];
        const inflatedSize   = [size[0]+inflate*2, size[1]+inflate*2, size[2]+inflate*2];

        // چرخش cube
        let cubeMat = boneMat;
        let cubePivot = pivot;
        if (cube.rotation) {
          const [rx, ry, rz] = cube.rotation;
          const cm = multiplyMat(multiplyMat(rotationMatrix("y", ry), rotationMatrix("x", rx)), rotationMatrix("z", rz));
          cubeMat = cubeMat ? multiplyMat(cubeMat, cm) : cm;
          cubePivot = cube.pivot || pivot;
        }

        let uvData = {};

        if (cube.uv) {
          if (Array.isArray(cube.uv)) {
            // UV box mode: [u, v]
            const [u0, v0] = cube.uv;
            const [sx, sy, sz] = inflatedSize;
            uvData = boxUVFaces(
              inflatedOrigin[0], inflatedOrigin[1], inflatedOrigin[2],
              sx, sy, sz, u0, v0, texW, texH
            );
          } else {
            // Per-face UV mode
            for (const [face, faceUV] of Object.entries(cube.uv)) {
              if (!faceUV) continue;
              const { uv, uv_size } = faceUV;
              if (!uv) continue;
              const [fu, fv] = uv;
              const [fw, fh] = uv_size || [inflatedSize[0], inflatedSize[1]];
              const faceLower = face.toLowerCase();
              uvData[faceLower] = [
                fu / texW,
                1 - (fv + fh) / texH,
                (fu + fw) / texW,
                1 - fv / texH,
              ];
            }
          }
        }

        addCube(
          inflatedOrigin, inflatedSize, uvData,
          cubeMat, cubePivot,
          `${boneName}_${ci}`,
          "mat_default"
        );
      });
    });
  });
}

// ─── پارسر Bedrock Legacy ────────────────────────────────────────────────────

function parseBedrockLegacy(d) {
  // تبدیل به ساختار جدید و ارسال به پارسر اصلی
  const converted = { "minecraft:geometry": [] };
  for (const [k, v] of Object.entries(d)) {
    if (!k.startsWith("geometry.")) continue;
    const texW = v.texturewidth  || 64;
    const texH = v.textureheight || 64;
    converted["minecraft:geometry"].push({
      description: { identifier: k, texture_width: texW, texture_height: texH },
      bones: v.bones || [],
    });
  }
  parseBedrock(converted);
}

// ─── پارسر Java Edition ──────────────────────────────────────────────────────

function parseJava(d) {
  const texW = 16, texH = 16;  // Java همیشه ۱۶×۱۶ per face UV

  const elements = d.elements || [];
  const textures = d.textures || {};

  // نقشه texture variable → نام فایل
  function resolveTexture(ref) {
    if (!ref) return "texture";
    while (ref.startsWith("#")) {
      const key = ref.slice(1);
      ref = textures[key] || ref;
      if (!ref.startsWith("#")) break;
    }
    return path.basename(ref.replace(/^minecraft:/, "")).replace(/^block\/|^item\//, "");
  }

  elements.forEach((el, ei) => {
    const from = el.from || [0, 0, 0];
    const to   = el.to   || [16, 16, 16];

    const origin = [from[0]/16, from[1]/16, from[2]/16];
    const size   = [(to[0]-from[0])/16, (to[1]-from[1])/16, (to[2]-from[2])/16];

    // چرخش
    let mat = null, pivotPt = null;
    if (el.rotation) {
      const { origin: rOrig, axis, angle } = el.rotation;
      pivotPt = rOrig ? [rOrig[0]/16, rOrig[1]/16, rOrig[2]/16] : [0.5, 0.5, 0.5];
      mat = rotationMatrix(axis || "y", angle || 0);
    }

    const uvData = {};
    const elFaces = el.faces || {};

    for (const [faceName, faceDef] of Object.entries(elFaces)) {
      if (!faceDef) continue;
      const faceUV = faceDef.uv || [from[0], from[1], to[0], to[1]];  // fallback
      const rot    = faceDef.rotation || 0;
      const texVar = faceDef.texture || "#all";
      const texName = resolveTexture(texVar);

      // UV corners [bl, br, tr, tl]
      uvData[faceName] = javaFaceUV(faceUV, 16, 16, rot);

      // material per texture
      // (در این نسخه یک متریال داریم؛ چند تکسچر → نام اول)
    }

    addCube(origin, size, uvData, mat, pivotPt, `el_${ei}`, "mat_default");
  });
}

// ─── اجرا ────────────────────────────────────────────────────────────────────

if      (fmt === "bedrock")        parseBedrock(data);
else if (fmt === "bedrock_legacy") parseBedrockLegacy(data);
else if (fmt === "java")           parseJava(data);

// ─── نوشتن OBJ ───────────────────────────────────────────────────────────────

const objLines = [
  `# Generated by json_to_obj.mjs`,
  `# Minecraft JSON Model Converter`,
  `# Format: ${fmt}`,
  ``,
  `mtllib ${baseName}.mtl`,
  ``,
  `# Vertices (${vertices.length})`,
  ...vertices.map(([x, y, z]) => `v ${x.toFixed(6)} ${y.toFixed(6)} ${z.toFixed(6)}`),
  ``,
  `# UV Coordinates (${uvCoords.length})`,
  ...uvCoords.map(([u, v]) => `vt ${u.toFixed(6)} ${v.toFixed(6)}`),
  ``,
  `# Normals (${normals.length})`,
  ...normals.map(([nx, ny, nz]) => `vn ${nx.toFixed(4)} ${ny.toFixed(4)} ${nz.toFixed(4)}`),
  ``,
  ...faces_out,
];

fs.writeFileSync(objFile, objLines.join("\n"), "utf-8");

// ─── نوشتن MTL ───────────────────────────────────────────────────────────────

const mtlLines = [
  `# MTL generated by json_to_obj.mjs`,
  ``,
  `newmtl mat_default`,
  `Ka 1.000 1.000 1.000`,
  `Kd 1.000 1.000 1.000`,
  `Ks 0.000 0.000 0.000`,
  `d 1.0`,
  `illum 1`,
  `map_Kd texture.png`,
];

fs.writeFileSync(mtlFile, mtlLines.join("\n"), "utf-8");

const vCount = vertices.length;
const fCount = faces_out.filter(l => l.startsWith("f ")).length;
console.log(`✅ تبدیل موفق!`);
console.log(`   فرمت: ${fmt}`);
console.log(`   Vertices: ${vCount}`);
console.log(`   Triangles: ${fCount}`);
console.log(`   OBJ: ${objFile}`);
console.log(`   MTL: ${mtlFile}`);
