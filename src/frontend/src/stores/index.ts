import { defineStore } from 'pinia';
import { ref } from 'vue';

import BlueKingConfigModel from '@model/root/blue-king-config';
import ConfigModel from '@model/root/config';


export const useStore = defineStore('counter', () => {
  const configs = ref<ConfigModel>(new ConfigModel());
  const blueKingConfig = ref<BlueKingConfigModel>(new BlueKingConfigModel());

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
});
