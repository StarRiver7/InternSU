<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import * as THREE from "three";

const props = withDefaults(
  defineProps<{
    class?: string;
    dotColor?: string;
    dotSize?: number;
    dotOpacity?: number;
    waveSpeed?: number;
    waveHeight?: number;
  }>(),
  {
    class: "",
    dotColor: "#1a1a1a",
    dotSize: 6,
    dotOpacity: 0.8,
    waveSpeed: 0.08,
    waveHeight: 40,
  },
);

const containerRef = ref<HTMLDivElement | null>(null);
let animationId = 0;

function hexToRgb(hex: string): [number, number, number] {
  const c = hex.replace("#", "");
  return [
    Number.parseInt(c.slice(0, 2), 16) / 255,
    Number.parseInt(c.slice(2, 4), 16) / 255,
    Number.parseInt(c.slice(4, 6), 16) / 255,
  ];
}

onMounted(() => {
  const container = containerRef.value;
  if (!container) return;

  // Scene
  const scene = new THREE.Scene();

  // Camera
  const camera = new THREE.PerspectiveCamera(
    75,
    window.innerWidth / window.innerHeight,
    1,
    5000,
  );
  camera.position.set(0, 355, 1220);
  camera.lookAt(0, 400, 0);

  // Renderer
  const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setClearColor(0x000000, 0);
  // Make canvas fill the container
  renderer.domElement.style.position = "absolute";
  renderer.domElement.style.top = "0";
  renderer.domElement.style.left = "0";
  renderer.domElement.style.width = "100%";
  renderer.domElement.style.height = "100%";
  container.appendChild(renderer.domElement);

  // Particles
  const SEPARATION = 100;
  const AMOUNTX = 50;
  const AMOUNTY = 40;
  const positions: number[] = [];
  const colors: number[] = [];
  const [r, g, b] = hexToRgb(props.dotColor);

  for (let ix = 0; ix < AMOUNTX; ix++) {
    for (let iy = 0; iy < AMOUNTY; iy++) {
      const x = ix * SEPARATION - (AMOUNTX * SEPARATION) / 2;
      const y = 0;
      const z = iy * SEPARATION - (AMOUNTY * SEPARATION) / 2;
      positions.push(x, y, z);
      colors.push(r, g, b);
    }
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));

  const material = new THREE.PointsMaterial({
    size: props.dotSize,
    vertexColors: true,
    transparent: true,
    opacity: props.dotOpacity,
    sizeAttenuation: true,
  });

  const points = new THREE.Points(geometry, material);
  scene.add(points);

  let count = 0;

  function animate() {
    animationId = requestAnimationFrame(animate);

    const posAttr = geometry.attributes.position;
    const pos = posAttr.array as Float32Array;

    let i = 0;
    for (let ix = 0; ix < AMOUNTX; ix++) {
      for (let iy = 0; iy < AMOUNTY; iy++) {
        pos[i * 3 + 1] =
          Math.sin((ix + count) * 0.3) * props.waveHeight +
          Math.sin((iy + count) * 0.5) * props.waveHeight;
        i++;
      }
    }
    posAttr.needsUpdate = true;

    renderer.render(scene, camera);
    count += props.waveSpeed;
  }

  animate();

  function onResize() {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  }

  window.addEventListener("resize", onResize);

  onUnmounted(() => {
    cancelAnimationFrame(animationId);
    window.removeEventListener("resize", onResize);
    geometry.dispose();
    material.dispose();
    renderer.dispose();
    if (container.contains(renderer.domElement)) {
      container.removeChild(renderer.domElement);
    }
  });
});
</script>

<template>
  <div
    ref="containerRef"
    :class="props.class"
    class="fixed inset-0 pointer-events-none"
    style="z-index: 0;"
  />
</template>
