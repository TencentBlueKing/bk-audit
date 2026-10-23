import { ref } from 'vue';

export interface PackageFilterOption {
  label: string;
  value: string;
}

export const packageFilterOptions = ref<PackageFilterOption[]>([]);
