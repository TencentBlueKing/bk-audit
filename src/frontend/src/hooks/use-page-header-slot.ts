import { computed, ref } from 'vue';

const HEADER_SLOT_IDS = ['teleport-router-link', 'teleport-generate-report'];

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

  const isActive = computed(() => activeOwnerId.value === ownerId);

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

  return {
    isActive,
    claim,
    release,
  };
}
