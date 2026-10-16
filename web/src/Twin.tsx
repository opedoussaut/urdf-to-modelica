import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { STLLoader } from "three/addons/loaders/STLLoader.js";
import { api, type Playback } from "./types";

interface Geometry {
  link: string;
  mesh: string;
  scale: number[];
  origin: number[];
  rotation: number[][];
}
export default function Twin({
  data,
  index,
  onSelect,
}: {
  data: Playback | null;
  index: number;
  onSelect: (name: string) => void;
}) {
  const host = useRef<HTMLDivElement>(null),
    objects = useRef(new Map<string, THREE.Group>());
  const latest = useRef({ data, index, onSelect });
  latest.current = { data, index, onSelect };
  const [error, setError] = useState(""),
    [loaded, setLoaded] = useState(0);
  useEffect(() => {
    const element = host.current;
    if (!element) return;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      setError(
        "3D rendering is unavailable in this browser. Recorded telemetry remains available.",
      );
      return;
    }
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.setClearColor(0x141b24, 1);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    element.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0x141b24, 4, 9);
    const camera = new THREE.PerspectiveCamera(36, 1, 0.01, 30);
    camera.up.set(0, 0, 1);
    camera.position.set(1.75, -2.5, 1.65);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 0, 0.27);
    controls.enableDamping = true;
    controls.minDistance = 0.5;
    controls.maxDistance = 5;
    controls.maxPolarAngle = Math.PI * 0.49;
    scene.add(new THREE.HemisphereLight(0xddeaff, 0x334455, 2.7));
    const key = new THREE.DirectionalLight(0xffffff, 3.8);
    key.position.set(2, -1, 4);
    scene.add(key);
    const rim = new THREE.DirectionalLight(0x4ccbd6, 2);
    rim.position.set(-2, 2, 1);
    scene.add(rim);
    const grid = new THREE.GridHelper(8, 80, 0x354859, 0x25303d);
    grid.rotation.x = Math.PI / 2;
    grid.position.z = -0.006;
    scene.add(grid);
    const lineMat = new THREE.LineBasicMaterial({
      color: 0x56d8cd,
      transparent: true,
      opacity: 0.65,
    });
    const paths = new THREE.Group();
    scene.add(paths);
    const localObjects = new Map<string, THREE.Group>();
    objects.current = localObjects;
    const material = new THREE.MeshStandardMaterial({
      color: 0xb7c2ce,
      metalness: 0.52,
      roughness: 0.38,
    });
    let disposed = false,
      frame = 0,
      count = 0;
    const loader = new STLLoader();
    api<Geometry[]>("/api/geometry")
      .then((items) => {
        for (const item of items) {
          const group = new THREE.Group();
          group.userData.link = item.link;
          localObjects.set(item.link, group);
          scene.add(group);
          group.visible = false;
          loader.load(
            item.mesh,
            (geometry) => {
              if (disposed) {
                geometry.dispose();
                return;
              }
              const mesh = new THREE.Mesh(geometry, material);
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
            () =>
              !disposed && setError("Some vendor meshes could not be loaded."),
          );
        }
      })
      .catch((e) => !disposed && setError(String(e)));
    let fitted = false;
    const resize = new ResizeObserver(() => {
      const w = element.clientWidth,
        h = element.clientHeight;
      renderer.setSize(w, h);
      camera.aspect = w / Math.max(h, 1);
      if (!fitted && w && h) {
        camera.position.multiplyScalar(Math.max(1, 1.4 / camera.aspect));
        fitted = true;
      }
      camera.updateProjectionMatrix();
    });
    resize.observe(element);
    const ray = new THREE.Raycaster(),
      pointer = new THREE.Vector2();
    let down = [0, 0];
    const pointerDown = (e: PointerEvent) => {
      down = [e.clientX, e.clientY];
    };
    const pick = (e: PointerEvent) => {
      if (Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 4) return;
      const rect = element.getBoundingClientRect();
      pointer.set(
        ((e.clientX - rect.left) / rect.width) * 2 - 1,
        (-(e.clientY - rect.top) / rect.height) * 2 + 1,
      );
      ray.setFromCamera(pointer, camera);
      const hit = ray
        .intersectObjects([...localObjects.values()], true)
        .find((h) => h.object.parent?.visible);
      if (hit) latest.current.onSelect(hit.object.userData.link);
    };
    renderer.domElement.addEventListener("pointerdown", pointerDown);
    renderer.domElement.addEventListener("pointerup", pick);
    let previous: Playback | null = null;
    const animate = () => {
      const { data, index } = latest.current;
      for (const [name, group] of localObjects) {
        const pose = data?.links[name]?.[index];
        group.visible = !!pose;
        if (pose) {
          group.position.fromArray(pose);
          group.quaternion.fromArray(pose, 3);
        }
      }
      if (data !== previous) {
        for (const child of [...paths.children]) {
          paths.remove(child);
          (child as THREE.Line).geometry.dispose();
        }
        if (data)
          for (const points of Object.values(data.end_effectors)) {
            const geometry = new THREE.BufferGeometry().setFromPoints(
              points.map(
                (p) => new THREE.Vector3(...(p as [number, number, number])),
              ),
            );
            paths.add(new THREE.Line(geometry, lineMat));
          }
        previous = data;
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
      renderer.domElement.removeEventListener("pointerdown", pointerDown);
      renderer.domElement.removeEventListener("pointerup", pick);
      scene.traverse((o) => {
        if (o instanceof THREE.Mesh || o instanceof THREE.Line)
          (o.geometry as THREE.BufferGeometry).dispose();
      });
      material.dispose();
      lineMat.dispose();
      renderer.dispose();
      renderer.domElement.remove();
      objects.current.clear();
    };
  }, []);
  return (
    <div
      className="twin"
      ref={host}
      aria-label="Interactive ALOHA 2 twin using recorded OpenModelica link poses"
    >
      <div className="viewport-label">
        <span className="live-dot" /> OPENMODELICA RECORDING{" "}
        <span>SI · metres</span>
      </div>
      <div className="viewport-help">
        Drag to orbit · Scroll to zoom · Click a component{" "}
        <span>{loaded} meshes</span>
      </div>
      {error && (
        <div className="viewport-error" role="alert">
          {error}
        </div>
      )}
      {!data && (
        <div className="viewport-empty">
          Select a verified run to load its recorded poses.
        </div>
      )}
    </div>
  );
}
