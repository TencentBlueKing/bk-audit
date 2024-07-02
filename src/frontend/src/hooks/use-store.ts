import { type Ref, ref } from 'vue';

import BlueKingConfigModel from '@model/root/blue-king-config';
import ConfigModel from '@model/root/config';

export interface Store {
  configs: Ref<ConfigModel>;
  blueKingConfig: Ref<BlueKingConfigModel>;
  updateConfigs: (data: ConfigModel) => void;
  updateBlueKingConfig: (data: BlueKingConfigModel) => void;
}

let storeInstance: Store | null;

const store = (): Store => {
  const configs = ref(new ConfigModel());
  const blueKingConfig = ref(new BlueKingConfigModel());

  function updateConfigs(data: ConfigModel) {
    configs.value = data;
  }

  function updateBlueKingConfig(data: BlueKingConfigModel) {
    blueKingConfig.value = data;
  }

  return {
    configs,
    blueKingConfig,
    updateConfigs,
    updateBlueKingConfig,
  };
};

export default function useStore() {
  if (!storeInstance) {
    storeInstance = store();
  }
  return storeInstance;
}
