import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { STLLoader } from "three/addons/loaders/STLLoader.js";
import { api } from "./types";
import { layout as loadLayout, poseToWorld, toLocal, world, type Layout, type LocalPoint } from "./workspaceFrames";
type Props = {
  poses: any; // link poses in each robot's own URDF base frame (from /api/workbench/pose)
  layout?: Layout; // display placement of both bases (experimental display transform, not calibration)
  mode: string;
  camera: string;
  selected: string;
  onSelect: (s: string) => void;
  onJoint: (delta: number) => void;
  onTarget: (t: LocalPoint<"leader">) => void;
  scene?: SceneState;
  status?: string;
  help?: string;
  ghostLeader?: boolean; // leader parked and not part of what is shown (follower attempt replay): draw it faint
};
/** Task objects in STUDIO_DISPLAY_WORLD (metres). Convert scenario-frame points with workspaceFrames first. */
export type SceneState = {
  cube: number[]; // centre
  cubeSize: number;
  cubeColor: string;
  attached: boolean;
  target: { center: number[]; size: number[]; color: string };
  marker: number[]; // start position A (on the table)
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
    // Task scene in the display world (one table, one cube, one target). Visual objects only: no physics (Level 1).
    const table = new THREE.Mesh(new THREE.PlaneGeometry(1, 1),
      new THREE.MeshStandardMaterial({ color: "#1b2a3a", transparent: true, opacity: 0.55 }));
    const tableEdge = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.PlaneGeometry(1, 1)),
      new THREE.LineBasicMaterial({ color: "#3b5068" }));
    const label = (text: string, color: string) => {
      const canvas = document.createElement("canvas");
      canvas.width = canvas.height = 64;
      const g = canvas.getContext("2d")!;
      g.fillStyle = color;
      g.font = "bold 48px Inter, sans-serif";
      g.textAlign = "center";
      g.textBaseline = "middle";
      g.fillText(text, 32, 34);
      const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(canvas), depthTest: false }));
      sprite.scale.setScalar(0.05);
      sprite.renderOrder = 11;
      return sprite;
    };
    const labelA = label("A", "#fbbf24"),
      labelB = label("B", "#4ade80");
    const targetPad = new THREE.Mesh(new THREE.PlaneGeometry(1, 1),
      new THREE.MeshBasicMaterial({ color: "#22C55E", transparent: true, opacity: 0.35 }));
    const targetEdge = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.PlaneGeometry(1, 1)),
      new THREE.LineBasicMaterial({ color: "#4ade80" }));
    const markerRing = new THREE.Mesh(new THREE.RingGeometry(0.03, 0.036, 40),
      new THREE.MeshBasicMaterial({ color: "#F59E0B", side: THREE.DoubleSide }));
    const cubeMaterial = new THREE.MeshStandardMaterial({ color: "#F59E0B", roughness: 0.45, emissive: "#000000" });
    const cube = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), cubeMaterial);
    // These are visual task indicators, not contact or collision geometry.
    // Keep the 4 cm cube at its physical scale; make it legible with a ground halo.
    const cubeHalo = new THREE.Mesh(
      new THREE.RingGeometry(0.03, 0.038, 48),
      new THREE.MeshBasicMaterial({ color: "#fbbf24", side: THREE.DoubleSide, depthTest: false }),
    );
    cubeHalo.renderOrder = 10;
    const cubeEdges = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.BoxGeometry(1, 1, 1)),
      new THREE.LineBasicMaterial({ color: "#fff0b3" }),
    );
    cube.add(cubeEdges);
    const sceneGroup = new THREE.Group();
    sceneGroup.add(targetPad, targetEdge, markerRing, cubeHalo, cube, labelA, labelB);
    scene.add(table, tableEdge);
    sceneGroup.visible = false;
    scene.add(sceneGroup);
    const highlight = new THREE.MeshStandardMaterial({ color: "#5eead4", emissive: "#0d9488", emissiveIntensity: 0.9 });
    const ghost = new THREE.MeshStandardMaterial({ color: "#0D9488", transparent: true, opacity: 0.12, depthWrite: false });
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
      lastCamera = "",
      lastLayout = "";
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
        if (!sphere.visible || !ray.intersectObject(sphere).length) return;
        const normal = camera.getWorldDirection(new THREE.Vector3());
        plane.setFromNormalAndCoplanarPoint(normal, sphere.position);
        dragging = true;
        renderer.domElement.setPointerCapture(e.pointerId);
      } else {
        const hit = ray
          .intersectObjects([...objects.values()], true)
          .find((h) => h.object.parent?.visible && !(p.ghostLeader && h.object.userData.link?.startsWith("leader/")));
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
        // The drag plane lives in the display world; the leader IK takes leader-base coordinates.
        if (ray.ray.intersectPlane(plane, intersection))
          p.onTarget(toLocal(p.layout || loadLayout(), "leader", world([intersection.x, intersection.y, intersection.z])));
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
      const lay = p.layout || loadLayout();
      controls.enabled = p.mode === "orbit";
      if (p.camera !== lastCamera || lay.name !== lastLayout) {
        // Camera and table follow the layout: centre between the two bases, table from the layout file.
        const cx = (lay.bases.leader.xyz[0] + lay.bases.follower.xyz[0]) / 2;
        const positions: Record<string, number[]> = {
          perspective: [cx + 0.9, -1.8, 1.15],
          front: [cx, -2.8, 0.35],
          top: [cx, -0.001, 2.8],
          side: [cx + 2.8, 0, 0.35],
        };
        camera.position.fromArray(positions[p.camera] || positions.perspective);
        controls.target.set(cx, 0, 0.2);
        table.scale.set(lay.table.size_xy[0], lay.table.size_xy[1], 1);
        table.position.set(lay.table.center_xy[0], lay.table.center_xy[1], lay.table.top_z - 0.002);
        tableEdge.scale.copy(table.scale);
        tableEdge.position.copy(table.position);
        points[0].length = points[1].length = 0;
        lastCamera = p.camera;
        lastLayout = lay.name;
        controls.update();
      }
      for (const [name, group] of objects) {
        const role = name.startsWith("leader/") ? "leader" : "follower",
          pose = p.poses?.[role]?.[name.split("/")[1]];
        group.visible = !!pose;
        if (pose) {
          const w = poseToWorld(lay, role, pose);
          group.position.fromArray(w);
          group.quaternion.fromArray(w, 3);
        }
      }
      const ee = p.poses?.leader?.ee_gripper_link;
      if (ee) {
        sphere.position.fromArray(poseToWorld(lay, "leader", ee));
        sphere.visible = p.mode === "ee";
      }
      const sc = p.scene;
      sceneGroup.visible = !!sc;
      if (sc) {
        const top = lay.table.top_z;
        targetPad.scale.set(sc.target.size[0], sc.target.size[1], 1);
        targetEdge.scale.copy(targetPad.scale);
        targetPad.position.set(sc.target.center[0], sc.target.center[1], top + 0.004);
        targetEdge.position.copy(targetPad.position);
        markerRing.position.set(sc.marker[0], sc.marker[1], top + 0.006);
        labelA.position.set(sc.marker[0], sc.marker[1] - 0.065, top + 0.03);
        labelB.position.set(sc.target.center[0], sc.target.center[1] + sc.target.size[1] / 2 + 0.03, top + 0.03);
        cubeHalo.position.set(sc.cube[0], sc.cube[1], top + 0.008);
        cube.scale.setScalar(sc.cubeSize);
        cube.position.set(sc.cube[0], sc.cube[1], sc.cube[2]);
        cubeMaterial.emissive.set(sc.attached ? "#7c4a03" : "#5b3600");
      }
      for (const [name, group] of objects) {
        const isGhost = !!p.ghostLeader && name.startsWith("leader/");
        const isSelected = !isGhost && name === p.selected && name.startsWith("leader/") && p.mode !== "orbit";
        group.traverse((o) => {
          if (o instanceof THREE.Mesh) {
            o.userData.base ??= o.material;
            o.material = isGhost ? ghost : isSelected ? highlight : o.userData.base;
          }
        });
      }
      const selected = [...objects.entries()].find(([n]) => n === p.selected);
      axis.visible = !!selected;
      if (selected) {
        axis.position.copy(selected[1].position);
        axis.quaternion.copy(selected[1].quaternion);
      }
      if (p.poses && p.poses !== lastPose) {
        (["leader", "follower"] as const).forEach((role, i) => {
          const ee = p.poses[role]?.ee_gripper_link;
          if (ee) {
            const w = poseToWorld(lay, role, ee);
            points[i].push(new THREE.Vector3(w[0], w[1], w[2]));
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
      ghost.dispose();
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
        {props.help ||
          (props.mode === "orbit"
            ? "Drag to orbit · right-drag to pan · scroll to zoom"
            : props.mode === "joint"
              ? "Drag a leader link horizontally to turn its joint"
              : "Drag in the viewport to move the glowing end effector")}{" "}
        · {loaded} source meshes
      </div>
      <div className="wb-stage-status" role="status" aria-label="Stage state">
        {props.scene
          ? props.status || "TASK SCENE · amber cube = A · green square = B · visual objects only (no contact physics)"
          : "TASK SCENE NOT LOADED · cube and target unavailable (check the scenario API and the Studio error log)"}
      </div>
      {error && <div className="wb-error">{error}</div>}
    </div>
  );
}
