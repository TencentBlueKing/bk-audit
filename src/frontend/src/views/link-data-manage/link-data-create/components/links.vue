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
  <scroll-faker
    :style="{
      height: `${linksHeight}px`,
    }">
    <template
      v-for="(link, index) in links"
      :key="index">
      <div class="link-data-table">
        <div class="table-head">
          <!-- 左表 -->
          <div class="left-name">
            <bk-form-item
              class="no-label"
              label-width="0"
              :style="configTypeMap[link.left_table.table_type] ? {
                width: '150px',
                marginBottom: '8px'
              } : {
                flex: 1,
                marginBottom: '8px'
              }">
              <select-verify
                ref="selectVerifyRef"
                :default-value="link.left_table.table_type"
                theme="background">
                <bk-select
                  v-model="link.left_table.table_type"
                  filterable
                  :placeholder="t('数据源类型')"
                  :prefix="t('数据源')"
                  @change="(value: string) => handleSelectLeftTableType(value ,index)">
                  <!-- 第一个关联，第一张表有所有选项 -->
                  <bk-option
                    v-for="item in ( index === 0 ? linkTableTableTypeList : leftTableTypeList)"
                    :key="item.value"
                    :label="item.label"
                    :value="item.value" />
                </bk-select>
              </select-verify>
            </bk-form-item>
            <!-- 三种数据源，对应的输入类型 -->
            <select-verify
              v-if="link.left_table.table_type"
              ref="selectVerifyRef"
              :default-value="link.left_table.table_type === 'EventLog' ?
                link.left_table.system_ids :
                link.left_table.rt_id"
              style="flex: 1;"
              theme="background">
              <component
                :is="configTypeMap[link.left_table.table_type]"
                ref="tableTypeRef"
                v-model="link.left_table"
                :link-index="index"
                :links="links"
                style="flex: 1;"
                :table-table-map="tableTableMap"
                type="left"
                @update-table-data="handleUpdateTableData" />
            </select-verify>
          </div>
          <!-- 关联关系 -->
          <join-type
            v-model:joinType="link.join_type"
            :join-type-list="joinTypeList" />
          <!-- 右表 -->
          <div class="right-name">
            <bk-form-item
              class="no-label"
              label-width="0"
              :style="configTypeMap[link.right_table.table_type] ? {
                width: '150px',
                marginBottom: '8px'
              } : {
                flex: 1,
                marginBottom: '8px'
              }">
              <select-verify
                ref="selectVerifyRef"
                :default-value="link.right_table.table_type"
                theme="background">
                <bk-select
                  v-model="link.right_table.table_type"
                  filterable
                  :placeholder="t('数据源类型')"
                  :prefix="t('数据源')"
                  @change="(value: string) => handleSelectRightTableType(value, index)">
                  <!-- rightTableTypeList，左表选中eventlog，右不显示 -->
                  <bk-option
                    v-for="item in rightTableTypeList"
                    :key="item.value"
                    :label="item.label"
                    :value="item.value" />
                </bk-select>
              </select-verify>
            </bk-form-item>
            <!-- 三种数据源，对应的输入类型 -->
            <select-verify
              v-if="link.right_table.table_type"
              ref="selectVerifyRef"
              :default-value="link.right_table.table_type === 'EventLog' ?
                link.right_table.system_ids :
                link.right_table.rt_id"
              style="flex: 1;"
              theme="background">
              <component
                :is="configTypeMap[link.right_table.table_type]"
                ref="tableTypeRef"
                v-model="link.right_table"
                :link-index="index"
                :links="links"
                style="flex: 1;"
                :table-table-map="tableTableMap"
                type="right"
                @update-table-data="handleUpdateTableData" />
            </select-verify>
          </div>
        </div>
        <!-- 对应字段 -->
        <table-field
          ref="tableFieldRef"
          v-model:linkFields="link.link_fields"
          :left-table-rt-id="link.left_table.rt_id"
          :right-table-rt-id="link.right_table.rt_id" />
        <!-- 删除关联关系 -->
        <audit-icon
          v-if="links.length > 1"
          class="delete-link"
          style="font-size: 14px;"
          type="delete"
          @click="() => handleDelete(index)" />
      </div>
    </template>
  </scroll-faker>
  <span
    class="add-link"
    @click="handleAdd">
    <audit-icon
      style="margin-right: 5px;"
      type="add-fill" />
    <span>{{ t('添加关联关系') }}</span>
  </span>
</template>
<script setup lang="ts">
  import { InfoBox } from 'bkui-vue';
  import { computed, h, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StrategyManageService from '@service/strategy-manage';

  import LinkDataDetailModel from '@model/link-data/link-data-detail';
  import CommonDataModel from '@model/strategy/common-data';

  import JoinType from './components/join-type.vue';
  import EventLogComponent from './components/scheme-input/event-log.vue';
  import OtherDataComponent from './components/scheme-input/other.vue';
  import ResourceDataComponent from './components/scheme-input/resource-data.vue';
  import SelectVerify from './components/select-verify.vue';
  import TableField from './components/table-field.vue';

  import useRequest from '@/hooks/use-request';

  type TableData = Array<{
    label: string;
    value: string;
    children: Array<{
      label: string;
      value: string;
    }>
  }>

  interface Exposes{
    getValue: () => Promise<any>;
  }

  const { t } = useI18n();
  const tableFieldRef = ref();
  const selectVerifyRef = ref();
  const links = defineModel<LinkDataDetailModel['config']['links']>('links', {
    required: true,
  });

  const tableTableMap = ref<Record<'BuildIn' | 'BizRt', TableData>>({
    BuildIn: [],
    BizRt: [],
  });
  const configTypeMap: Record<string, any> = ref({
    EventLog: EventLogComponent,
    BuildIn: ResourceDataComponent,
    BizRt: OtherDataComponent,
  });

  const linkTableTableTypeList = ref<Array<Record<string, any>>>([]);
  const oldFirstLefType = ref('');
  const joinTypeList = ref<Array<Record<string, any>>>([]);

  const linksHeight = computed(() => {
    const windowHeight = window.innerHeight;
    const result = links.value.reduce(
      (accumulator, item) => {
        const linkFieldsLength = item.link_fields.length;
        return {
          totalFieldsLength: accumulator.totalFieldsLength + linkFieldsLength,
          linksLength: accumulator.linksLength + 2,
        };
      },
      { totalFieldsLength: 0, linksLength: 0 },
    );
    const resultHeight = (result.totalFieldsLength + result.linksLength) * 41;
    return resultHeight > (windowHeight - 450) ? windowHeight - 450 : resultHeight;
  });

  // 右表不能再选EventLog，如果左表选了，直接隐藏不显示
  const rightTableTypeList = computed(() => {
    if (links.value.some(link => link.left_table.table_type === 'EventLog')) {
      return linkTableTableTypeList.value.filter(item => item.value !== 'EventLog');
    }
    return linkTableTableTypeList.value;
  });

  // 左表只能使用前面已经选中的数据源
  const leftTableTypeList = computed(() => {
    // 使用一个 Set 来存储所有关联中选中的数据源类型，以避免重复
    const selectedTableTypes = new Set();

    // 遍历所有的关联，收集所有的 left_table 和 right_table 的 table_type
    links.value.forEach((link) => {
      selectedTableTypes.add(link.left_table.table_type);
      selectedTableTypes.add(link.right_table.table_type);
    });

    // 从 linkTableTableTypeList 中筛选出与收集到的类型匹配的项
    return linkTableTableTypeList.value.filter(item => selectedTableTypes.has(item.value));
  });

  /**
   * 缓存 'BuildIn' 和 'BizRt' 类型的表格数据
   * @param data - 需要缓存的表格数据，类型为 `TableData`
   * @param type - 表格数据的类型，只能是 `'BuildIn'` 或 `'BizRt'`
   */
  const handleUpdateTableData = (data: TableData, type: 'BuildIn' | 'BizRt') => {
    tableTableMap.value[type] = data;
  };

  const createInfoBoxConfig = (overrides: {onConfirm: () => void, onClose: () => void}): any => ({
    type: 'warning',
    title: t('切换数据源请注意'),
    subTitle: () => h('div', {
      style: {
        color: '#4D4F56',
        backgroundColor: '#f5f6fa',
        padding: '12px 16px',
        borderRadius: '2px',
        fontSize: '14px',
        textAlign: 'left',
      },
    }, t('切换后，已配置的数据将被清空。是否继续？')),
    confirmText: t('继续切换'),
    cancelText: t('取消'),
    headerAlign: 'center',
    contentAlign: 'center',
    footerAlign: 'center',
    ...overrides,
  });

  /**
   * 重置链接的字段和表信息
   * @param link 链接对象
   * @param resetLeft 是否重置左表
   * @param resetRight 是否重置右表
   */
  const resetLink = (link: LinkDataDetailModel['config']['links'][0], resetLeft: boolean, resetRight: boolean) => ({
    ...link,
    left_table: {
      ...link.left_table,
      rt_id: resetLeft ? [] : link.left_table.rt_id,
      system_ids: resetLeft ? [] : link.left_table.system_ids,
      table_type: resetLeft ? '' : link.left_table.table_type,
    },
    right_table: {
      ...link.right_table,
      rt_id: resetRight ? [] : link.right_table.rt_id,
      system_ids: resetRight ? [] : link.right_table.system_ids,
      table_type: resetRight ? '' : link.right_table.table_type,
    },
    link_fields: link.link_fields.map(fieldItem => ({
      left_field: resetLeft ? { field_name: '', display_name: '' } : fieldItem.left_field,
      right_field: resetRight ? { field_name: '', display_name: '' } : fieldItem.right_field,
    })),
  });

  /**
 * 处理选择左表类型
 * @param value 选择的表类型
 * @param index 当前链接的索引
 */
  const handleSelectLeftTableType = (value: string, index: number) => {
    if (index === 0 && links.value.length > 1) {
      InfoBox(createInfoBoxConfig({
        onConfirm() {
          // 重置所有链接的表
          links.value = links.value.map((item, linkIndex) => {
            // 重置所有链接的表
            const updatedLink = resetLink(item, true, true);
            // 第一个链接的左表类型更新为新值
            if (linkIndex === 0) {
              updatedLink.left_table.table_type = value;
            }
            return updatedLink;
          });
        },
        onClose() {
          // 恢复旧的左表类型
          links.value[0].left_table.table_type = oldFirstLefType.value;
        },
      }));
      return;
    }

    // 其他情况，仅重置当前链接的左表
    links.value[index] = resetLink(links.value[index], true, false);
    links.value[index].left_table.table_type = value;
  };

  /**
   * 处理选择右表类型
   * @param index 当前链接的索引
   */
  const handleSelectRightTableType = (value: string, index: number) => {
    // 仅重置当前链接的右表
    links.value[index] = resetLink(links.value[index], false, true);
    links.value[index].right_table.table_type = value;
  };

  // 获取数据源
  const {
    data: commonData,
  } = useRequest(StrategyManageService.fetchStrategyCommon, {
    defaultValue: new CommonDataModel(),
    manual: true,
    onSuccess() {
      linkTableTableTypeList.value = commonData.value.link_table_table_type;
      joinTypeList.value = commonData.value.link_table_join_type;
    },
  });

  const handleAdd = () => {
    links.value?.push({
      left_table: {
        rt_id: '',
        table_type: '',
        system_ids: [],
        display_name: '',
      },
      right_table: {
        rt_id: '',
        table_type: '',
        system_ids: [],
        display_name: '',
      },
      join_type: 'left_join',
      link_fields: [{
        left_field: {
          field_name: '',
          display_name: '',
        },
        right_field: {
          field_name: '',
          display_name: '',
        },
      }],
    });
  };

  const handleDelete = (index: number) => {
    links.value?.splice(index, 1);
  };

  watch(() => links.value[0].left_table.table_type, (_, old) => {
    oldFirstLefType.value = old;
  });

  defineExpose<Exposes>({
    getValue() {
      return Promise.all([
        ...tableFieldRef.value.map((item: { getValue: () => any }) => item.getValue()),
        ...selectVerifyRef.value.map((item: { getValue: () => any }) => item.getValue()),
      ]);
    },
  });
</script>
<style scoped lang="postcss">
.link-data-table {
  position: relative;
  padding: 16px;
  margin-bottom: 8px;
  background: #f5f7fa;
  border-radius: 2px;

  .table-head {
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    gap: 8px;
    align-items: center;
    width: calc(100% - 44px);

    .left-name,
    .right-name {
      display: flex;
    }
  }

  .delete-link {
    position: absolute;
    top: 5px;
    right: 5px;
    font-size: 13px;
    color: #979ba5;
    cursor: pointer;
  }
}

.add-link {
  color: #3a84ff;
  cursor: pointer;
}
</style>
