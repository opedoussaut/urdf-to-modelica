import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { STLLoader } from "three/addons/loaders/STLLoader.js";
import { api } from "./types";
type Props = {
  poses: any;
  mode: string;
  camera: string;
  selected: string;
  onSelect: (s: string) => void;
  onJoint: (delta: number) => void;
  onTarget: (t: number[]) => void;
};
export default function RobotStage(props: Props) {
  const host = useRef<HTMLDivElement>(null),
    latest = useRef(props);
  latest.current = props;
  const [error, setError] = useState(""),
    [loaded, setLoaded] = useState(0);
  useEffect(() => {
    const element = host.current!;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true });
    } catch {
      setError(
        "WebGL unavailable. Joint controls and telemetry remain available.",
      );
      return;
    }
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.setClearColor("#111a24");
    element.appendChild(renderer.domElement);
    const scene = new THREE.Scene(),
      camera = new THREE.PerspectiveCamera(36, 1, 0.01, 30);
    camera.up.set(0, 0, 1);
    camera.position.set(1.15, -1.8, 1.15);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0.15, 0, 0.3);
    controls.enableDamping = true;
    controls.maxDistance = 6;
    controls.minDistance = 0.4;
    scene.add(new THREE.HemisphereLight(0xdceaff, 0x334155, 3));
    const light = new THREE.DirectionalLight(0xffffff, 4);
    light.position.set(1, -1, 3);
    scene.add(light);
    const grid = new THREE.GridHelper(5, 50, 0x3a4b61, 0x233245);
    grid.rotation.x = Math.PI / 2;
    grid.position.z = -0.005;
    scene.add(grid);
    const objects = new Map<string, THREE.Group>(),
      materials = [
        new THREE.MeshStandardMaterial({
          color: "#0D9488",
          metalness: 0.35,
          roughness: 0.4,
        }),
        new THREE.MeshStandardMaterial({
          color: "#2563EB",
          metalness: 0.35,
          roughness: 0.4,
        }),
      ];
    const sphere = new THREE.Mesh(
      new THREE.SphereGeometry(0.014, 20, 20),
      new THREE.MeshBasicMaterial({ color: "#70ffee" }),
    );
    scene.add(sphere);
    const axis = new THREE.AxesHelper(0.14);
    scene.add(axis);
    const trails = [
      new THREE.Line(
        new THREE.BufferGeometry(),
        new THREE.LineBasicMaterial({ color: "#0D9488" }),
      ),
      new THREE.Line(
        new THREE.BufferGeometry(),
        new THREE.LineBasicMaterial({ color: "#2563EB" }),
      ),
    ];
    trails.forEach((t) => scene.add(t));
    const points: THREE.Vector3[][] = [[], []];
    let disposed = false,
      frame = 0,
      count = 0,
      lastPose: any = null,
      lastCamera = "";
    const loader = new STLLoader();
    api<any[]>("/api/geometry")
      .then((items) =>
        items
          .filter(
            (i) =>
              i.link.startsWith("leader/") ||
              i.link.startsWith("follower_right/"),
          )
          .forEach((item) => {
            const group = new THREE.Group();
            group.userData.link = item.link;
            objects.set(item.link, group);
            scene.add(group);
            group.visible = false;
            loader.load(
              item.mesh,
              (geometry) => {
                if (disposed) {
                  geometry.dispose();
                  return;
                }
                const mesh = new THREE.Mesh(
                  geometry,
                  materials[item.link.startsWith("leader/") ? 0 : 1],
                );
                mesh.scale.fromArray(item.scale);
                mesh.position.fromArray(item.origin);
                const r = item.rotation;
                mesh.quaternion.setFromRotationMatrix(
                  new THREE.Matrix4().set(
                    r[0][0],
                    r[0][1],
                    r[0][2],
                    0,
                    r[1][0],
                    r[1][1],
                    r[1][2],
                    0,
                    r[2][0],
                    r[2][1],
                    r[2][2],
                    0,
                    0,
                    0,
                    0,
                    1,
                  ),
                );
                mesh.userData.link = item.link;
                group.add(mesh);
                setLoaded(++count);
              },
              undefined,
              () => !disposed && setError("A source mesh could not be loaded."),
            );
          }),
      )
      .catch((e) => setError(String(e)));
    const resize = new ResizeObserver(() => {
      if (!element.clientWidth || !element.clientHeight) return;
      renderer.setSize(element.clientWidth, element.clientHeight);
      camera.aspect = element.clientWidth / element.clientHeight;
      camera.updateProjectionMatrix();
    });
    resize.observe(element);
    const ray = new THREE.Raycaster(),
      pointer = new THREE.Vector2(),
      plane = new THREE.Plane(),
      intersection = new THREE.Vector3();
    let dragging = false,
      previousX = 0;
    const cast = (e: PointerEvent) => {
      const rect = element.getBoundingClientRect();
      pointer.set(
        ((e.clientX - rect.left) / rect.width) * 2 - 1,
        (-(e.clientY - rect.top) / rect.height) * 2 + 1,
      );
      ray.setFromCamera(pointer, camera);
    };
    const down = (e: PointerEvent) => {
      cast(e);
      const p = latest.current;
      if (p.mode === "ee") {
        const normal = camera.getWorldDirection(new THREE.Vector3());
        plane.setFromNormalAndCoplanarPoint(normal, sphere.position);
        dragging = true;
        renderer.domElement.setPointerCapture(e.pointerId);
      } else {
        const hit = ray
          .intersectObjects([...objects.values()], true)
          .find((h) => h.object.parent?.visible);
        if (hit) {
          p.onSelect(hit.object.userData.link);
          dragging =
            p.mode === "joint" &&
            hit.object.userData.link.startsWith("leader/");
          previousX = e.clientX;
          if (dragging) renderer.domElement.setPointerCapture(e.pointerId);
        }
      }
    };
    const move = (e: PointerEvent) => {
      if (!dragging) return;
      const p = latest.current;
      if (p.mode === "joint") {
        p.onJoint((e.clientX - previousX) * 0.008);
        previousX = e.clientX;
      } else if (p.mode === "ee") {
        cast(e);
        if (ray.ray.intersectPlane(plane, intersection))
          p.onTarget([intersection.x + 0.5, intersection.y, intersection.z]);
      }
    };
    const up = () => {
      dragging = false;
    };
    renderer.domElement.addEventListener("pointerdown", down);
    renderer.domElement.addEventListener("pointermove", move);
    renderer.domElement.addEventListener("pointerup", up);
    renderer.domElement.addEventListener("pointercancel", up);
    const animate = () => {
      if (!element.getClientRects().length) {
        frame = requestAnimationFrame(animate);
        return;
      }
      const p = latest.current;
      controls.enabled = p.mode === "orbit";
      if (p.camera !== lastCamera) {
        const positions: Record<string, number[]> = {
          perspective: [1.15, -1.8, 1.15],
          front: [0.15, -2.8, 0.35],
          top: [0.15, -0.001, 2.8],
          side: [2.8, 0, 0.35],
        };
        camera.position.fromArray(positions[p.camera] || positions.perspective);
        lastCamera = p.camera;
        controls.update();
      }
      for (const [name, group] of objects) {
        const leader = name.startsWith("leader/"),
          pose =
            p.poses?.[leader ? "leader" : "follower"]?.[name.split("/")[1]];
        group.visible = !!pose;
        if (pose) {
          group.position.fromArray(pose);
          group.position.x += leader ? -0.5 : 0.45;
          group.quaternion.fromArray(pose, 3);
        }
      }
      const ee = p.poses?.leader?.ee_gripper_link;
      if (ee) {
        sphere.position.set(ee[0] - 0.5, ee[1], ee[2]);
        sphere.visible = p.mode === "ee";
      }
      const selected = [...objects.entries()].find(([n]) => n === p.selected);
      axis.visible = !!selected;
      if (selected) {
        axis.position.copy(selected[1].position);
        axis.quaternion.copy(selected[1].quaternion);
      }
      if (p.poses && p.poses !== lastPose) {
        ["leader", "follower"].forEach((role, i) => {
          const ee = p.poses[role]?.ee_gripper_link;
          if (ee) {
            points[i].push(
              new THREE.Vector3(ee[0] + (i ? 0.45 : -0.5), ee[1], ee[2]),
            );
            if (points[i].length > 600) points[i].shift();
            trails[i].geometry.dispose();
            trails[i].geometry = new THREE.BufferGeometry().setFromPoints(
              points[i],
            );
          }
        });
        lastPose = p.poses;
      }
      controls.update();
      renderer.render(scene, camera);
      frame = requestAnimationFrame(animate);
    };
    animate();
    return () => {
      disposed = true;
      cancelAnimationFrame(frame);
      resize.disconnect();
      controls.dispose();
      renderer.domElement.removeEventListener("pointerdown", down);
      renderer.domElement.removeEventListener("pointermove", move);
      renderer.domElement.removeEventListener("pointerup", up);
      renderer.domElement.removeEventListener("pointercancel", up);
      scene.traverse((o) => {
        if (o instanceof THREE.Mesh || o instanceof THREE.Line) {
          o.geometry.dispose();
          if (!Array.isArray(o.material)) o.material.dispose();
        }
      });
      materials.forEach((m) => m.dispose());
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, []);
  return (
    <div
      className="wb-stage"
      ref={host}
      aria-label="Leader control and follower simulation, actual URDF meshes"
    >
      <div className="wb-role leader">
        LEADER · CONTROL <small>WidowX-250</small>
      </div>
      <div className="wb-role follower">
        FOLLOWER · SIMULATION <small>ViperX-300</small>
      </div>
      <div className="wb-stage-help">
        {props.mode === "orbit"
          ? "Drag to orbit · right-drag to pan · scroll to zoom"
          : props.mode === "joint"
            ? "Drag a leader link horizontally to turn its joint"
            : "Drag in the viewport to move the glowing end effector"}{" "}
        · {loaded} source meshes
      </div>
      {error && <div className="wb-error">{error}</div>}
    </div>
  );
}
