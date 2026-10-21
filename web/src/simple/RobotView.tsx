import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";

/** 3D view of a robot, built from the same URDF that is converted: each joint is a frame placed by its URDF origin
 * (xyz, then roll-pitch-yaw), turning or sliding along its URDF axis; each part carries its URDF meshes.
 * Parts without a mesh (or uploaded URDFs, which come without meshes) are drawn as a skeleton of joints and bars. */

type Visual = { mesh: number | null; xyz: number[]; rpy: number[]; scale: number[]; rgba: number[] | null };
type Link = { mass: number | null; placeholder: boolean; com: number[] | null; visuals: Visual[] };
type Joint = {
  name: string;
  type: string;
  parent: string;
  child: string;
  xyz: number[];
  rpy: number[];
  axis: number[];
  lower: number | null;
  upper: number | null;
  mimic: { joint: string; multiplier: number; offset: number } | null;
};
export type Robot3D = { source: string; robot: string; root: string; links: Record<string, Link>; joints: Joint[]; meshes: number; mesh_bytes: number };
export type Hover = { link: string; mass: number | null; joint?: string; jointType?: string; shapeless?: boolean } | null;

const describeCache = new Map<string, Promise<Robot3D>>();
const geometryCache = new Map<string, Promise<THREE.BufferGeometry>>();
const loader = new STLLoader();

export function robot3d(source: string) {
  if (!describeCache.has(source))
    describeCache.set(
      source,
      fetch("/api/convert/robot3d?source=" + encodeURIComponent(source)).then((r) => {
        if (!r.ok) throw new Error("3D description unavailable");
        return r.json();
      }),
    );
  return describeCache.get(source)!;
}

function geometry(url: string) {
  if (!geometryCache.has(url)) geometryCache.set(url, loader.loadAsync(url));
  return geometryCache.get(url)!;
}

const euler = (rpy: number[]) => new THREE.Euler(rpy[0], rpy[1], rpy[2], "ZYX"); // URDF: R = Rz(yaw)·Ry(pitch)·Rx(roll)
const movable = (j: Joint) => j.type === "revolute" || j.type === "continuous" || j.type === "prismatic";

/** Joint values for the "move the joints" demo, with the scorer's standard excitation (kkh/convert/excite.py):
 * q = centre + A·sin(2π f t), A = 40 % of the URDF range, f = 0.25 + 0.05·k Hz for the k-th independent joint;
 * without limits ±1 rad / ±0.05 m. Mimic joints follow their master as the URDF says. */
function sweep(joints: Joint[], t: number): Record<string, number> {
  const q: Record<string, number> = {};
  let k = 0;
  for (const j of joints) {
    if (!movable(j) || j.mimic) continue;
    const limited = j.lower != null && j.upper != null && j.upper > j.lower && j.type !== "continuous";
    const centre = limited ? (j.lower! + j.upper!) / 2 : 0,
      amp = limited ? 0.4 * (j.upper! - j.lower!) : j.type === "prismatic" ? 0.05 : 1;
    q[j.name] = centre + amp * Math.sin(2 * Math.PI * (0.25 + 0.05 * k++) * t);
  }
  for (const j of joints) if (j.mimic && movable(j)) q[j.name] = j.mimic.multiplier * (q[j.mimic.joint] ?? 0) + j.mimic.offset;
  return q;
}

/** Rest pose: zero where zero is inside the limits, else the nearest limit (mimic joints follow their master). */
function rest(joints: Joint[]): Record<string, number> {
  const q: Record<string, number> = {};
  for (const j of joints) if (movable(j) && !j.mimic) q[j.name] = Math.min(Math.max(0, j.lower ?? 0), j.upper ?? 0);
  for (const j of joints) if (j.mimic && movable(j)) q[j.name] = j.mimic.multiplier * (q[j.mimic.joint] ?? 0) + j.mimic.offset;
  return q;
}

export default function RobotView({
  source,
  lod = "full",
  interactive = false,
  autoRotate = false,
  moving = false,
  showCom = false,
  speed = 0.25,
  height = 360,
  onHover,
  onInfo,
}: {
  source: string;
  lod?: "low" | "full";
  interactive?: boolean;
  autoRotate?: boolean;
  moving?: boolean;
  showCom?: boolean;
  speed?: number;
  height?: number;
  onHover?: (h: Hover) => void;
  onInfo?: (r: Robot3D, loaded: { meshes: number; total: number }) => void;
}) {
  const host = useRef<HTMLDivElement>(null);
  const movingRef = useRef(moving);
  movingRef.current = moving;
  const speedRef = useRef(speed);
  speedRef.current = speed;
  const showComRef = useRef(showCom);
  showComRef.current = showCom;
  const hoverRef = useRef(onHover);
  hoverRef.current = onHover;
  const infoRef = useRef(onInfo);
  infoRef.current = onInfo;
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    const el = host.current!;
    let disposed = false;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    el.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    scene.add(new THREE.HemisphereLight(0xffffff, 0x8a8f99, 2.2));
    const sun = new THREE.DirectionalLight(0xffffff, 1.6);
    sun.position.set(2, 4, 3);
    scene.add(sun);
    const camera = new THREE.PerspectiveCamera(35, 1, 0.005, 100);
    const world = new THREE.Group();
    world.rotation.x = -Math.PI / 2; // URDF is Z-up, three.js is Y-up
    scene.add(world);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enabled = interactive;
    controls.enableDamping = true;
    controls.autoRotate = autoRotate;
    controls.autoRotateSpeed = 1.2;

    const motion = new Map<string, { group: THREE.Group; joint: Joint }>();
    const pickable: THREE.Object3D[] = [];
    let joints: Joint[] = [];
    let raf = 0;
    let updateCom = () => {};

    const resize = () => {
      const w = el.clientWidth || 300;
      renderer.setSize(w, height);
      camera.aspect = w / height;
      camera.updateProjectionMatrix();
    };
    const ro = new ResizeObserver(resize);
    ro.observe(el);
    resize();

    const pose = (q: Record<string, number>) => {
      for (const { group, joint } of motion.values()) {
        const v = q[joint.name] ?? 0;
        const axis = new THREE.Vector3(...(joint.axis as [number, number, number])).normalize();
        if (joint.type === "prismatic") {
          group.position.copy(axis.multiplyScalar(v));
          group.quaternion.identity();
        } else {
          group.position.set(0, 0, 0);
          group.quaternion.setFromAxisAngle(axis, v);
        }
      }
    };

    const frame = () => {
      const box = new THREE.Box3().setFromObject(world);
      if (box.isEmpty()) return;
      const size = box.getSize(new THREE.Vector3()).length() || 1;
      const centre = box.getCenter(new THREE.Vector3());
      controls.target.copy(centre);
      camera.position.copy(centre).add(new THREE.Vector3(0.9, 0.45, 1.1).normalize().multiplyScalar(size * 1.35));
      camera.near = size / 200;
      camera.far = size * 20;
      camera.updateProjectionMatrix();
      controls.update();
    };

    robot3d(source)
      .then(async (r) => {
        if (disposed) return;
        joints = r.joints;
        const linkGroup = new Map<string, THREE.Group>();
        for (const name of Object.keys(r.links)) {
          const g = new THREE.Group();
          g.userData.link = name;
          linkGroup.set(name, g);
        }
        const parentJoint = new Map<string, Joint>();
        for (const j of r.joints) {
          const parent = linkGroup.get(j.parent),
            child = linkGroup.get(j.child);
          if (!parent || !child) continue;
          parentJoint.set(j.child, j);
          const origin = new THREE.Group();
          origin.position.set(j.xyz[0], j.xyz[1], j.xyz[2]);
          origin.setRotationFromEuler(euler(j.rpy));
          const mover = new THREE.Group();
          origin.add(mover);
          mover.add(child);
          parent.add(origin);
          if (movable(j)) motion.set(j.name, { group: mover, joint: j });
        }
        world.add(linkGroup.get(r.root) ?? new THREE.Group());

        // skeleton: a bar from each part's frame to each of its child joints, a dot at each joint. On a robot drawn with
        // its meshes, only parts without a shape (sensors, reference frames) get a small, muted dot.
        const reach = Math.max(0.05, ...r.joints.map((j) => Math.hypot(j.xyz[0], j.xyz[1], j.xyz[2])));
        const meshed = new Set(
          Object.entries(r.links)
            .filter(([, l]) => l.visuals.some((v) => v.mesh !== null))
            .map(([n]) => n),
        );
        const withMeshes = meshed.size > 0;
        const dot = new THREE.SphereGeometry(Math.max(0.003, reach * (withMeshes ? 0.012 : 0.06)), 12, 8);
        const skeletonMat = new THREE.MeshStandardMaterial({ color: withMeshes ? 0x94a3b8 : 0x2563eb, roughness: 0.6 });
        const barMat = new THREE.LineBasicMaterial({ color: 0x64748b });
        for (const j of r.joints) {
          const parent = linkGroup.get(j.parent);
          if (!parent || (meshed.has(j.parent) && meshed.has(j.child))) continue;
          const bar = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3(j.xyz[0], j.xyz[1], j.xyz[2])]);
          parent.add(new THREE.Line(bar, barMat));
          const d = new THREE.Mesh(dot, skeletonMat);
          d.userData.link = j.child;
          linkGroup.get(j.child)?.add(d);
          pickable.push(d);
        }

        const pending: Promise<void>[] = [];
        let loadedMeshes = 0;
        const total = Object.values(r.links).reduce((n, l) => n + l.visuals.filter((v) => v.mesh !== null).length, 0);
        for (const [name, link] of Object.entries(r.links)) {
          for (const v of link.visuals) {
            if (v.mesh === null) continue;
            const url = `/api/convert/mesh?source=${encodeURIComponent(source)}&i=${v.mesh}&lod=${lod}`;
            pending.push(
              geometry(url)
                .then((geo) => {
                  if (disposed) return;
                  const c = v.rgba ? new THREE.Color(v.rgba[0], v.rgba[1], v.rgba[2]) : new THREE.Color(0x9aa3ad);
                  // very dark URDF colours read as black blobs on screen: lift them slightly, keep the hue
                  const hsl = { h: 0, s: 0, l: 0 };
                  c.getHSL(hsl);
                  if (hsl.l < 0.28) c.setHSL(hsl.h, hsl.s, 0.28);
                  const m = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: c, roughness: 0.55, metalness: 0.1 }));
                  m.position.set(v.xyz[0], v.xyz[1], v.xyz[2]);
                  m.setRotationFromEuler(euler(v.rpy));
                  m.scale.set(v.scale[0], v.scale[1], v.scale[2]);
                  m.userData.link = name;
                  linkGroup.get(name)?.add(m);
                  pickable.push(m);
                  loadedMeshes++;
                })
                .catch(() => {}),
            );
          }
        }
        // whole-robot centre of mass: mass-weighted mean of each part's URDF centre of mass, placed with the current pose
        const massive = Object.entries(r.links).filter(([, l]) => l.mass && l.com) as [string, Link & { mass: number; com: number[] }][];
        const totalMass = massive.reduce((m, [, l]) => m + l.mass, 0);
        if (totalMass > 0) {
          const size = Math.max(0.01, reach * 0.05);
          const marker = new THREE.Group();
          const ball = new THREE.Mesh(
            new THREE.SphereGeometry(size, 24, 16),
            new THREE.MeshBasicMaterial({ color: 0xea580c, depthTest: false, transparent: true, opacity: 0.95 }),
          );
          const plumb = new THREE.Line(
            new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
            new THREE.LineDashedMaterial({ color: 0xea580c, dashSize: size, gapSize: size * 0.6, depthTest: false }),
          );
          ball.renderOrder = plumb.renderOrder = 10;
          marker.add(ball);
          scene.add(marker, plumb);
          const p = new THREE.Vector3(),
            acc = new THREE.Vector3();
          updateCom = () => {
            marker.visible = plumb.visible = showComRef.current;
            if (!showComRef.current) return;
            world.updateMatrixWorld(true);
            acc.set(0, 0, 0);
            for (const [name, l] of massive) {
              const g = linkGroup.get(name);
              if (!g) continue;
              acc.addScaledVector(g.localToWorld(p.set(l.com[0], l.com[1], l.com[2])), l.mass);
            }
            acc.divideScalar(totalMass);
            marker.position.copy(acc);
            // dashed plumb line down to the lowest point of the robot: shows whether the centre of mass is over the feet
            const floor = new THREE.Box3().setFromObject(world).min.y;
            plumb.geometry.setFromPoints([acc.clone(), new THREE.Vector3(acc.x, floor, acc.z)]);
            plumb.computeLineDistances();
          };
        }
        pose(rest(joints));
        frame();
        setState("ready");
        await Promise.all(pending);
        if (disposed) return;
        pose(rest(joints));
        frame();
        infoRef.current?.(r, { meshes: loadedMeshes, total });

        // hover: name, mass and joint of the part under the pointer
        if (interactive) {
          const ray = new THREE.Raycaster(),
            ptr = new THREE.Vector2();
          let last = "";
          renderer.domElement.addEventListener("pointermove", (e) => {
            const b = renderer.domElement.getBoundingClientRect();
            ptr.set(((e.clientX - b.left) / b.width) * 2 - 1, -((e.clientY - b.top) / b.height) * 2 + 1);
            ray.setFromCamera(ptr, camera);
            const hit = ray.intersectObjects(pickable, false)[0];
            const link = hit?.object.userData.link ?? "";
            if (link === last) return;
            last = link;
            const pj = parentJoint.get(link);
            hoverRef.current?.(
              link ? { link, mass: r.links[link]?.mass ?? null, joint: pj?.name, jointType: pj?.type, shapeless: withMeshes && !meshed.has(link) } : null,
            );
          });
          renderer.domElement.addEventListener("pointerleave", () => {
            last = "";
            hoverRef.current?.(null);
          });
        }
      })
      .catch(() => !disposed && setState("error"));

    // test time advances at the chosen speed (1 = the real excitation, where the 43-joint G1 reaches ~2.4 Hz)
    let last = performance.now(),
      testTime = 0;
    let wasMoving = false;
    const loop = () => {
      raf = requestAnimationFrame(loop);
      const nowMs = performance.now();
      if (movingRef.current) testTime += ((nowMs - last) / 1000) * speedRef.current;
      last = nowMs;
      if (movingRef.current) pose(sweep(joints, testTime));
      else if (wasMoving) pose(rest(joints));
      wasMoving = movingRef.current;
      updateCom();
      controls.update();
      renderer.render(scene, camera);
    };
    loop();

    return () => {
      disposed = true;
      cancelAnimationFrame(raf);
      ro.disconnect();
      controls.dispose();
      scene.traverse((o) => {
        const m = (o as THREE.Mesh).material as THREE.Material | undefined;
        m?.dispose?.();
      });
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [source, lod, interactive, autoRotate, height]);

  return (
    <div className="sx-robot3d" ref={host} style={{ height }}>
      {state === "loading" && <span className="sx-robot3d-note">Loading the 3D model…</span>}
      {state === "error" && <span className="sx-robot3d-note">3D view unavailable for this robot</span>}
    </div>
  );
}
