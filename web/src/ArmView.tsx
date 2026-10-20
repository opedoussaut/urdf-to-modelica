import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { STLLoader } from "three/addons/loaders/STLLoader.js";
import { api } from "./types";
import { request } from "./studio";
import { partOfJoint, partOfLink, type Part } from "./robotParts";

/**
 * The ALOHA follower arm, drawn from its real URDF meshes and forward-kinematics poses, as the studio's visual thread.
 * The focus joint's moving part is highlighted; the look follows the engineering step:
 *   robot (blue), knowledge (violet), model (blueprint wireframe), simulate (the joint swings), decide (amber).
 * Hover names each part in plain language; click selects it as the focus joint.
 */
export type ArmMode = "robot" | "knowledge" | "model" | "simulate" | "decide";

const ACCENT: Record<ArmMode, string> = {
  robot: "#3b82f6",
  knowledge: "#8b5cf6",
  model: "#38bdf8",
  simulate: "#14b8a6",
  decide: "#f59e0b",
};

export type ArmRobot = "aloha_vx300s" | "aloha_wx250s";
// Geometry prefix and /pose side for each arm (the follower shown is the right-hand ViperX).
const SIDE: Record<ArmRobot, { prefix: string; pose: "follower" | "leader" }> = {
  aloha_vx300s: { prefix: "follower_right/", pose: "follower" },
  aloha_wx250s: { prefix: "leader/", pose: "leader" },
};

let cache: Promise<{ geometry: any[]; config: any; home: any }> | null = null;
function loadBasics() {
  cache ??= Promise.all([api<any[]>("/api/geometry"), request("/configuration")]).then(async ([geometry, config]) => ({
    geometry,
    config,
    home: await request("/pose", "POST", { q: config.home }),
  }));
  return cache;
}
/** Link names (no prefix) that have a mesh on the given arm. */
export async function linksWithGeometry(robot: ArmRobot) {
  const { geometry } = await loadBasics();
  return new Set(geometry.filter((g) => g.link.startsWith(SIDE[robot].prefix)).map((g) => g.link.split("/")[1]));
}

export default function ArmView({
  focus,
  mode = "robot",
  theme = "light",
  height = 220,
  interactive = true,
  autoRotate = true,
  onSelect,
  onHover,
  robot = "aloha_vx300s",
  links,
  secondary,
  onPickLink,
}: {
  robot?: ArmRobot;
  /** Explicit highlight (link names without prefix); overrides the focus joint. */
  links?: string[];
  /** Lighter highlight, e.g. the parent link of a selected joint. */
  secondary?: string[];
  onPickLink?: (link: string) => void;
  focus?: string;
  mode?: ArmMode;
  theme?: "light" | "dark";
  height?: number;
  interactive?: boolean;
  autoRotate?: boolean;
  onSelect?: (joint: string) => void;
  onHover?: (part?: Part) => void;
}) {
  const host = useRef<HTMLDivElement>(null);
  const props = useRef({ focus, mode, onSelect, onHover, links, secondary, onPickLink });
  props.current = { focus, mode, onSelect, onHover, links, secondary, onPickLink };
  const [failed, setFailed] = useState("");
  const [hover, setHover] = useState<Part>();
  const [hoverLink, setHoverLink] = useState<string>();

  useEffect(() => {
    const el = host.current!;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      setFailed("3D view unavailable (WebGL)");
      return;
    }
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);
    el.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(32, 1, 0.01, 20);
    camera.up.set(0, 0, 1);
    scene.add(new THREE.HemisphereLight(0xffffff, theme === "dark" ? 0x1e293b : 0xcbd5e1, 2.6));
    const key = new THREE.DirectionalLight(0xffffff, 2.2);
    key.position.set(1.5, -1.2, 2.2);
    scene.add(key);
    const rim = new THREE.DirectionalLight(0x93c5fd, 1.1);
    rim.position.set(-1.5, 1.5, 1);
    scene.add(rim);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableZoom = false;
    controls.enablePan = false;
    controls.enabled = interactive;
    controls.autoRotate = autoRotate;
    controls.autoRotateSpeed = 0.9;
    controls.enableDamping = true;
    const base = new THREE.MeshStandardMaterial({ color: theme === "dark" ? 0x9fb3cc : 0x8b9bb0, metalness: 0.35, roughness: 0.45 });
    const focusMat = new THREE.MeshStandardMaterial({ color: 0x3b82f6, metalness: 0.2, roughness: 0.35, emissive: 0x1d4ed8, emissiveIntensity: 0.35 });
    const secondMat = new THREE.MeshStandardMaterial({ color: 0x93c5fd, metalness: 0.2, roughness: 0.4, emissive: 0x1d4ed8, emissiveIntensity: 0.08 });
    const hoverMat = new THREE.MeshStandardMaterial({ color: 0xffffff, metalness: 0.1, roughness: 0.4, emissive: 0x64748b, emissiveIntensity: 0.25 });
    const wire = new THREE.MeshBasicMaterial({ color: 0x7dd3fc, wireframe: true, transparent: true, opacity: 0.35 });
    const groups = new Map<string, THREE.Group>();
    const floor = new THREE.Mesh(
      new THREE.CircleGeometry(0.42, 64),
      new THREE.MeshBasicMaterial({ color: theme === "dark" ? 0x1e3a5f : 0xdbe4ef, transparent: true, opacity: theme === "dark" ? 0.55 : 0.7 }),
    );
    floor.position.z = -0.001;
    scene.add(floor);
    let disposed = false,
      frame = 0,
      poses: any = null,
      swing: any[] = [],
      swingJoint = "",
      hovered: string | undefined;
    const loader = new STLLoader();

    const place = (p: any) => {
      for (const [link, g] of groups) {
        const pose = p?.[link.split("/")[1]];
        g.visible = !!pose;
        if (pose) {
          g.position.fromArray(pose);
          g.quaternion.fromArray(pose, 3);
        }
      }
    };
    const frameCamera = () => {
      const box = new THREE.Box3();
      groups.forEach((g) => g.visible && box.expandByObject(g));
      if (box.isEmpty()) return;
      const c = box.getCenter(new THREE.Vector3()),
        s = box.getSize(new THREE.Vector3()).length();
      controls.target.copy(c);
      camera.position.set(c.x + s * 1.05, c.y - s * 1.35, c.z + s * 0.55);
      controls.update();
    };
    loadBasics()
      .then(({ geometry: all, home }) => {
        if (disposed) return;
        const geometry = all.filter((g) => g.link.startsWith(SIDE[robot].prefix));
        poses = home[SIDE[robot].pose];
        let pending = geometry.length;
        geometry.forEach((item) => {
          const group = new THREE.Group();
          group.userData.link = item.link;
          groups.set(item.link, group);
          scene.add(group);
          loader.load(
            item.mesh,
            (geo) => {
              if (disposed) return geo.dispose();
              const mesh = new THREE.Mesh(geo, base);
              mesh.scale.fromArray(item.scale);
              mesh.position.fromArray(item.origin);
              const r = item.rotation;
              mesh.quaternion.setFromRotationMatrix(
                new THREE.Matrix4().set(r[0][0], r[0][1], r[0][2], 0, r[1][0], r[1][1], r[1][2], 0, r[2][0], r[2][1], r[2][2], 0, 0, 0, 0, 1),
              );
              mesh.userData.link = item.link;
              group.add(mesh);
              const overlay = new THREE.Mesh(geo, wire);
              overlay.scale.copy(mesh.scale);
              overlay.position.copy(mesh.position);
              overlay.quaternion.copy(mesh.quaternion);
              overlay.userData.overlay = true;
              overlay.visible = false;
              group.add(overlay);
              if (--pending === 0) {
                place(poses);
                frameCamera();
              }
            },
            undefined,
            () => --pending,
          );
        });
        place(poses);
      })
      .catch((e) => !disposed && setFailed(String(e)));

    // Simulate mode: precompute a gentle swing of the focus joint through real forward kinematics (server poses).
    const prepareSwing = async (joint: string) => {
      swingJoint = joint;
      swing = [];
      const { config } = await loadBasics();
      const i = config.joint_ids.indexOf(joint);
      if (i < 0 || i > 5) return;
      const frames = await Promise.all(
        Array.from({ length: 16 }, (_, k) => {
          const q = [...config.home];
          q[i] += 0.32 * Math.sin((2 * Math.PI * k) / 16);
          return request("/pose", "POST", { q }).then((p) => p[SIDE[robot].pose]).catch(() => null);
        }),
      );
      if (swingJoint === joint) swing = frames.filter(Boolean);
    };

    const ray = new THREE.Raycaster(),
      ndc = new THREE.Vector2();
    const pick = (e: PointerEvent) => {
      const r = renderer.domElement.getBoundingClientRect();
      ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      ray.setFromCamera(ndc, camera);
      const hit = ray.intersectObjects([...groups.values()], true).find((h) => !h.object.userData.overlay);
      return hit?.object.userData.link as string | undefined;
    };
    let downAt = 0;
    const onMove = (e: PointerEvent) => {
      const link = pick(e);
      const part = partOfLink(link);
      const pickable = !!link && !!props.current.onPickLink;
      hovered = part || pickable ? link : undefined;
      renderer.domElement.style.cursor = (part && props.current.onSelect) || pickable ? "pointer" : "grab";
      setHover(part);
      setHoverLink(pickable ? link!.split("/")[1] : undefined);
      props.current.onHover?.(part);
    };
    const onLeave = () => {
      hovered = undefined;
      setHover(undefined);
      setHoverLink(undefined);
      props.current.onHover?.(undefined);
    };
    const onDown = () => (downAt = performance.now());
    const onUp = (e: PointerEvent) => {
      if (performance.now() - downAt > 250) return; // a drag, not a click
      const link = pick(e);
      if (link) props.current.onPickLink?.(link.split("/")[1]);
      const part = partOfLink(link);
      if (part) props.current.onSelect?.(part.joint);
    };
    if (interactive) {
      renderer.domElement.addEventListener("pointermove", onMove);
      renderer.domElement.addEventListener("pointerleave", onLeave);
      renderer.domElement.addEventListener("pointerdown", onDown);
      renderer.domElement.addEventListener("pointerup", onUp);
    }
    const resize = new ResizeObserver(() => {
      const w = el.clientWidth,
        h = el.clientHeight;
      if (!w || !h) return;
      renderer.setSize(w, h);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    });
    resize.observe(el);

    let lastLinks = "",
      lastFocus = "",
      lastMode = "",
      lastHover: string | undefined,
      t0 = performance.now();
    const animate = () => {
      frame = requestAnimationFrame(animate);
      if (!el.getClientRects().length) return;
      const { focus: f, mode: m } = props.current;
      const part = partOfJoint(f);
      if (m === "simulate" && f && f !== swingJoint) prepareSwing(f);
      if (m !== "simulate" && swing.length) {
        swing = [];
        swingJoint = "";
        place(poses);
      }
      if (m === "simulate" && swing.length) place(swing[Math.floor(((performance.now() - t0) / 90) % swing.length)]);
      const { links: L, secondary: S } = props.current;
      const linkKey = (L || []).join(",") + "|" + (S || []).join(",");
      if (f !== lastFocus || m !== lastMode || hovered !== lastHover || linkKey !== lastLinks) {
        focusMat.color.set(ACCENT[m]);
        focusMat.emissive.set(ACCENT[m]);
        for (const [link, g] of groups) {
          const name = link.split("/")[1];
          const isFocus = L
            ? L.includes(name)
            : !!part && (name === part.link || (part.joint === "left_finger" && ["left_finger_link", "right_finger_link"].includes(name)));
          const isSecond = !isFocus && !!S?.includes(name);
          const isHover = hovered === link && !isFocus;
          g.traverse((o) => {
            if (!(o instanceof THREE.Mesh)) return;
            if (o.userData.overlay) o.visible = m === "model";
            else o.material = isFocus ? focusMat : isHover ? hoverMat : isSecond ? secondMat : base;
          });
        }
        lastFocus = f || "";
        lastMode = m;
        lastHover = hovered;
        lastLinks = linkKey;
      }
      controls.update();
      renderer.render(scene, camera);
    };
    animate();
    return () => {
      disposed = true;
      cancelAnimationFrame(frame);
      resize.disconnect();
      controls.dispose();
      renderer.domElement.removeEventListener("pointermove", onMove);
      renderer.domElement.removeEventListener("pointerleave", onLeave);
      renderer.domElement.removeEventListener("pointerdown", onDown);
      renderer.domElement.removeEventListener("pointerup", onUp);
      scene.traverse((o) => o instanceof THREE.Mesh && o.geometry.dispose());
      [base, focusMat, hoverMat, secondMat, wire].forEach((m) => m.dispose());
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [theme, interactive, autoRotate, robot]);

  return (
    <div className={"arm-view " + theme} style={{ height }} ref={host}>
      {failed && <p className="arm-failed">{failed}</p>}
      {(hover || hoverLink) && (
        <div className="arm-tip">
          <b>{hover ? hover.name : hoverLink}</b>
          <span>{hoverLink ? `${hover ? hoverLink + " · " : ""}click to select it in the model` : hover!.plain}</span>
        </div>
      )}
    </div>
  );
}
