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
  <div class="list-table">
    <div class="list-table-head">
      <audit-icon
        class="move"
        type="move" />
      <span class="head-text">{{ data.name }}</span>
      <bk-tag
        style="margin-left: 10px;background-color: #fdeed8;"
        theme="warning">
        {{ t('表格') }}
      </bk-tag>
      <audit-icon
        class="close"
        type="close" />
    </div>
    <div class="list-table-body">
      <div class="list-info">
        <bk-input
          v-model="listInfo.name"
          class="mb8"
          style="width: 400px;">
          <template #prefix>
            <span class="info-prefix">{{ t('表格显示名') }} </span>
          </template>
        </bk-input>
        <bk-input
          v-model="listInfo.desc"
          class="mb8"
          style="width: 100%;margin-left: 20px;">
          <template #prefix>
            <span class="info-prefix">{{ t('表格说明') }} </span>
          </template>
        </bk-input>
      </div>
      <div class="list-content">
        <div class="content-title">
          {{ t('表格字段设置') }}
        </div>
        <div class="content">
          <div class="render-field">
            <div class="field-header-row">
              <div
                class="field-value"
                style="flex: 0 0 200px;">
                {{ t('字段名') }}
              </div>
              <div
                class="field-value"
                style="flex: 0 0 250px;">
                {{ t('显示名') }}
              </div>
              <div
                class="field-value"
                style="flex: 0 0 250px;">
                {{ t('字段值映射') }}
              </div>
              <div
                class="field-value"
                style="flex: 0 0 300px;">
                {{ t('字段下钻') }}
              </div>
              <div
                class="field-value">
                <span
                  v-bk-tooltips="{ content: t('在查询结果页，鼠标移入label，即可显示字段说明') }"
                  class="underline-dashed">{{ t('字段说明') }}</span>
              </div>
            </div>
          </div>
          <vuedraggable
            class="draggable-box"
            :group="{
              name: 'field',
              pull: false,
              push: true
            }"
            item-key="key"
            :list="list">
            <template #item="{ element }">
              <div>
                <!-- 显示名 -->
                <div class="render-field">
                  <div class="field-row">
                    <div
                      class="field-value"
                      style="flex: 0 0 200px;">
                      <audit-icon
                        class="field-value-move"
                        type="move" />
                      <span class="field-value-text">{{ element.name }}</span>
                    </div>
                    <div
                      class="field-value"
                      style="flex: 0 0 250px;">
                      <bk-form-item
                        error-display-type="tooltips"
                        label=""
                        label-width="0">
                        <bk-input v-model="element.displayName" />
                      </bk-form-item>
                    </div>
                    <div
                      class="field-value"
                      style="flex: 0 0 250px;">
                      <bk-form-item
                        error-display-type="tooltips"
                        label=""
                        label-width="0">
                        <span
                          :class="element?.enum_mappings?.mappings.length === 0 ? `field-span` : `field-span-black`"
                          @click="handleAddEnumMapping(element)">
                          {{ t(element?.enum_mappings?.mappings.length === 0 ? '请点击配置' : '已配置') }}
                        </span>
                      </bk-form-item>
                    </div>
                    <div
                      class="field-value"
                      style="flex: 0 0 300px;">
                      <bk-form-item
                        error-display-type="tooltips"
                        label=""
                        label-width="0">
                        <span class="field-span"> {{ t('请点击配置') }} </span>
                      </bk-form-item>
                    </div>
                    <div
                      class="field-value">
                      <bk-form-item
                        error-display-type="tooltips"
                        label=""
                        label-width="0">
                        <bk-input v-model="element.description" />
                      </bk-form-item>
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </vuedraggable>
        </div>
      </div>
    </div>
    <!-- 字段映射 -->
    <field-dict
      ref="fieldDictRef"
      v-model:showFieldDict="showFieldDict"
      :edit-data="enumMappingsData"
      @submit="handleDictSubmit" />
  </div>
</template>
<script setup lang='ts'>
  import { onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import Vuedraggable from 'vuedraggable';

  import fieldDict from '@/views/strategy-manage/strategy-create/components/step2/components/event-table/field-dict.vue';

  interface Props {
    data: any,
  }

  const props = defineProps<Props>();
  const { t } = useI18n();
  const listInfo = ref({
    name: '',
    desc: '',
  });
  const list = ref([]);
  const showFieldDict = ref(false);
  const enumMappingsData = ref([]);
  // 点击字段映射记录id
  const enumMappingsId = ref('');
  // 点击字段映射
  const handleAddEnumMapping = (element: any) => {
    console.log('点击字段映射', element);
    enumMappingsId.value = element.id;
    enumMappingsData.value = element.enum_mappings.mappings;
    showFieldDict.value = true;
  };

  // 字段映射提交
  const handleDictSubmit = (data: any) => {
    console.log('字段映射提交', data);
    list.value = list.value.map((item: any) => {
      if (item.id === enumMappingsId.value) {
        // eslint-disable-next-line no-param-reassign
        item.enum_mappings.mappings = data;
      }
      return item;
    });
  };
  onMounted(() => {
    console.log('data', props.data?.list);

    list.value = props.data?.list.map((item: any) => ({
      ...item,
      displayName: '',
      enum_mappings: {
        mappings: [],
      },
      fieldDrill: '',
      description: '',
    }));
    // 提取list中每一项的的name
  });
</script>
<style lang="postcss" scoped>
.list-table {
  position: relative;
  margin-top: 20px;
  border: 1px solid #dcdee5;
  border-radius: 2px;

  .list-table-head {
    display: flex;
    height: 31px;
    background: #f0f1f5;
    box-shadow: 0 1px 0 0 #dcdee5;
    align-items: center;

    .move {
      margin-left: 5px;
      color: #c4c6cc;
      cursor: move;
    }

    .head-text {
      margin-left: 5px;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0;
      color: #4d4f56;
    }

    .close {
      position: absolute;
      right: 5px;
      color: #979ba5;
      cursor: pointer;
    }
  }

  .list-info {
    display: flex;
    padding: 20px 10px 0;
  }

  .info-prefix {
    display: inline-block;
    height: 32px;
    padding-right: 5px;
    padding-left: 5px;
    line-height: 31px;
    text-align: center;
    background: #fafbfd;
    border: 1px solid #c4c6cc;
    border-radius: 2px 0 0 2px;
  }

  .list-content {
    padding: 10px;

    .content-title {
      font-size: 12px;
      letter-spacing: 0;
      color: #4d4f56;
    }

    .content {
      padding-top: 10px;
    }
  }
}

.render-field {
  display: flex;
  min-width: 640px;
  overflow: hidden;

  /* border: 1px solid #dcdee5; */
  border-radius: 2px;
  user-select: none;
  flex-direction: column;
  flex: 1;

  .field-select {
    width: 40px;
    text-align: center;
    background: #fafbfd;
  }

  .field-operation {
    width: 170px;
    padding-left: 16px;
    background: #fafbfd;
    border-left: 1px solid #dcdee5;
  }


}

:deep(.field-value) {
  display: flex;
  flex: 1;

  /* width: 180px; */
  overflow: hidden;
  border-left: 1px solid #dcdee5;
  align-items: center;

  .field-value-div {
    display: flex;
    padding: 0 8px;
    cursor: pointer;
    align-items: center;

    &:hover {
      .remove-btn {
        display: block;
      }
    }

    .remove-btn {
      position: absolute;
      top: 36%;
      right: 28px;
      z-index: 1;
      display: none;
      font-size: 12px;
      color: #c4c6cc;
      transition: all .15s;

      &:hover {
        color: #979ba5;
      }

      &.is-popconfirm-visible {
        display: block;
      }
    }

    .remove-mappings-btn {
      top: 40%;
      right: 8px;
    }

    .renew-tips {
      position: absolute;
      right: 8px;
      font-size: 14px;
      color: #3a84ff;
    }
  }

  .bk-form-item.is-error {
    .bk-input--text {
      background-color: #ffebeb;
    }
  }

  .bk-form-item {
    width: 100%;
    margin-bottom: 0;

    .bk-input,
    .bk-date-picker-editor,
    .bk-select-trigger,
    .bk-select-tag,
    .date-picker {
      height: 42px !important;
      border: none;
    }

    .icon-wrapper {
      top: 6px;
    }

    .bk-input.is-focused:not(.is-readonly) {
      border: 1px solid #3a84ff;
      outline: 0;
      box-shadow: 0 0 3px #a3c5fd;
    }

    .bk-form-error-tips {
      top: 12px
    }
  }
}

.field-header-row {
  display: flex;
  height: 42px;
  font-size: 12px;
  line-height: 40px;
  color: #313238;
  background: #f0f1f5;

  .field-value {
    padding-left: 8px;
  }

  .field-value.is-required {
    &::after {
      margin-left: 4px;
      color: red;
      content: '*';
    }
  }

  .field-select,
  .field-operation {
    background: #f0f1f5;
  }
}

.field-row {
  display: flex;
  overflow: hidden;
  font-size: 12px;
  line-height: 42px;
  color: #63656e;
  border-right: 1px solid #dcdee5;
  border-bottom: 1px solid #dcdee5;
}

.field-icon {
  margin-left: 20px;
  color: #c4c6cc;
}

.field-span {
  margin-left: 5px;
  color: #c4c6cc;
  cursor: pointer;
}

.underline-dashed {
  text-decoration: underline;
  text-decoration-style: dashed;
  text-decoration-color: #c4c6cc;
  text-underline-offset: 5px;
  cursor: pointer;
}

.field-value-move {
  margin-left: 5px;
  font-size: 18px;
  color: #c4c6cc;
  cursor: move;
}

.field-value-text {
  margin-left: 5px;
  color: #4d4f56;
}

.field-span-black {
  margin-left: 5px;
  color: black;
  cursor: pointer;
}
</style>
