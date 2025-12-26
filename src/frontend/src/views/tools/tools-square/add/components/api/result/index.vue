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
  <card-part-vue :title="t('查询结果设置')">
    <template #content>
      <div class="group-box">
        <span>{{ t('是否分组') }}</span>
        <bk-switcher
          v-model="outputConfigEnableGrouping.enable_grouping"
          :before-change="handleEnableGrouping"
          class="group"
          theme="primary" />
        <span v-if="!outputConfigEnableGrouping.enable_grouping">
          <audit-icon
            class="info-fill"
            type="info-fill" />
          <span class="info-fill-tex">{{ t('开启后，查询结果将按字段分组展示') }}</span>
        </span>
        <span v-else>
          <span
            class="group-button"
            @click="handleAddGroup">
            <audit-icon
              class="plus-circle"
              type="plus-circle" />
            <span class="plus-circle-tex">{{ t('添加分组') }}</span>
          </span>
          <span class="line" />
          <span>
            <span
              class="plus-circle-tex"
              @click="handleOpenGroup">{{ t(openGroup ? '一键展开分组' : '一键收起分组') }}</span>
          </span>
        </span>
      </div>
      <content
        v-if="!isGrouping"
        ref="contentRef"
        :is-edit-mode="isEditMode"
        :is-grouping="outputConfigEnableGrouping.enable_grouping"
        :result-data="resultData" />
      <group-content
        v-else
        ref="groupContentRef"
        :is-edit-mode="isEditMode"
        :is-grouping="outputConfigEnableGrouping.enable_grouping"
        :result-data="resultData" />
    </template>
  </card-part-vue>
</template>
<script setup lang='tsx'>
  import { InfoBox } from 'bkui-vue';
  import { nextTick, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  import resultDataModel from '@model/tool/api';

  import CardPartVue from '../../card-part.vue';

  import content from './content.vue';
  import groupContent from './group-content.vue';


  interface Props {
    isEditMode: boolean,
    resultData: Array<resultDataModel> | string,
  }
  interface Exposes {
    handleGetResultConfig: () => void;
    setConfigs: (data: any) => void;
  }

  defineProps<Props>();
  const contentRef = ref();
  const { t } = useI18n();
  const groupContentRef = ref();
  const openGroup = ref(false);
  const outputConfigEnableGrouping = ref({
    enable_grouping: false,
  });
  const isGrouping  = ref(false);
  const handleEnableGrouping = (lastValue: boolean) => new Promise<boolean>((resolve, reject) => {
    if (lastValue) {
      isGrouping.value = true;
      // 开启分组
      const contentRefData  = contentRef.value?.handleGetResultConfig(); // 分组前的配置信息
      resolve(true);
      nextTick(() => {
        const setConfigsData = [
          {
            name: '分组1',
            output_fields: contentRefData,
          },
        ];
        groupContentRef.value?.setConfigs(setConfigsData);
      });
    } else {
      const groupContentRefData =  groupContentRef.value?.handleGetResultConfig(); // 分组后的配置信息

      if (groupContentRefData.length > 1) {
        InfoBox({
          title: t('当前存在多个分组，请先合并至一个分组后再关闭'),
          contentAlign: 'left',
          content: '',
          cancelText: t('取消'),
          confirmText: t('确定'),
          onConfirm() {
            outputConfigEnableGrouping.value.enable_grouping = true;
            isGrouping.value = true;
            reject(true);
          },
          onCancel() {
            outputConfigEnableGrouping.value.enable_grouping = true;
            isGrouping.value = true;
            reject(true);
          },
        });
        return;
      }
      resolve(false);
      isGrouping.value = false;
      outputConfigEnableGrouping.value.enable_grouping = false;
      nextTick(() => {
        contentRef.value?.setConfigs(groupContentRefData);
      });
    }
  });
  // 添加分组
  const handleAddGroup = async () => {
    const newGroupKey = groupContentRef.value?.addGroup();
    // 等待DOM更新后滚动到新分组位置
    nextTick(() => {
      // 增加延迟确保DOM完全渲染
      setTimeout(() => {
        if (newGroupKey) {
          const newGroupElement = document.querySelector(`[data-group-key="${newGroupKey}"]`);
          if (newGroupElement) {
            newGroupElement.scrollIntoView({
              behavior: 'smooth',
              block: 'start',
            });
          }
        }
      }, 100);
    });
  };
  // 一键展开分组
  const handleOpenGroup = () => {
    openGroup.value = !openGroup.value;
    groupContentRef.value?.openGroup(openGroup.value);
  };
  // 获取配置信息
  const getResultConfig = () => {
    if (outputConfigEnableGrouping.value.enable_grouping) {
      const groupContentRefData =  groupContentRef.value?.handleGetResultConfig();
      const isGroupOutputConfig = {
        enable_grouping: true,
        groups: [] as Array<{ name: string; output_fields: any[] }>,
      };
      isGroupOutputConfig.groups = groupContentRefData.map((item: any) => {
        const groupConfig = {
          name: item.name, // 分组名
          output_fields: item.config?.map((configItem: any) => {
            // 表格
            if (configItem.type === 'table') {
              return {
                raw_name: configItem.name,
                json_path: configItem.json_path,
                description: configItem.listDescription || '',
                display_name: configItem.listName || '',
                drill_config: null,
                enum_mappings: null,
                field_config: {
                  field_type: 'table',
                  output_fields: configItem?.list.map((listItem: any) => ({
                    raw_name: listItem.name,
                    json_path: listItem.json_path,
                    description: listItem?.description || '',
                    display_name: listItem?.display_name || '',
                    drill_config: listItem?.drill_config || null,
                    enum_mappings: {
                      mappings: listItem?.enum_mappings?.mappings || [],
                    },
                  })),
                },
              };
            }
            // 对象
            return {
              raw_name: configItem.name,
              json_path: configItem.json_path,
              description: configItem.config?.description || '',
              display_name: configItem.config?.display_name || '',
              drill_config: configItem.config?.drill_config || null,
              field_config: {
                field_type: 'kv',
              },
              enum_mappings: {
                mappings: configItem.config?.mappings || [],
              },
            };
          }),
        };
        return groupConfig;
      });
      return isGroupOutputConfig;
    }
    const contentRefData  = contentRef.value?.handleGetResultConfig();

    const noGroupOutputConfig = {
      enable_grouping: false,
      groups: [] as Array<{ name: string; output_fields: any[] }>,
    };

    noGroupOutputConfig.groups[0] = {
      name: '',
      output_fields: contentRefData.map((item: any) => {
        if (item.type === 'table') {
          return {
            raw_name: item.name,
            json_path: item.json_path,
            description: item.listDescription || '',
            display_name: item.listName || '',
            drill_config: null,
            enum_mappings: null,
            field_config: {
              field_type: 'table',
              output_fields: item.list.map((listItem: any) => ({
                raw_name: listItem.name,
                json_path: listItem.json_path,
                description: listItem?.description || '',
                display_name: listItem?.display_name || '',
                drill_config: listItem?.drill_config || null,
                enum_mappings: {
                  mappings: listItem?.enum_mappings?.mappings || [],
                },
              })),
            },
          };
        }
        return {
          raw_name: item.name,
          json_path: item.json_path,
          description: item?.config.description || '',
          display_name: item?.config.display_name || '',
          drill_config: item?.config.drill_config || null,
          enum_mappings: {
            mappings: item?.config.mappings || [],
          },
          field_config: {
            field_type: 'kv',
          },
        };
      }),
    };
    return noGroupOutputConfig;
  };
  defineExpose<Exposes>({
    // 提交获取字段
    handleGetResultConfig() {
      return getResultConfig();
    },
    setConfigs(data: any) {
      outputConfigEnableGrouping.value.enable_grouping = data.enable_grouping;
      isGrouping.value = data.enable_grouping;
      nextTick(() => {
        contentRef.value?.setConfigs(data.groups);
        groupContentRef.value?.setConfigs(data.groups);
      });
    },
  });
</script>

<style lang="postcss" scoped>
.group-box {
  display: flex;
  font-size: 12px;
  color: #4d4f56;
}

.group {
  margin-left: 10px;
}

.info-fill {
  margin-left: 10px;
  font-size: 14px;
  color: #979ba5;
}

.info-fill-tex {
  margin-left: 10px;
  font-size: 12px;
  color: #979ba5;
}

.group-button {
  margin-left: 10px;
  font-size: 12px;
  color: #3a84ff;
  cursor: pointer;
}

.plus-circle {
  margin-left: 10px;
  font-size: 14px;
  color: #3a84ff;
  cursor: pointer;

}

.plus-circle-tex {
  margin-left: 5px;
  font-size: 12px;
  color: #3a84ff;
  cursor: pointer;
}

.line {
  display: inline-block;
  width: 1px;
  height: 16px;
  margin-left: 10px;
  vertical-align: middle;
  background: #dcdee5;
}
</style>
