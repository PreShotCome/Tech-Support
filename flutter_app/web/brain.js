import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

// =================================================================
// CONFIG — region centers in 3D space + category mapping.
// =================================================================
// Brain extends along X: +X = anterior (frontal), -X = posterior (occipital).
// Y: +Y = superior (top), -Y = inferior (bottom).
// Z: lateral (depth, points toward viewer in default camera).
// Region radii are tuned to keep nodes INSIDE the cortex envelope
// (which is roughly x:±1.65, y:±0.95, z:±1.05 after the noise displacement).
const REGIONS = {
  frontal:    { cx:  0.85, cy:  0.20, cz: 0.30, rx: 0.40, ry: 0.35, rz: 0.30, label: "Frontal — Voice / Identity" },
  motor:      { cx:  0.10, cy:  0.55, cz: 0.25, rx: 0.30, ry: 0.15, rz: 0.30, label: "Motor — Tools" },
  parietal:   { cx: -0.45, cy:  0.45, cz: 0.30, rx: 0.40, ry: 0.25, rz: 0.30, label: "Parietal — Memory" },
  occipital:  { cx: -1.15, cy:  0.05, cz: 0.15, rx: 0.28, ry: 0.40, rz: 0.25, label: "Occipital — Vision" },
  temporal:   { cx:  0.20, cy: -0.40, cz: 0.40, rx: 0.65, ry: 0.20, rz: 0.25, label: "Temporal — Episodic" },
  wernicke:   { cx: -0.55, cy: -0.10, cz: 0.35, rx: 0.20, ry: 0.15, rz: 0.20, label: "Wernicke — Research" },
  broca:      { cx:  0.85, cy: -0.20, cz: 0.30, rx: 0.20, ry: 0.15, rz: 0.20, label: "Broca — Skills" },
  cerebellum: { cx: -1.35, cy: -0.55, cz: 0.05, rx: 0.28, ry: 0.20, rz: 0.28, label: "Cerebellum — Drift" },
  brainstem:  { cx: -0.20, cy: -1.15, cz: 0.00, rx: 0.10, ry: 0.25, rz: 0.10, label: "Brain stem — Core" },
  limbic:     { cx:  0.00, cy:  0.00, cz: 0.00, rx: 0.28, ry: 0.20, rz: 0.28, label: "Limbic — Self / Human / Narrative" },
};

const CATEGORY_TO_REGION = {
  "core":                        "brainstem",
  "voice":                       "frontal",
  "principles":                  "frontal",
  "toolgroup:trading":           "motor",
  "toolgroup:safety":            "cerebellum",
  "toolgroup:system":            "motor",
  "toolgroup:identity":          "frontal",
  "toolgroup:web":               "motor",
  "toolgroup:introspection":     "limbic",
  "toolgroup:osint":             "motor",
  "toolgroup:finance":           "motor",
  "toolgroup:server_metrics":    "motor",
  "toolgroup:security":          "cerebellum",
  "toolgroup:browser":           "motor",
  "toolgroup:skills":            "broca",
  "toolgroup:diagrams":          "motor",
  "toolgroup:file_sync":         "motor",
  "toolgroup:chess":             "frontal",
  "toolgroup:file_transfer":     "motor",
  "toolgroup:image_gen":         "occipital",
  "toolgroup:qr":                "motor",
  "toolgroup:ascii":             "occipital",
  "toolgroup:vision":            "occipital",
  "toolgroup:register_check":    "limbic",
  "skills":                      "broca",
  "research":                    "temporal",
  "memory":                      "limbic",
  "threads":                     "frontal",
};

const REGION_COLOR = {
  frontal:    0xB2A4FF,
  motor:      0x7BDFA0,
  parietal:   0xA0B0A6,
  temporal:   0x9DC1B7,
  wernicke:   0xA0B0A6,
  occipital:  0x9D7BCF,
  broca:      0xE6B85C,
  cerebellum: 0xE57373,
  brainstem:  0xF4E4B5,
  limbic:     0xF4A23B,
};

// =================================================================
// PSEUDO-NOISE — cheap 3D noise for vertex displacement.
// Not real simplex; layered sin/cos that produces smooth bumps.
// =================================================================
function noise3d(x, y, z) {
  return (
    Math.sin(x * 1.3 + Math.cos(y * 0.7 + z * 0.4)) *
    Math.cos(z * 1.1 + Math.sin(x * 0.5 + y * 0.6)) * 0.55
    + Math.sin(x * 2.7 + y * 1.3) * Math.cos(z * 2.1 + y * 1.7) * 0.30
    + Math.sin(x * 5.3 + z * 3.1) * Math.cos(y * 4.7 + x * 2.3) * 0.15
  );
}

// =================================================================
// SCENE SETUP
// =================================================================
const viewport = document.getElementById("viewport");
const canvas   = document.getElementById("brain-canvas");

const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2(0x02030a, 0.06);

const camera = new THREE.PerspectiveCamera(45, 1, 0.05, 100);
camera.position.set(0.0, 0.4, 14.0);

const renderer = new THREE.WebGLRenderer({
  canvas, antialias: true, alpha: true,
  powerPreference: "high-performance",
});
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.setClearColor(0x000000, 0);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.1;

// Postprocessing — UnrealBloomPass gives the holographic glow.
const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(
  new THREE.Vector2(1, 1),
  0.30,   // strength (lower = less halo bleed)
  0.65,   // radius
  0.45,   // threshold (higher = only brighter pixels bloom)
);
composer.addPass(bloom);

// Controls
// Zoom configuration. Used by the wheel handler and the camera-driven
// node-expansion lerp. ZOOM_FAR/ZOOM_NEAR define the band over which
// expandT ramps 0->1. ZOOM_STEPS is the discrete distance ladder that
// each scroll click snaps to.
const ZOOM_FAR  = 14.0;
const ZOOM_NEAR = 1.0;
const ZOOM_STEPS = [22.0, 14.0, 9.0, 5.5, 3.5, 2.0, 1.0];
const ZOOM_DEFAULT_INDEX = 1;  // start at 14.0

const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.dampingFactor = 0.07;
controls.rotateSpeed = 0.7;
controls.enableZoom = false;  // we handle wheel manually for discrete steps
controls.minDistance = 0.5;
controls.maxDistance = 30;
controls.target.set(0, 0, 0);
controls.autoRotate = false;
controls.autoRotateSpeed = 0.45;

// Pause auto-rotate when the user is interacting.
let autoRotateOn = false;
let userInteracting = false;
controls.addEventListener("start", () => { userInteracting = true; });
controls.addEventListener("end",   () => { userInteracting = false; });

function resize() {
  const w = viewport.clientWidth;
  const h = viewport.clientHeight;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h, false);
  composer.setSize(w, h);
  bloom.setSize(w, h);
}
window.addEventListener("resize", resize);

// =================================================================
// BRAIN GEOMETRY — procedural cortex, cerebellum, stem, limbic.
// =================================================================
const brainGroup = new THREE.Group();
scene.add(brainGroup);

// ---- CORTEX (the big bumpy mass) ----
function buildCortex() {
  const geom = new THREE.IcosahedronGeometry(1.0, 7);  // ~5120 triangles
  const pos = geom.attributes.position;
  const v = new THREE.Vector3();
  for (let i = 0; i < pos.count; i++) {
    v.fromBufferAttribute(pos, i);

    // Layered noise displacement → gyri/sulci texture
    const n1 = noise3d(v.x * 2.2, v.y * 2.2, v.z * 2.2);
    const n2 = noise3d(v.x * 5.5, v.y * 5.5, v.z * 5.5);
    const n3 = noise3d(v.x * 11.0, v.y * 11.0, v.z * 11.0);
    const displacement = n1 * 0.08 + n2 * 0.035 + n3 * 0.018;
    v.multiplyScalar(1 + displacement);

    // Elongate anterior-posterior, slightly flatten top-bottom
    v.x *= 1.65;
    v.y *= 0.95;
    v.z *= 1.05;

    // Longitudinal fissure — deep dip along the top midline (z=0)
    const topness = Math.max(0, v.y - 0.25);
    const midness = Math.max(0, 1 - Math.abs(v.z) / 0.18);
    v.y -= topness * midness * 0.22;

    // Temporal lobe bulge — pull mid-low area slightly down/out
    if (v.y < -0.2 && v.y > -0.95 && Math.abs(v.x) < 1.4) {
      v.y -= 0.05;
    }

    // Carve out cerebellum area in back-bottom
    if (v.x < -1.0 && v.y < -0.4) {
      v.y += 0.18 * Math.max(0, (-1.0 - v.x));
    }

    pos.setXYZ(i, v.x, v.y, v.z);
  }
  pos.needsUpdate = true;
  geom.computeVertexNormals();

  // Two materials layered: wireframe overlay + faint solid underneath
  // for the holographic feel.
  const mat = new THREE.MeshBasicMaterial({
    color: 0xF4A23B,
    wireframe: true,
    transparent: true,
    opacity: 0.55,
  });
  const innerMat = new THREE.MeshBasicMaterial({
    color: 0xF4A23B,
    transparent: true,
    opacity: 0.03,
    side: THREE.BackSide,
    depthWrite: false,
  });

  const mesh = new THREE.Mesh(geom, mat);
  const inner = new THREE.Mesh(geom, innerMat);
  const g = new THREE.Group();
  g.add(inner);
  g.add(mesh);
  return g;
}

// ---- CEREBELLUM (cauliflower at back-bottom) ----
function buildCerebellum() {
  const geom = new THREE.IcosahedronGeometry(0.55, 5);
  const pos = geom.attributes.position;
  const v = new THREE.Vector3();
  for (let i = 0; i < pos.count; i++) {
    v.fromBufferAttribute(pos, i);
    // Higher frequency noise for the tighter parallel-fold pattern
    const n = noise3d(v.x * 8, v.y * 14, v.z * 8) * 0.08
            + noise3d(v.x * 18, v.y * 18, v.z * 18) * 0.025;
    v.multiplyScalar(1 + n);
    v.x *= 1.05;
    v.y *= 0.75;
    pos.setXYZ(i, v.x, v.y, v.z);
  }
  pos.needsUpdate = true;
  geom.computeVertexNormals();

  const mat = new THREE.MeshBasicMaterial({
    color: 0xE57373,
    wireframe: true,
    transparent: true,
    opacity: 0.55,
  });
  const mesh = new THREE.Mesh(geom, mat);
  mesh.position.set(-1.6, -0.65, 0);
  return mesh;
}

// ---- BRAIN STEM (tube hanging down) ----
function buildBrainstem() {
  const geom = new THREE.CylinderGeometry(0.18, 0.30, 1.1, 16, 6, false);
  const pos = geom.attributes.position;
  const v = new THREE.Vector3();
  for (let i = 0; i < pos.count; i++) {
    v.fromBufferAttribute(pos, i);
    const n = noise3d(v.x * 6, v.y * 4, v.z * 6) * 0.04;
    v.x *= 1 + n;
    v.z *= 1 + n;
    pos.setXYZ(i, v.x, v.y, v.z);
  }
  pos.needsUpdate = true;
  geom.computeVertexNormals();

  const mat = new THREE.MeshBasicMaterial({
    color: 0xF4E4B5,
    wireframe: true,
    transparent: true,
    opacity: 0.5,
  });
  const mesh = new THREE.Mesh(geom, mat);
  mesh.position.set(-0.25, -1.25, 0);
  mesh.rotation.x = 0.15;
  return mesh;
}

// ---- LIMBIC CORE (glowing sphere inside) ----
function buildLimbicCore() {
  const g = new THREE.Group();
  const inner = new THREE.Mesh(
    new THREE.SphereGeometry(0.18, 32, 32),
    new THREE.MeshBasicMaterial({
      color: 0xFFD27A,
      transparent: true,
      opacity: 0.28,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  const outer = new THREE.Mesh(
    new THREE.SphereGeometry(0.32, 32, 32),
    new THREE.MeshBasicMaterial({
      color: 0xF4A23B,
      transparent: true,
      opacity: 0.06,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  g.add(inner);
  g.add(outer);
  g.position.set(0.05, 0.05, 0);
  return g;
}

// Procedural fallbacks — shown while the .glb loads, and used
// permanently if the load fails.
const cortex      = buildCortex();
const cerebellum  = buildCerebellum();
const brainstem   = buildBrainstem();
const limbicCore  = buildLimbicCore();

brainGroup.add(cortex);
brainGroup.add(cerebellum);
brainGroup.add(brainstem);
brainGroup.add(limbicCore);

// ---- Real anatomical mesh (brain.glb by Oxterium, Sketchfab Standard) ----
// Swap in once it loads. Keep limbicCore as the inner glowing core.
let loadedBrain = null;
// Captured by GLB success callback; consumed by buildNodes if it runs
// AFTER the GLB has loaded. Handles either ordering of the two async loads.
let _envelopeScale = null;
const loader = new GLTFLoader();
loader.load(
  "assets/brain.glb",
  (gltf) => {
    const realBrain = gltf.scene;

    // Keep the original Sketchfab materials — the model was designed
    // with its own holographic look, and our amber override was killing
    // that. We do NOT traverse + replace materials anymore.

    // Align the model's anterior-posterior axis with our world X axis.
    // The Oxterium model has its long axis (3.30 units) on Z, but our
    // node region coordinates assume +X = anterior, -X = posterior.
    // Rotation.y = +PI/2 sends +Z -> +X, so the model's "front" becomes
    // our world "right" (typical anatomical-side-view convention).
    // If the brain ends up backwards on screen, flip the sign.
    realBrain.rotation.y = Math.PI / 2;
    realBrain.updateMatrixWorld(true);

    // Normalize scale + center: the Sketchfab model comes in arbitrary
    // units / off-center. Scale so longest axis = 3.3, then recenter.
    const box = new THREE.Box3().setFromObject(realBrain);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    const longest = Math.max(size.x, size.y, size.z);
    const scale = 3.3 / longest;
    realBrain.scale.setScalar(scale);
    realBrain.position.sub(center.multiplyScalar(scale));
    realBrain.updateMatrixWorld(true);

    // Swap: drop the procedural cortex/cerebellum/stem, add the real one.
    brainGroup.remove(cortex);
    brainGroup.remove(cerebellum);
    brainGroup.remove(brainstem);
    brainGroup.add(realBrain);
    loadedBrain = realBrain;

    // Reposition all existing nodes to match the real brain's envelope.
    // The procedural cortex was sized 3.3 x 1.9 x 2.1 (full extents).
    // The real brain has longest axis = 3.3 (normalized above), other
    // axes whatever the model has. Scale each node's position so they
    // stay inside the new envelope.
    const realSize = new THREE.Box3().setFromObject(realBrain).getSize(new THREE.Vector3());
    _envelopeScale = {
      sx: realSize.x / 3.3,
      sy: realSize.y / 1.9,
      sz: realSize.z / 2.1,
    };
    console.log("brain.glb envelope:", realSize, "node scale:", _envelopeScale);
    // Raycast each existing node against the loaded brain to pin to
    // the actual mesh surface in its anatomical zone.
    repinNodesToSurface();
  },
  undefined,
  (err) => {
    console.warn("Failed to load brain.glb, keeping procedural fallback.", err);
  },
);

// =================================================================
// NODES — one Mesh per node, positioned in its region's volume.
// =================================================================
const nodesGroup = new THREE.Group();
scene.add(nodesGroup);

// Particle background — sparse stars for the "lab atmosphere"
function buildStarfield() {
  const N = 220;
  const positions = new Float32Array(N * 3);
  for (let i = 0; i < N; i++) {
    const r = 8 + Math.random() * 12;
    const theta = Math.random() * Math.PI * 2;
    const phi   = Math.acos(2 * Math.random() - 1);
    positions[i*3]   = r * Math.sin(phi) * Math.cos(theta);
    positions[i*3+1] = r * Math.sin(phi) * Math.sin(theta) * 0.4;
    positions[i*3+2] = r * Math.cos(phi);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  const m = new THREE.PointsMaterial({
    color: 0x5BC0EB,
    size: 0.03,
    sizeAttenuation: true,
    transparent: true,
    opacity: 0.45,
  });
  return new THREE.Points(g, m);
}
scene.add(buildStarfield());

// =================================================================
// STATE
// =================================================================
let _allNodeMeshes = [];   // [{mesh, data, baseColor, baseScale}]
let _hovered = null;
let _selected = null;
let _data = null;
const tip = document.getElementById("tip");
const _diagEl = document.getElementById("diag");
let _diagFrame = 0;
const hint = document.getElementById("hint");

// Hide drag-hint after first interaction
let interactionCount = 0;
function fadeHint() {
  interactionCount += 1;
  if (interactionCount >= 2) hint.classList.add("dim");
}
canvas.addEventListener("pointerdown", fadeHint);
canvas.addEventListener("wheel", fadeHint, { passive: true });

// =================================================================
// DISCRETE ZOOM — each wheel click animates to the next step
// =================================================================
let _zoomIndex = ZOOM_DEFAULT_INDEX;
canvas.addEventListener("wheel", (e) => {
  e.preventDefault();
  // Scroll up (deltaY<0) = zoom in = higher index (closer distance)
  // Scroll down (deltaY>0) = zoom out = lower index (farther distance)
  const newIndex = e.deltaY > 0
    ? Math.max(0, _zoomIndex - 1)
    : Math.min(ZOOM_STEPS.length - 1, _zoomIndex + 1);
  if (newIndex === _zoomIndex) return;
  _zoomIndex = newIndex;
  const dist = ZOOM_STEPS[_zoomIndex];
  const dir = camera.position.clone().sub(controls.target).normalize();
  const newPos = controls.target.clone().add(dir.multiplyScalar(dist));
  animateToCamera(newPos, controls.target.clone(), 300);
}, { passive: false });

function animateToCamera(toPos, toTarget, duration) {
  const startPos = camera.position.clone();
  const startTarget = controls.target.clone();
  const t0 = performance.now();
  function step() {
    const t = Math.min(1, (performance.now() - t0) / duration);
    const eased = t * t * (3 - 2 * t);
    camera.position.lerpVectors(startPos, toPos, eased);
    controls.target.lerpVectors(startTarget, toTarget, eased);
    controls.update();
    if (t < 1) requestAnimationFrame(step);
  }
  step();
}

// =================================================================
// DATA LOAD
// =================================================================
fetch("brain.json", { cache: "no-cache" })
  .then(r => { if (!r.ok) throw new Error("missing"); return r.json(); })
  .then(render)
  .catch(() => { document.getElementById("empty").style.display = "grid"; });

function render(data) {
  _data = data;
  populatePortrait(data);
  populateStats(data);
  buildNodes(data);
  setupSearch();
  setupCloseButton();
  setupControls();
  setupRegionRail();
}

function populatePortrait(data) {
  const v = data.identity_version || "?";
  document.getElementById("version").textContent =
    `v${v} · ${(data.generated_at || "").replace("T"," ").slice(0,16)}`;
  document.getElementById("theo-version").textContent = `v${v}`;
  const name = data.name || "Theo";
  const voice = data.voice || "voice: not picked yet";
  document.getElementById("theo-name").textContent = name;
  document.getElementById("theo-voice").textContent = voice;
  document.getElementById("avatar").textContent = name.charAt(0).toUpperCase();
}

function populateStats(data) {
  const s = data.stats || {};
  const order = [
    ["tools",         "tools"],
    ["transcripts",   "sessions"],
    ["memory_chunks", "chunks"],
    ["idioms",        "idioms"],
    ["open_threads",  "open threads"],
    ["pinned",        "pinned"],
  ];
  const html = order
    .filter(([k]) => s[k] !== undefined)
    .map(([k, label]) => `
      <div class="stat-card">
        <b>${typeof s[k] === "number" ? s[k].toLocaleString() : s[k]}</b>
        <span>${label}</span>
      </div>`)
    .join("");
  document.getElementById("stats").innerHTML = html;
}

// ---- Build all node meshes ----
function buildNodes(data) {
  // Clear any existing
  while (nodesGroup.children.length) {
    const m = nodesGroup.children.pop();
    m.geometry?.dispose?.();
    m.material?.dispose?.();
  }
  _allNodeMeshes = [];

  // Shared geometry — one sphere reused across every node.
  const sphereGeom = new THREE.SphereGeometry(0.10, 14, 14);

  for (const cat of data.categories || []) {
    const regionId = CATEGORY_TO_REGION[cat.id] || "limbic";
    const region   = REGIONS[regionId];
    const colorHex = REGION_COLOR[regionId] || 0xE6B85C;
    if (!region) continue;
    for (const n of (cat.nodes || [])) {
      const mat = new THREE.MeshBasicMaterial({
        color: colorHex,
        transparent: true,
        opacity: 0.92,
      });
      const mesh = new THREE.Mesh(sphereGeom, mat);
      const { cluster, expand } = computeNodePositions(regionId, region);
      mesh.position.copy(cluster);
      mesh.userData = {
        data: n,
        region: regionId,
        categoryLabel: cat.label,
        baseColor: colorHex,
        baseScale: 1.0,
        clusterPos: cluster.clone(),
        expandPos:  expand.clone(),
        basePosition: cluster.clone(),
      };
      nodesGroup.add(mesh);
      _allNodeMeshes.push(mesh);
    }
  }
}

function randomPositionInRegion(r) {
  // Reject-sample within an ellipsoid for nicer distribution.
  let v;
  for (let i = 0; i < 10; i++) {
    const x = (Math.random() * 2 - 1);
    const y = (Math.random() * 2 - 1);
    const z = (Math.random() * 2 - 1);
    if (x*x + y*y + z*z <= 1) {
      v = new THREE.Vector3(
        r.cx + x * r.rx,
        r.cy + y * r.ry,
        r.cz + z * r.rz,
      );
      break;
    }
  }
  if (!v) v = new THREE.Vector3(r.cx, r.cy, r.cz);
  return v;
}

// Regions that live INSIDE the brain mass (deep structures). They
// get volumetric placement; cortical regions get surface placement.
const _INSIDE_REGIONS = new Set(["limbic", "brainstem"]);
const _surfaceRay = new THREE.Raycaster();

// Depth tuning for cortical nodes:
//   SHELL_DEEP    = how far out (as a fraction of the bounding
//                   ellipsoid radius) the CLUSTERED position sits.
//                   Lower = deeper inside the brain. Brains aren't
//                   perfect ellipsoids, so 0.5 sits inside the bulk.
//   SHELL_SURFACE = how far out the EXPANDED position sits. 1.0 puts
//                   nodes right on the envelope; >1.0 explodes past it.
const SHELL_DEEP    = 0.35;
const SHELL_SURFACE = 5.50;

// Angular spread (in tangent-plane units, ~radians for small values)
// around the region's center direction. CLUSTER_SPREAD is the cone
// half-angle at the default view -- small = tight packs. EXPAND_SPREAD
// is the cone half-angle at full zoom-in -- bigger = wider arc of
// nodes visibly fanning out across the brain surface.
const CLUSTER_SPREAD = 0.15;
const EXPAND_SPREAD  = 0.40;

// Node scale interpolation. Keep max modest so nodes don't visually
// overlap when spread out -- the drama comes from the angular spread,
// not from making each node huge.
const NODE_SCALE_MIN = 1.0;
const NODE_SCALE_MAX = 1.6;

// Zoom trigger range. The expansion ramps over EXACTLY this distance
// band -- shorter band = more dramatic per scroll click. We want it
// to start the moment the user zooms in past default (4.2) so the
// animation happens during the zoom-in, not lazily across the entire
// possible zoom range.

// Math helper: ray from origin in `dir` (unit vector) hits the
// brain's bounding ellipsoid at distance t. Solve (x/a)^2+(y/b)^2+(z/c)^2=1.
function ellipsoidT(dir) {
  const a = 3.3 / 2;
  const b = 1.9 * (_envelopeScale?.sy || 1) / 2;
  const c = 2.1 * (_envelopeScale?.sz || 1) / 2;
  const denom = (dir.x/a)**2 + (dir.y/b)**2 + (dir.z/c)**2;
  return 1 / Math.sqrt(Math.max(denom, 1e-9));
}

// Random unit vector perpendicular to `axis`. Used to spread nodes
// ANGULARLY around a region's center direction instead of adding
// jitter to coordinates (the old approach silently collapsed
// similar-jitter values into similar directions after normalize).
const _spreadHelper = new THREE.Vector3();
const _spreadPerp1  = new THREE.Vector3();
const _spreadPerp2  = new THREE.Vector3();
function randomPerpUnit(axis) {
  _spreadHelper.set(
    Math.abs(axis.x) < 0.9 ? 1 : 0,
    Math.abs(axis.x) < 0.9 ? 0 : 1,
    0,
  );
  _spreadPerp1.crossVectors(axis, _spreadHelper).normalize();
  _spreadPerp2.crossVectors(axis, _spreadPerp1).normalize();
  const theta = Math.random() * Math.PI * 2;
  return _spreadPerp1.clone().multiplyScalar(Math.cos(theta))
    .add(_spreadPerp2.clone().multiplyScalar(Math.sin(theta)));
}

// Surface-relative position: take the region's center direction,
// rotate by a random angle within a `spread`-sized cone, then walk
// out to `factor * envelope_radius` along that direction. Spread is
// ANGULAR (a tangent-plane offset magnitude), so identical spread
// values from different calls produce truly different directions --
// nodes actually fan out across the brain surface.
function surfacePosition(region, factor, spread) {
  const center = new THREE.Vector3(region.cx, region.cy, region.cz);
  if (_envelopeScale) {
    center.x *= _envelopeScale.sx;
    center.y *= _envelopeScale.sy;
    center.z *= _envelopeScale.sz;
  }
  if (center.lengthSq() < 0.0001) {
    // Region at origin — random unit dir as fallback
    const v = new THREE.Vector3(
      Math.random()-0.5, Math.random()-0.5, Math.random()-0.5,
    ).normalize();
    return v.multiplyScalar(ellipsoidT(v) * factor);
  }
  const baseDir = center.normalize();
  // Random offset in the tangent plane, magnitude up to `spread`
  const r = Math.sqrt(Math.random()) * spread;  // sqrt for uniform area
  const perp = randomPerpUnit(baseDir).multiplyScalar(r);
  const dir = baseDir.clone().add(perp).normalize();
  return dir.multiplyScalar(ellipsoidT(dir) * factor);
}

// For each node, compute BOTH a clustered position (deep inside the
// brain, tight to its region's anchor) and an expanded position
// (near the surface, spread wider across the region). In the animate
// loop we lerp between them based on camera zoom.
function computeNodePositions(regionId, region) {
  // Deep structures: cluster moderately tight, expand to OVERFILL
  // the region (matches the dramatic spread we use on cortical
  // regions so the effect feels consistent).
  if (_INSIDE_REGIONS.has(regionId) || !loadedBrain) {
    const tight = randomPositionInRegion({
      ...region,
      rx: region.rx * 0.40,
      ry: region.ry * 0.40,
      rz: region.rz * 0.40,
    });
    const full = randomPositionInRegion({
      ...region,
      rx: region.rx * 1.8,
      ry: region.ry * 1.8,
      rz: region.rz * 1.8,
    });
    if (_envelopeScale) {
      tight.x *= _envelopeScale.sx; tight.y *= _envelopeScale.sy; tight.z *= _envelopeScale.sz;
      full.x  *= _envelopeScale.sx; full.y  *= _envelopeScale.sy; full.z  *= _envelopeScale.sz;
    }
    return { cluster: tight, expand: full };
  }
  // Cortical regions: cluster deep, expand to surface (and slightly
  // past), with much wider jitter on expand for the dramatic
  // "Iron Man element discovery" explosion.
  return {
    cluster: surfacePosition(region, SHELL_DEEP,    CLUSTER_SPREAD),
    expand:  surfacePosition(region, SHELL_SURFACE, EXPAND_SPREAD),
  };
}

// Legacy entry point — buildNodes still calls placeNode; route it to
// computeNodePositions and return the cluster pos as the initial
// position (basePosition gets set from this).
function placeNode(regionId, region) {
  return computeNodePositions(regionId, region).cluster;
}

// Re-place every existing node — called by the GLB success callback
// once the loaded mesh is available for raycasting.
function repinNodesToSurface() {
  // Diagnostic: count how the GLB is structured so we know whether
  // raycasting works or we're relying on the ellipsoid fallback.
  let meshCount = 0, pointsCount = 0;
  loadedBrain.traverse(o => {
    if (o.isMesh) meshCount++;
    if (o.isPoints) pointsCount++;
  });
  console.log(`brain.glb children: ${meshCount} Mesh, ${pointsCount} Points`);

  for (const m of _allNodeMeshes) {
    const regionId = m.userData.region;
    const region = REGIONS[regionId];
    if (!region) continue;
    const { cluster, expand } = computeNodePositions(regionId, region);
    m.userData.clusterPos = cluster.clone();
    m.userData.expandPos  = expand.clone();
    m.position.copy(cluster);
  }
}

// =================================================================
// RAYCASTER — hover + click on nodes
// =================================================================
const raycaster = new THREE.Raycaster();
raycaster.params.Points = { threshold: 0.05 };
const pointer = new THREE.Vector2();

function pickAt(clientX, clientY) {
  const rect = canvas.getBoundingClientRect();
  pointer.x = ((clientX - rect.left) / rect.width)  * 2 - 1;
  pointer.y = -((clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const hits = raycaster.intersectObjects(_allNodeMeshes, false);
  return hits.length ? hits[0].object : null;
}

canvas.addEventListener("pointermove", e => {
  const hit = pickAt(e.clientX, e.clientY);
  if (hit !== _hovered) {
    if (_hovered) restoreNode(_hovered);
    _hovered = hit;
    if (_hovered) highlightNode(_hovered);
  }
  if (_hovered) {
    showTipFor(_hovered, e.clientX, e.clientY);
  } else {
    tip.classList.remove("show");
  }
});

canvas.addEventListener("click", e => {
  const hit = pickAt(e.clientX, e.clientY);
  if (hit) {
    selectNode(hit);
  }
});

function highlightNode(mesh) {
  // Scale is handled by the tick loop (rides on top of zoom scale).
  mesh.material.color.setHex(0xFFD27A);
}
function restoreNode(mesh) {
  if (mesh === _selected) return;
  mesh.material.color.setHex(mesh.userData.baseColor);
}

function showTipFor(mesh, clientX, clientY) {
  const d = mesh.userData;
  const region = REGIONS[d.region];
  tip.querySelector(".tip-label").textContent = d.data.label || d.data.id || "node";
  tip.querySelector(".tip-region").textContent = region ? region.label : "";
  const rect = viewport.getBoundingClientRect();
  tip.style.left = (clientX - rect.left) + "px";
  tip.style.top  = (clientY - rect.top)  + "px";
  tip.classList.add("show");
}

function selectNode(mesh) {
  if (_selected && _selected !== mesh) {
    // Force restore the old selection regardless of _selected guard
    const old = _selected;
    _selected = null;
    old.scale.setScalar(1.0);
    old.material.color.setHex(old.userData.baseColor);
  }
  _selected = mesh;
  mesh.scale.setScalar(2.2);
  mesh.material.color.setHex(0xE6B85C);
  renderDetail(mesh.userData);
  // Open mobile panel
  document.getElementById("panel").classList.add("open");
}

function renderDetail(d) {
  const n = d.data;
  const region = REGIONS[d.region];
  const detail = document.getElementById("detail-panel");
  detail.classList.remove("empty");
  let bodyHTML = "";
  if (n.body) {
    bodyHTML = `<pre>${escapeHtml(n.body)}</pre>`;
  } else if (n.summary) {
    bodyHTML = `<div class="body">${escapeHtml(n.summary)}</div>`;
  } else {
    bodyHTML = `<div class="body" style="color:var(--sage);font-style:italic">No body text — this is an index node.</div>`;
  }
  const meta = [];
  if (region) meta.push(region.label);
  if (d.categoryLabel) meta.push(d.categoryLabel);
  if (n.path) meta.push(n.path);
  detail.innerHTML = `
    <h3>Selection</h3>
    <div class="title">${escapeHtml(n.label || n.id)}</div>
    <div class="meta">${escapeHtml(meta.join("  ·  "))}</div>
    ${bodyHTML}
  `;
}

function escapeHtml(s) {
  return (s || "").toString()
    .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

// =================================================================
// SEARCH — filter visible nodes
// =================================================================
function setupSearch() {
  const input = document.getElementById("search");
  input.addEventListener("input", () => {
    const q = input.value.trim().toLowerCase();
    for (const m of _allNodeMeshes) {
      const d = m.userData.data;
      const text = `${d.id || ""} ${d.label || ""} ${d.body || ""} ${d.summary || ""}`.toLowerCase();
      const match = !q || text.includes(q);
      m.visible = match;
    }
  });
}

function setupCloseButton() {
  document.getElementById("close-panel").addEventListener("click", () => {
    document.getElementById("panel").classList.remove("open");
  });
}

// =================================================================
// CONTROLS — zoom buttons + auto-rotate toggle
// =================================================================
function setupControls() {
  document.getElementById("zoom-fit").addEventListener("click", () => {
    _zoomIndex = ZOOM_DEFAULT_INDEX;
    const dist = ZOOM_STEPS[_zoomIndex];
    animateToCamera(new THREE.Vector3(0, 0.4, dist), new THREE.Vector3(0,0,0), 300);
    clearRegionFocus();
  });
  document.getElementById("zoom-in").addEventListener("click", () => {
    if (_zoomIndex < ZOOM_STEPS.length - 1) {
      _zoomIndex++;
      const dist = ZOOM_STEPS[_zoomIndex];
      const dir = camera.position.clone().sub(controls.target).normalize();
      const newPos = controls.target.clone().add(dir.multiplyScalar(dist));
      animateToCamera(newPos, controls.target.clone(), 300);
    }
  });
  document.getElementById("zoom-out").addEventListener("click", () => {
    if (_zoomIndex > 0) {
      _zoomIndex--;
      const dist = ZOOM_STEPS[_zoomIndex];
      const dir = camera.position.clone().sub(controls.target).normalize();
      const newPos = controls.target.clone().add(dir.multiplyScalar(dist));
      animateToCamera(newPos, controls.target.clone(), 300);
    }
  });
  document.getElementById("auto-rotate").addEventListener("click", () => {
    autoRotateOn = !autoRotateOn;
    controls.autoRotate = autoRotateOn;
  });
}

// =================================================================
// REGION RAIL — Tron-style left-side selectors
// =================================================================
let _activeRegion = null;

function setupRegionRail() {
  const rail = document.getElementById("region-rail");
  // Order matters here — anatomical ordering top-to-bottom
  const order = [
    "frontal", "broca", "motor", "parietal",
    "wernicke", "temporal", "occipital",
    "limbic", "cerebellum", "brainstem",
  ];
  for (const id of order) {
    const r = REGIONS[id];
    const hex = "#" + REGION_COLOR[id].toString(16).padStart(6, "0");
    const btn = document.createElement("button");
    btn.className = "region-pick";
    btn.dataset.region = id;
    btn.style.setProperty("--region-color", hex);
    btn.textContent = r.label;
    btn.addEventListener("click", () => {
      if (_activeRegion === id) clearRegionFocus();
      else focusRegion(id);
    });
    rail.appendChild(btn);
  }
  const clear = document.createElement("button");
  clear.className = "rail-clear";
  clear.id = "rail-clear";
  clear.textContent = "Show all";
  clear.addEventListener("click", clearRegionFocus);
  rail.appendChild(clear);
}

// Glowing region indicator — single sphere we move around to mark the
// currently focused region on the brain. Initialized lazily.
let _focusIndicator = null;
function _ensureFocusIndicator() {
  if (_focusIndicator) return _focusIndicator;
  _focusIndicator = new THREE.Mesh(
    new THREE.SphereGeometry(0.55, 32, 32),
    new THREE.MeshBasicMaterial({
      color: 0xE6B85C,
      transparent: true,
      opacity: 0.0,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  scene.add(_focusIndicator);
  return _focusIndicator;
}

function focusRegion(id) {
  _activeRegion = id;

  // Camera target: the centroid of where this region's nodes will be
  // AT FULL EXPANSION. We're zooming in deep, so the nodes will be at
  // their expandPos (not their clusterPos / not the region anchor).
  // Aim at the actual node cloud, not the empty space it used to occupy.
  let cx = 0, cy = 0, cz = 0, count = 0;
  for (const m of _allNodeMeshes) {
    if (m.userData.region === id) {
      cx += m.userData.expandPos.x;
      cy += m.userData.expandPos.y;
      cz += m.userData.expandPos.z;
      count++;
    }
  }
  let target;
  if (count > 0) {
    target = new THREE.Vector3(cx / count, cy / count, cz / count);
  } else {
    // Fallback to the region anchor (envelope-scaled)
    const r = REGIONS[id];
    target = new THREE.Vector3(r.cx, r.cy, r.cz);
    if (_envelopeScale) {
      target.x *= _envelopeScale.sx;
      target.y *= _envelopeScale.sy;
      target.z *= _envelopeScale.sz;
    }
  }
  // Snap the zoom ladder to a deep step so subsequent scrolls behave.
  // ZOOM_STEPS = [22, 14, 9, 5.5, 3.5, 2, 1]; index 5 = distance 2.0.
  _zoomIndex = Math.max(0, ZOOM_STEPS.length - 2);
  animateCamera(target, ZOOM_STEPS[_zoomIndex]);

  // Highlight the region on the brain — glow sphere at the centroid.
  const indicator = _ensureFocusIndicator();
  indicator.position.copy(target);
  indicator.material.color.setHex(REGION_COLOR[id] || 0xE6B85C);
  indicator.material.opacity = 0.45;

  // Mark active button + show clear
  document.querySelectorAll(".region-pick").forEach(b => {
    b.classList.toggle("active", b.dataset.region === id);
  });
  document.getElementById("rail-clear").classList.add("show");

  // Dim other regions' nodes
  for (const m of _allNodeMeshes) {
    const matched = m.userData.region === id;
    m.material.opacity = matched ? 1.0 : 0.10;
  }

  // Populate the side panel with the list of nodes in this region.
  renderRegionList(id);
  // Make sure the panel is visible on narrow viewports (mobile media query
  // hides it by default — focusing a region should pop it open).
  document.getElementById("panel").classList.add("open");

  // Pause auto-rotate while focused
  controls.autoRotate = false;
}

function clearRegionFocus() {
  _activeRegion = null;
  _zoomIndex = ZOOM_DEFAULT_INDEX;
  animateCamera(new THREE.Vector3(0, 0, 0), ZOOM_STEPS[_zoomIndex]);
  document.querySelectorAll(".region-pick.active").forEach(b => b.classList.remove("active"));
  document.getElementById("rail-clear").classList.remove("show");
  for (const m of _allNodeMeshes) m.material.opacity = 0.92;
  if (_focusIndicator) _focusIndicator.material.opacity = 0.0;
  // Reset panel back to placeholder
  const detail = document.getElementById("detail-panel");
  detail.classList.add("empty");
  detail.innerHTML = `
    <h3>Selection</h3>
    <div class="placeholder">
      Drag to rotate. Scroll to zoom. Click a node to inspect.
      Each lobe carries a category — Frontal for voice and identity,
      Limbic for the self-model and the relationship, Motor cortex
      for tools, Cerebellum for drift detection.
    </div>
  `;
  controls.autoRotate = autoRotateOn;
}

// Side-panel content when a REGION (not a single node) is focused.
// Shows the list of nodes in that region; each one is clickable to
// drill into the individual node's body text.
function renderRegionList(id) {
  const r = REGIONS[id];
  const detail = document.getElementById("detail-panel");
  detail.classList.remove("empty");
  const colorHex = "#" + (REGION_COLOR[id] || 0xE6B85C).toString(16).padStart(6, "0");

  const nodesInRegion = _allNodeMeshes.filter(m => m.userData.region === id);
  if (nodesInRegion.length === 0) {
    detail.innerHTML = `
      <h3>Region · Nodes</h3>
      <div class="title" style="color:${colorHex}">${escapeHtml(r.label)}</div>
      <div class="body" style="color:var(--sage);font-style:italic">
        No nodes in this region yet.
      </div>
    `;
    return;
  }

  const items = nodesInRegion.map((m, idx) => {
    const d = m.userData.data;
    const label = d.label || d.id || "node";
    return `<li class="region-node-item" data-node-idx="${idx}">${escapeHtml(label)}</li>`;
  }).join("");

  detail.innerHTML = `
    <h3>Region · Nodes</h3>
    <div class="title" style="color:${colorHex}">${escapeHtml(r.label)}</div>
    <div class="meta">${nodesInRegion.length} ${nodesInRegion.length === 1 ? "node" : "nodes"}</div>
    <ul class="region-node-list">${items}</ul>
  `;

  detail.querySelectorAll(".region-node-item").forEach(li => {
    li.addEventListener("click", () => {
      const i = parseInt(li.dataset.nodeIdx, 10);
      const mesh = nodesInRegion[i];
      if (mesh) selectNode(mesh);
    });
  });
}

function animateCamera(targetPos, distance) {
  const startTarget = controls.target.clone();
  const startCam    = camera.position.clone();
  const dir = camera.position.clone().sub(controls.target).normalize();
  const newCam = targetPos.clone().add(dir.multiplyScalar(distance));
  const startTime = performance.now();
  const duration = 700;
  function step() {
    const t = Math.min(1, (performance.now() - startTime) / duration);
    const eased = t * t * (3 - 2 * t); // smoothstep
    controls.target.lerpVectors(startTarget, targetPos, eased);
    camera.position.lerpVectors(startCam, newCam, eased);
    controls.update();
    if (t < 1) requestAnimationFrame(step);
  }
  step();
}

// =================================================================
// ANIMATION LOOP
// =================================================================
const clock = new THREE.Clock();
function tick() {
  const dt = clock.getDelta();
  // Gentle pulse on limbic core
  const t = clock.elapsedTime;
  const pulse = 1 + Math.sin(t * 1.4) * 0.04;
  limbicCore.scale.setScalar(pulse);

  // Zoom-driven cluster <-> expand interpolation. As the camera
  // approaches the brain, nodes spread AND scale up -- the Iron Man
  // "element grows quickly and vastly" effect comes from both at
  // once. Linear lerp across the whole zoom range so transitions
  // feel continuous (not the "two modes" Ian reported in v3.11).
  const camDist = camera.position.distanceTo(controls.target);
  const expandT = THREE.MathUtils.clamp(
    (ZOOM_FAR - camDist) / (ZOOM_FAR - ZOOM_NEAR),
    0, 1,
  );
  // Diagnostic HUD — verifies expansion is wired (top-right corner)
  _diagFrame++;
  if (_diagFrame % 10 === 0 && _diagEl) {
    _diagEl.textContent =
      `dist ${camDist.toFixed(2)}  ·  expand ${(expandT*100).toFixed(0)}%`;
  }
  const nodeScale = NODE_SCALE_MIN + (NODE_SCALE_MAX - NODE_SCALE_MIN) * expandT;

  for (let i = 0; i < _allNodeMeshes.length; i++) {
    const m = _allNodeMeshes[i];
    const c = m.userData.clusterPos;
    const e = m.userData.expandPos;
    if (!c || !e) continue;

    // Position: hover/select stay put; everything else lerps and bobs
    if (m !== _hovered && m !== _selected) {
      m.position.lerpVectors(c, e, expandT);
      m.userData.basePosition.copy(m.position);
      if (!_activeRegion && !userInteracting) {
        const phase = i * 0.17;
        m.position.x += Math.sin(t * 0.6 + phase) * 0.006;
        m.position.y += Math.cos(t * 0.5 + phase) * 0.004;
      }
    }

    // Scale: every node tracks zoom scale, with a multiplier on
    // top for hover/select so they pop above siblings.
    let mult = 1.0;
    if (m === _selected) mult = 2.1;
    else if (m === _hovered) mult = 1.7;
    m.scale.setScalar(nodeScale * mult);
  }

  controls.update();
  composer.render();
  requestAnimationFrame(tick);
}

// Boot
resize();
tick();
