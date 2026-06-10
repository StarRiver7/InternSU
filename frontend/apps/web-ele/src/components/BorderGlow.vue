<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import type { Ref } from 'vue';

const props = withDefaults(
  defineProps<{
    glowColor?: string;
    backgroundColor?: string;
    borderRadius?: number;
    glowRadius?: number;
    glowIntensity?: number;
    coneSpread?: number;
    edgeSensitivity?: number;
    colors?: string[];
  }>(),
  {
    glowColor: '174 96 40',
    backgroundColor: '#f3f4f6',
    borderRadius: 24,
    glowRadius: 36,
    glowIntensity: 1.0,
    coneSpread: 20,
    edgeSensitivity: 25,
    colors: () => ['#14b8a6', '#5eead4', '#0d9488'],
  },
);

const cardRef = ref<HTMLElement | null>(null);
const isHovered = ref(false);
const cursorAngle = ref(45);
const edgeProximity = ref(0);

const colorSensitivity: Ref<number> = computed(() => props.edgeSensitivity + 20);
const isVisible = computed(() => isHovered.value);
const borderOpacity = computed(() =>
  isVisible.value
    ? Math.max(0, (edgeProximity.value * 100 - colorSensitivity.value) / (100 - colorSensitivity.value))
    : 0,
);
const glowOpacityVal = computed(() =>
  isVisible.value
    ? Math.max(0, (edgeProximity.value * 100 - props.edgeSensitivity) / (100 - props.edgeSensitivity))
    : 0,
);

const GRADIENT_POSITIONS = ['80% 55%', '69% 34%', '8% 6%', '41% 38%', '86% 85%', '82% 18%', '51% 4%'];
const COLOR_MAP = [0, 1, 2, 0, 1, 2, 1];

function buildMeshGradients(): string[] {
  const c = props.colors;
  const g: string[] = [];
  for (let i = 0; i < 7; i++) {
    g.push(`radial-gradient(at ${GRADIENT_POSITIONS[i]}, ${c[Math.min(COLOR_MAP[i], c.length - 1)]} 0px, transparent 50%)`);
  }
  g.push(`linear-gradient(${c[0]} 0 100%)`);
  return g;
}

const meshGradients = computed(() => buildMeshGradients());
const borderBg = computed(() => meshGradients.value.map((g) => `${g} border-box`));
const fillBg = computed(() => meshGradients.value.map((g) => `${g} padding-box`));
const angleDeg = computed(() => `${cursorAngle.value.toFixed(3)}deg`);

function getCenter(el: HTMLElement): [number, number] {
  const { width, height } = el.getBoundingClientRect();
  return [width / 2, height / 2];
}

function getEdgeProximity(el: HTMLElement, x: number, y: number): number {
  const [cx, cy] = getCenter(el);
  const dx = x - cx;
  const dy = y - cy;
  let kx = Infinity; let ky = Infinity;
  if (dx !== 0) kx = cx / Math.abs(dx);
  if (dy !== 0) ky = cy / Math.abs(dy);
  return Math.min(Math.max(1 / Math.min(kx, ky), 0), 1);
}

function getCursorAngle(el: HTMLElement, x: number, y: number): number {
  const [cx, cy] = getCenter(el);
  const dx = x - cx;
  const dy = y - cy;
  if (dx === 0 && dy === 0) return 0;
  const rad = Math.atan2(dy, dx);
  let deg = rad * (180 / Math.PI) + 90;
  if (deg < 0) deg += 360;
  return deg;
}

function onPointerMove(e: PointerEvent) {
  const card = cardRef.value;
  if (!card) return;
  const rect = card.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const y = e.clientY - rect.top;
  edgeProximity.value = getEdgeProximity(card, x, y);
  cursorAngle.value = getCursorAngle(card, x, y);
}

function onPointerEnter() { isHovered.value = true; }
function onPointerLeave() { isHovered.value = false; }

function buildBoxShadow(): string {
  const [h, s, l] = props.glowColor.split(' ').map(Number);
  const base = h + 'deg ' + s + '% ' + l + '%';
  const layers: number[][] = [
    [0,0,0,1,100], [0,0,1,0,60], [0,0,3,0,50], [0,0,6,0,40],
    [0,0,15,0,30], [0,0,25,2,20], [0,0,50,2,10],
  ];
  return layers.map(([x, y, blur, spread, alpha]) => {
    const a = Math.min(alpha * props.glowIntensity, 100);
    return x + 'px ' + y + 'px ' + blur + 'px ' + spread + 'px hsl(' + base + ' / ' + a + '%)';
  }).join(', ');
}

const boxShadowStr = computed(() => buildBoxShadow());
</script>

<template>
  <div
    ref="cardRef"
    class="relative grid isolate border border-white/15"
    :style="{
      background: props.backgroundColor,
      borderRadius: props.borderRadius + 'px',
      transform: 'translate3d(0, 0, 0.01px)',
    }"
    @pointermove="onPointerMove"
    @pointerenter="onPointerEnter"
    @pointerleave="onPointerLeave"
  >
    <!-- mesh gradient border -->
    <div
      class="absolute inset-0 rounded-[inherit] -z-[1]"
      :style="{
        border: '1px solid transparent',
        background: [
          'linear-gradient(' + props.backgroundColor + ' 0 100%) padding-box',
          'linear-gradient(rgb(255 255 255 / 0%) 0% 100%) border-box',
          ...borderBg,
        ].join(', '),
        opacity: borderOpacity,
        maskImage: 'conic-gradient(from ' + angleDeg + ' at center, black ' + props.coneSpread + '%, transparent ' + (props.coneSpread + 15) + '%, transparent ' + (100 - props.coneSpread - 15) + '%, black ' + (100 - props.coneSpread) + '%)',
        WebkitMaskImage: 'conic-gradient(from ' + angleDeg + ' at center, black ' + props.coneSpread + '%, transparent ' + (props.coneSpread + 15) + '%, transparent ' + (100 - props.coneSpread - 15) + '%, black ' + (100 - props.coneSpread) + '%)',
        transition: isVisible ? 'opacity 0.25s ease-out' : 'opacity 0.75s ease-in-out',
      }"
    />

    <!-- outer glow -->
    <span
      class="absolute pointer-events-none z-[1] rounded-[inherit]"
      :style="{
        inset: (-props.glowRadius) + 'px',
        maskImage: 'conic-gradient(from ' + angleDeg + ' at center, black 2.5%, transparent 10%, transparent 90%, black 97.5%)',
        WebkitMaskImage: 'conic-gradient(from ' + angleDeg + ' at center, black 2.5%, transparent 10%, transparent 90%, black 97.5%)',
        opacity: glowOpacityVal,
        mixBlendMode: 'plus-lighter',
        transition: isVisible ? 'opacity 0.25s ease-out' : 'opacity 0.75s ease-in-out',
      }"
    >
      <span
        class="absolute rounded-[inherit]"
        :style="{
          inset: props.glowRadius + 'px',
          boxShadow: boxShadowStr,
        }"
      />
    </span>

    <div class="relative z-[1] w-full">
      <slot />
    </div>
  </div>
</template>
