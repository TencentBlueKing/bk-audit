<!--
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
  Copyright (C) 2023 THL A29 Limited,
  a Tencent company. All rights reserved.
  Licensed under the MIT License (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at http://opensource.org/licenses/MIT
  Unless required by applicable law or agreed to in writing,
  software distributed under the License is distributed on
  an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
  either express or implied. See the License for the
  specific language governing permissions and limitations under the License.
  We undertake not to change the open source license (MIT license) applicable
  to the current version of the project delivered to anyone in the future.
-->
<template>
  <card-part-vue
    v-if="inputVariable.length > 0"
    :title="t('参数配置')"
    :title-description="t('设置仪表盘组件和变量的值，替代BKVision仪表盘的默认值')">
    <template #content>
      <div
        v-if="isUpdate && isEditMode"
        class="tips">
        <audit-icon
          class="info-fill"
          type="info-fill" />
        <span class="tips-text">{{ t('该仪表盘参数已更新，请同步工具参数以获取BKVision最新参数') }}</span>
        <span
          class="tips-bnt"
          @click="handleUpdateVariable">{{ t('立即更新') }}</span>
      </div>
      <!-- 交互组件 -->
      <bk-collapse
        v-model="activeIndex"
        class="bk-collapse-demo"
        header-icon="collapse-demo"
        :list="list">
        <template #title>
          <div
            class="collapse-title"
            @click="changeCom">
            <audit-icon
              class="full-screen-img"
              :class="{ 'rotated': isRotatedCom }"
              type="angle-fill-down" />
            <span class="title-text">{{ t('交互组件') }} </span>
            <audit-icon
              v-bk-tooltips="t('设置BKVision交互组件的默认值，用户打开图表后，可通过交互组件调整该值')"
              class="info-fill"
              type="info-fill" />
          </div>
        </template>
        <template #content>
          <div
            style="display: flex;width: 100%;flex-wrap: wrap;margin-top: -10px;">
            <bk-vision-components
              v-for="comItem in comList"
              :key="comItem.raw_name"
              :class="getClass(comItem)"
              :config="comItem"
              :disabled="isUpdateSubmit"
              :report-lists-panels="reportListsPanels"
              style="width: 22%;margin: 0 1.5%;margin-top: 10px;"
              @change="(val: any) => handleVisionChange(val, comItem.raw_name)"
              @change-is-default-value="(val: boolean) => handleIsDefaultValue(val, comItem.description)" />
          </div>
        </template>
      </bk-collapse>
      <!-- 变量 -->
      <bk-collapse
        v-if="toolInfoVariable.length > 0"
        v-model="variablesIndex"
        class="bk-collapse-demo"
        header-icon="collapse-demo"
        :list="list">
        <template #title>
          <div
            class="collapse-title"
            @click="changeVar">
            <audit-icon
              class="full-screen-img"
              :class="{ 'rotated': isRotatedVar }"
              type="angle-fill-down" />
            <span class="title-text">{{ t('变量') }} </span>
            <audit-icon
              v-bk-tooltips="t('设置BKVision变量的值，该值在图表打开后不可修改')"
              class="info-fill"
              type="info-fill" />
          </div>
        </template>
        <template #content>
          <div
            style="display: flex;width: 100%;flex-wrap: wrap;margin-top: -10px;">
            <div
              v-for="(variables, variableIndex) in toolInfoVariable"
              :key="variableIndex"
              :class="getClass(variables)"
              style="width: 22%;margin: 0 1.5%;margin-top: 10px;">
              <div class="variables-title">
                <span
                  v-bk-tooltips="{
                    disabled: variables.display_name === '',
                    content: variables.display_name
                  }"> {{ variables.raw_name }}</span>
                <bk-checkbox
                  v-model="variables.is_default_value"
                  class="title-right"
                  :disabled="isUpdateSubmit"
                  size="small"
                  @change="getVariablesDefaultValue(variables.is_default_value, variableIndex)">
                  {{ t('使用默认值') }}
                </bk-checkbox>
              </div>
              <div>
                <div
                  v-bk-tooltips="{
                    disabled: !isUpdateSubmit,
                    theme: 'light',
                    content: t('当前工具引用的 BKVision 参数有更新，请先完成 BKVision 参数的更新操作，再编辑参数')
                  }">
                  <bk-input
                    :disabled="variables.is_default_value || isUpdateSubmit"
                    :model-value="variables.default_value as string"
                    placeholder=" "
                    @update:model-value="(val: string) => variables.default_value = val" />
                </div>
              </div>
            </div>
          </div>
        </template>
      </bk-collapse>
    </template>
  </card-part-vue>
  <update-variable
    ref="updateVariableRef"
    @change-submit="handleUpdateSubmit" />
</template>
<script setup lang='tsx'>
  import { InfoBox } from 'bkui-vue';
  import { nextTick, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import CardPartVue from '../card-part.vue';

  import bkVisionComponents from './bk-vision-components.vue';
  import updateVariable from './variables-update.vue';

  type InputVariable = Array<{
    raw_name: string;
    display_name: string;
    description: string;
    required: boolean;
    field_category: string;
    default_value: string | Array<string>;
    is_default_value: boolean;
    raw_default_value?: string | Array<string>;
    choices: Array<{
      key: string,
      name: string
    }>
  }>

  interface Props {
    isEditMode: boolean;
    isUpdate: boolean;
    isFirstEdit: boolean;
    reportListsPanels: Array<Record<string, any>>;
  }

  interface Exposes {
    getValue: () => Promise<any>;
    setConfigs: (configs: InputVariable) => void;
    getFields: () => InputVariable;
    setVariablesConfig: (
      configs: Array<Record<string, any>>,
      bkVisionCom: Array<Record<string, any>>,
      bkVisionRes: any
    ) => void;
  }

  interface Emits {
    (event: 'changeSubmit', value: boolean): void;
    (event: 'changeIsUpdateSubmit', value: boolean): void;
  }

  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const { t } = useI18n();
  const activeIndex = ref(0);
  const variablesIndex = ref(0);
  const inputVariable = ref<InputVariable>([]);
  // aip 的组件信息
  const comList = ref<InputVariable>([]);
  const toolInfoVariable = ref<InputVariable>([]);
  // const variablesConfig = ref<Array<Record, any>>([]);
  const bkVisionVariable = ref<Array<Record<string, any>>>([]);
  // bkVision 的组件信息
  const bkVisionComList = ref<Array<Record<string, any>>>([]);
  const updateVariableRef = ref();
  const addClass = ref<string[]>([]);
  const updateClass = ref<string[]>([]);
  const list = ref([{
    title: t('交互组件'),
    content: '',
  }]);
  const variablesConfig = ref<Array<Record<string, any>>>([]);
  // 旋转状态
  const isRotatedVar = ref(false);
  const isRotatedCom = ref(false);
  const isUpdateSubmit = ref(false);
  // 更新变量
  const handleUpdateVariable = () => {
    if (updateVariableRef.value) {
      updateVariableRef.value?.show(
        toolInfoVariable.value,
        bkVisionVariable.value,
        comList.value,
        bkVisionComList.value,
      );
    }
  };

  // bk_vision 组件值改动
  const handleVisionChange = (value: any, rawName: string) => {
    inputVariable.value = inputVariable.value.map((item: any) => {
      const reItem = item;
      if (item.raw_name === rawName) {
        reItem.default_value = value;
      }
      return reItem;
    });
  };

  // bk_vision 组件是否使用默认值
  const handleIsDefaultValue = (value: any, description: string) => {
    if (!value) {
      return;
    }
    nextTick(() => {
      comList.value = comList.value.map((item: any) => {
        const reItem = item;
        if (item.description === description) {
          const findCom = bkVisionComList.value.find((item: any) => item.description === description);
          return {
            ...reItem,
            default_value: findCom?.default_value,
            is_default_value: value,
          };
        }
        return reItem;
      });
    });
  };
  // 获取变量默认值
  const getVariablesDefaultValue = (isDefault: boolean | undefined, index: number) => {
    if (isDefault) {
      InfoBox({
        title: t('提示'),
        closeIcon: false,
        content: t('当启用「使用默认值」选项后，若在 BKVision 嵌入管理页面中对变量值进行修改，当前工具会有参数更新提示'),
        onConfirm() {
          toolInfoVariable.value[index].default_value = toolInfoVariable.value[index].raw_default_value || '';
        },
        onCancel() {
        },
      });
    }
  };

  // 更新变量
  const updateArray = (updateArray: any[], infoObj: any) => {
    // 创建局部变量，避免直接修改函数参数
    let updated = [...updateArray];

    // 添加新项
    infoObj.addArrays.forEach((newItem: any) => {
      const exists = updated.some(item => item.raw_name === newItem.raw_name
        && item.description === newItem.description);

      if (!exists) {
        updated.push(newItem);
      }
    });

    // 更新项
    infoObj.updateArrays.forEach((itemToUpdate: any) => {
      const index = updated.findIndex(item => item.raw_name === itemToUpdate.raw_name
        && item.description === itemToUpdate.description);
      if (index !== -1) {
        updated[index] = { ...updated[index], ...itemToUpdate };
      }
    });

    // 删除项
    infoObj.delArrays.forEach((itemToDelete: any) => {
      updated = updated.filter(item => !(item.raw_name === itemToDelete.raw_name
        && item.description === itemToDelete.description));
    });
    // 删除每个数组项的 type 属性
    updated = updated.map((item: any) => {
      const { type, ...rest } = item;
      if (type === 'add') {
        addClass.value.push(`${item.raw_name}-${item.display_name}-${item.description}`);
      }
      if (type === 'update') {
        updateClass.value.push(`${item.raw_name}-${item.display_name}-${item.description}`);
      }
      return rest;
    });

    return updated;
  };


  // 侧边栏确认
  const handleUpdateSubmit = (value: any) => {
    const updateArrays = updateArray(comList.value.concat(toolInfoVariable.value), value);
    comList.value = updateArrays.filter((item: any) => item.field_category !== 'variable');
    toolInfoVariable.value = updateArrays.filter((item: any) => item.field_category === 'variable');
    isUpdateSubmit.value = false;
    emits('changeSubmit', false);

    emits('changeIsUpdateSubmit', isUpdateSubmit.value);
  };
  // class
  const getClass = (value: any) => {
    const name = `${value.raw_name}-${value.display_name}-${value.description}`;
    if (addClass.value.includes(name)) {
      return 'variables-item-add';
    }
    if (updateClass.value.includes(name)) {
      return 'variables-item-update';
    }
    return '';
  };

  const changeVar = () => {
    isRotatedVar.value = !isRotatedVar.value;
  };
  const changeCom = () => {
    isRotatedCom.value = !isRotatedCom.value;
  };

  defineExpose<Exposes>({
    getValue() {
      return Promise.resolve();
    },
    setConfigs(configs: InputVariable) {
      inputVariable.value = configs;
      // 工具信息api获取的变量
      toolInfoVariable.value = configs.filter((item: any) => item.field_category === 'variable');
      // 工具信息api获取的组件
      comList.value = configs.filter((item: any) => item.field_category !== 'variable');
    },
    getFields() {
      return comList.value.concat(toolInfoVariable.value);
    },
    setVariablesConfig(
      configs: Array<Record<string, any>>,
      bkVisionCom: Array<Record<string, any>>,
      bkVisionRes: any,
    ) {
      variablesConfig.value = configs;
      // 组件
      bkVisionComList.value = bkVisionCom;
      // bkVision变量
      bkVisionVariable.value = configs.map((item: any) => {
        if (item.build_in) {
          return undefined;
        }
        const matchedTool = toolInfoVariable.value.find((toolItem: any) => toolItem.raw_name === item.flag);
        const toolIsDefaultValue = matchedTool ? matchedTool.is_default_value : false;
        return {
          raw_name: item.flag || '',
          display_name: item.description || '',
          description: item.uid || '',
          field_category: item.type || '',
          required: true,
          is_default_value: toolIsDefaultValue,
          raw_default_value: bkVisionRes.constants[item.flag] || '',
          default_value: bkVisionRes.constants[item.flag] || '',
          choices: [],
        };
      }).filter((item: any): item is Record<string, any> => item !== undefined) as Array<Record<string, any>>;
    },
  });

  watch(
    () => props.isUpdate, (value) => {
      if (value && props.isEditMode && props.isFirstEdit) {
        nextTick(() => {
          isUpdateSubmit.value = true;
          handleUpdateVariable();
        });
      } else {
        isUpdateSubmit.value = false;
      }
    },
    { deep: true, immediate: true },
  );
</script>

<style lang="postcss" scoped>
.tips {
  top: 10px;
  right: 10px;
  display: flex;
  width: 98%;
  height: 30px;
  margin-left: 1%;
  font-size: 12px;
  background: #f0f5ff;
  border: 1px solid #a3c5fd;
  border-radius: 2px;
  align-items: center;

  .tips-text {
    margin-right: 5px;
    margin-left: 5px;
    font-size: 12px;
  }

  .tips-bnt {
    font-size: 12px;
    color: #3a84ff;
    cursor: pointer;
  }
}

.collapse-title {
  position: absolute;
  left: 10px;
  width: 100%;
}

.title-text {
  margin-left: 2px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  color: #4d4f56;
}

.info-fill {
  margin-left: 5px;
  font-size: 14px;
  color: #a3c5fd;
}

:deep(.bk-collapse-content) {
  padding: 0;
}

.variables-title {
  display: flex;
  justify-content: space-between;

  .title-right {
    color: #3a84ff;
    cursor: pointer
  }
}

.variables-item-add {
  padding: 5px;
  background-color: #ebfaf0;
}

.variables-item-update {
  padding: 5px;
  background-color: #fdf4e8;
}

.rotated {
  display: inline-block;
  transform: rotate(-90deg);
  transition: transform .2s ease;
}

</style>
