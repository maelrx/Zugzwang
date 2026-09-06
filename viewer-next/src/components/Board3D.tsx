import { useEffect, useRef } from "react";
import * as THREE from "three";

interface Props {
  fen: string | null;
  /** camera azimuth in degrees */
  orbitDeg?: number;
  height?: number;
}

const LIGHT = 0xe9d9bd;
const DARK = 0xa88967;
const WHITE_PIECE = 0xf5f3ee;
const BLACK_PIECE = 0x33383f;

const GLYPH: Record<string, string> = { k: "K", q: "Q", r: "R", b: "B", n: "N", p: "P" };
const PIECE_H: Record<string, number> = { k: 0.95, q: 0.85, r: 0.6, b: 0.7, n: 0.65, p: 0.45 };

function disposeGroup(group: THREE.Group): void {
  for (const child of [...group.children]) {
    child.traverse((obj) => {
      const mesh = obj as THREE.Mesh;
      if (mesh.geometry) mesh.geometry.dispose();
      const mat = mesh.material as THREE.Material | THREE.Material[] | undefined;
      if (Array.isArray(mat)) mat.forEach((m) => m.dispose());
      else if (mat) mat.dispose();
    });
    group.remove(child);
  }
}

/** Minimal 3D board: FEN → tiles + piece meshes, orbit camera, no controls lib.
 *
 * Scene/renderer are mounted once; only the piece group is rebuilt per FEN
 * (with geometry/material dispose). Rendering is on-demand — no rAF loop —
 * since a replay position is static.
 */
export function Board3D({ fen, orbitDeg = 35, height = 320 }: Props) {
  const mount = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const piecesRef = useRef<THREE.Group | null>(null);
  const texCache = useRef(new Map<string, THREE.Texture>());
  const renderRef = useRef<(() => void) | null>(null);

  // Mount once (renderer/scene/lights/tiles). Re-created only if height changes.
  useEffect(() => {
    const el = mount.current;
    if (!el) return;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    el.appendChild(renderer.domElement);

    scene.add(new THREE.AmbientLight(0xffffff, 1.1));
    const key = new THREE.DirectionalLight(0xffffff, 2.0);
    key.position.set(5, 9, 4);
    scene.add(key);

    for (let r = 0; r < 8; r++) {
      for (let f = 0; f < 8; f++) {
        const tile = new THREE.Mesh(
          new THREE.BoxGeometry(1, 0.12, 1),
          new THREE.MeshLambertMaterial({ color: (r + f) % 2 === 1 ? DARK : LIGHT }),
        );
        tile.position.set(f - 3.5, 0, 3.5 - r);
        scene.add(tile);
      }
    }

    const pieces = new THREE.Group();
    scene.add(pieces);

    sceneRef.current = scene;
    cameraRef.current = camera;
    rendererRef.current = renderer;
    piecesRef.current = pieces;

    const render = () => {
      const rad = (orbitDeg * Math.PI) / 180;
      const radius = 11.8;
      camera.position.set(Math.sin(rad) * radius, 8.8, Math.cos(rad) * radius);
      camera.lookAt(0, -0.4, 0);
      renderer.render(scene, camera);
    };
    renderRef.current = render;

    const resize = () => {
      const w = el.clientWidth || 320;
      renderer.setSize(w, height);
      camera.aspect = w / height;
      camera.updateProjectionMatrix();
      render();
    };
    resize();
    window.addEventListener("resize", resize);
    const texes = texCache.current;

    return () => {
      window.removeEventListener("resize", resize);
      disposeGroup(pieces);
      scene.traverse((obj) => {
        const mesh = obj as THREE.Mesh;
        if (mesh.geometry) mesh.geometry.dispose();
        const mat = mesh.material as THREE.Material | THREE.Material[] | undefined;
        if (Array.isArray(mat)) mat.forEach((m) => m.dispose());
        else if (mat) mat.dispose();
      });
      texes.forEach((t) => t.dispose());
      texes.clear();
      renderer.dispose();
      renderer.forceContextLoss();
      if (renderer.domElement.parentElement === el) el.removeChild(renderer.domElement);
      sceneRef.current = cameraRef.current = rendererRef.current = piecesRef.current = null;
      renderRef.current = null;
    };
    // orbitDeg is static in all callers; height changes are rare.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [height]);

  // Rebuild only the pieces when the position changes.
  useEffect(() => {
    const pieces = piecesRef.current;
    if (!pieces) return;
    disposeGroup(pieces);
    if (fen) {
      const rows = fen.split(" ")[0].split("/");
      for (let r = 0; r < 8; r++) {
        let f = 0;
        for (const ch of rows[r] ?? "") {
          if (/\d/.test(ch)) {
            f += +ch;
            continue;
          }
          const isWhite = ch === ch.toUpperCase();
          const color = isWhite ? WHITE_PIECE : BLACK_PIECE;
          const lower = ch.toLowerCase();
          const h = PIECE_H[lower] ?? 0.5;
          const g = new THREE.Group();

          const base = new THREE.Mesh(
            new THREE.CylinderGeometry(0.28, 0.34, 0.14, 24),
            new THREE.MeshLambertMaterial({ color }),
          );
          base.position.y = 0.19;
          g.add(base);
          const body = new THREE.Mesh(
            new THREE.CylinderGeometry(0.12, 0.22, h, 20),
            new THREE.MeshLambertMaterial({ color }),
          );
          body.position.y = 0.22 + h / 2;
          g.add(body);

          const tkey = (GLYPH[lower] ?? "?") + color;
          let tex = texCache.current.get(tkey);
          if (!tex) {
            const c = document.createElement("canvas");
            c.width = c.height = 96;
            const ctx = c.getContext("2d")!;
            ctx.fillStyle = "#" + (isWhite ? 0x1a1d22 : 0xe8e4da).toString(16).padStart(6, "0");
            ctx.font = "700 64px 'Geist Sans', sans-serif";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText(GLYPH[lower] ?? "?", 48, 52);
            tex = new THREE.CanvasTexture(c);
            texCache.current.set(tkey, tex);
          }
          const plane = new THREE.Mesh(
            new THREE.PlaneGeometry(0.5, 0.5),
            new THREE.MeshBasicMaterial({ map: tex, transparent: true }),
          );
          plane.position.set(0, 0.4 + h, 0);
          g.add(plane);

          g.position.set(f - 3.5, 0.06, 3.5 - r);
          pieces.add(g);
          f++;
        }
      }
    }
    renderRef.current?.();
  }, [fen]);

  return <div ref={mount} style={{ height }} className="w-full overflow-hidden rounded-md" data-testid="board3d" />;
}
