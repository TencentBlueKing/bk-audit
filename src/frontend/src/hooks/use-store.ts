import { type Ref, ref } from 'vue';

import BlueKingConfigModel from '@model/root/blue-king-config';

export interface Store {
  blueKingConfig: Ref<BlueKingConfigModel>;
}

let storeInstance: Store | null;

const store = (): Store => {
  const blueKingConfig = ref(new BlueKingConfigModel());

  return {
    blueKingConfig,
  };
};

export default function useStore() {
  if (!storeInstance) {
    storeInstance = store();
  }
  return storeInstance;
}
