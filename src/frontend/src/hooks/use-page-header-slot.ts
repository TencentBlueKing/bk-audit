import {
  computed,
  onActivated,
  onBeforeUnmount,
  onDeactivated,
  onMounted,
  ref,
} from 'vue';

const HEADER_SLOT_IDS = ['teleport-router-link', 'teleport-generate-report', 'teleport-nav-step'];

export const clearPageHeaderSlots = () => {
  HEADER_SLOT_IDS.forEach((id) => {
    document.getElementById(id)?.replaceChildren();
  });
};

let ownerSeed = 0;
const activeOwnerId = ref(0);

export default function usePageHeaderSlot() {
  ownerSeed += 1;
  const ownerId = ownerSeed;
  const isPageActive = ref(false);

  const claim = () => {
    clearPageHeaderSlots();
    activeOwnerId.value = ownerId;
  };

  const release = () => {
    if (activeOwnerId.value !== ownerId) {
      return;
    }
    activeOwnerId.value = 0;
    clearPageHeaderSlots();
  };

  const isActive = computed(() => isPageActive.value && activeOwnerId.value === ownerId);

  onMounted(() => {
    isPageActive.value = true;
    claim();
  });

  onActivated(() => {
    isPageActive.value = true;
    claim();
  });

  onDeactivated(() => {
    isPageActive.value = false;
    release();
  });

  onBeforeUnmount(() => {
    isPageActive.value = false;
    release();
  });

  return {
    isActive,
    isPageActive,
    claim,
    release,
  };
}
