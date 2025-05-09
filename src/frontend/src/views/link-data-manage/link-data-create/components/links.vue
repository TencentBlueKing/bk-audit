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
  <bk-loading :loading="loading">
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
            <div
              class="left-name"
              :class="link.left_table.table_type === 'EventLog' ? 'select-group-grid' : ''">
              <select-verify
                ref="selectVerifyRef"
                :default-value="link.left_table.table_type"
                theme="background">
                <bk-cascader
                  v-if="Array.isArray(link.left_table.rt_id)"
                  v-slot="{data, node}"
                  v-model="link.left_table.rt_id"
                  :filter-method="configTypeTableFilter"
                  filterable
                  id-key="value"
                  :list="index === 0 ? allConfigTypeTable : leftTableList"
                  name-key="label"
                  :placeholder="t('搜索数据名称、别名、数据ID等')"
                  trigger="hover"
                  @change="(value: Array<string>) => handleSelectLeftTable(value, index)">
                  <p
                    v-bk-tooltips="{
                      disabled: !data.disabled || !data.leaf,
                      content: node.pathNames[0] === '资产数据'
                        ? t('该系统暂未上报资源数据')
                        : t('审计无权限，请前往BKBase申请授权'),
                      delay: 400,
                    }">
                    {{ node.name }}
                  </p>
                </bk-cascader>
                <audit-icon
                  v-if="link.left_table.table_type && link.left_table.table_type !== 'EventLog'"
                  class="view-icon"
                  type="view"
                  @click="dataStructurePreview(link.left_table.rt_id)" />
              </select-verify>
              <template v-if="link.left_table.table_type === 'EventLog'">
                <select-verify
                  ref="selectVerifyRef"
                  :default-value="link.left_table.system_ids"
                  style="flex: 1;"
                  theme="background">
                  <event-log-component
                    ref="eventLogRef"
                    v-model="link.left_table"
                    :link-index="index"
                    :links="links"
                    style="flex: 1;"
                    type="left" />
                  <audit-icon
                    class="view-icon"
                    type="view"
                    @click="dataStructurePreview(link.left_table.rt_id)" />
                </select-verify>
              </template>
            </div>
            <!-- 关联关系 -->
            <join-type
              v-model:joinType="link.join_type"
              :join-type-list="joinTypeList" />
            <!-- 右表 -->
            <div
              class="right-name"
              :class="link.right_table.table_type === 'EventLog' ? 'select-group-grid' : ''">
              <select-verify
                ref="selectVerifyRef"
                :default-value="link.right_table.table_type"
                theme="background">
                <bk-cascader
                  v-if="Array.isArray(link.right_table.rt_id)"
                  v-slot="{data, node}"
                  v-model="link.right_table.rt_id"
                  :filter-method="configTypeTableFilter"
                  filterable
                  id-key="value"
                  :list="rightTableList"
                  name-key="label"
                  :placeholder="t('搜索数据名称、别名、数据ID等')"
                  trigger="hover"
                  @change="(value: Array<string>) => handleSelectRightTable(value, index)">
                  <p
                    v-bk-tooltips="{
                      disabled: !data.disabled || !data.leaf,
                      content: node.pathNames[0] === '资产数据'
                        ? t('该系统暂未上报资源数据')
                        : t('审计无权限，请前往BKBase申请授权'),
                      delay: 400,
                    }">
                    {{ node.name }}
                  </p>
                </bk-cascader>
                <audit-icon
                  v-if="link.right_table.table_type && link.right_table.table_type !== 'EventLog'"
                  class="view-icon"
                  type="view"
                  @click="dataStructurePreview(link.right_table.rt_id)" />
              </select-verify>
              <template v-if="link.right_table.table_type === 'EventLog'">
                <select-verify
                  ref="selectVerifyRef"
                  :default-value="link.right_table.system_ids"
                  style="flex: 1;"
                  theme="background">
                  <event-log-component
                    ref="eventLogRef"
                    v-model="link.right_table"
                    :link-index="index"
                    :links="links"
                    style="flex: 1;"
                    type="right" />
                  <audit-icon
                    class="view-icon"
                    type="view"
                    @click="dataStructurePreview(link.right_table.rt_id)" />
                </select-verify>
              </template>
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
  </bk-loading>
  <structure-preview
    v-model:show-structure="showStructure"
    :rt-id="currentViewRtId" />
</template>
<script setup lang="ts">
  import { InfoBox } from 'bkui-vue';
  import { computed, h, inject, nextTick, type Ref, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  import StrategyManageService from '@service/strategy-manage';

  import LinkDataDetailModel from '@model/link-data/link-data-detail';
  import CommonDataModel from '@model/strategy/common-data';

  import JoinType from './components/join-type.vue';
  import EventLogComponent from './components/scheme-input/event-log.vue';
  import SelectVerify from './components/select-verify.vue';
  import StructurePreview from './components/structure-preview.vue';
  import TableField from './components/table-field.vue';

  import useRequest from '@/hooks/use-request';

  interface Exposes{
    getValue: () => Promise<any>;
    setValue: (value: LinkDataDetailModel['config']['links']) => void;
  }

  interface ConfigTypeTableItem {
    label: string
    value: string
    children: Array<{
      label: string
      value: string
      children?: Array<{
        label: string
        value: string
      }>
    }>
  }

  const { t } = useI18n();
  const tableFieldRef = ref();
  const selectVerifyRef = ref();
  const allConfigTypeTable = ref<Array<ConfigTypeTableItem>>([]);
  const links = defineModel<LinkDataDetailModel['config']['links']>('links', {
    required: true,
  });
  const isEditMode = inject<Ref<boolean>>('isEditMode', ref(false));
  const loading = ref(false);
  let isInit = false;

  const showStructure = ref(false);
  const currentViewRtId = ref('');

  const linkTableTableTypeList = ref<Array<{
    label: string
    value: string
  }>>([]);
  const oldFirstLefTable = ref<Array<string>>([]);
  const joinTypeList = ref<Array<Record<string, any>>>([]);

  if (!isEditMode.value) {
    isInit = true;
  }

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

  const dataStructurePreview = (rtId: Array<string> | string) => {
    showStructure.value = true;
    currentViewRtId.value = rtId.length > 0 ? rtId[rtId.length - 1] : '';
  };

  const setDeepestLeafDisabled = (node: any, selectedRtIds: Set<string>) => {
    if (!node.children || node.children.length === 0) {
      // 当前节点就是叶子节点
      return {
        ...node,
        disabled: !selectedRtIds.has(node.value),
      };
    }

    // 递归处理子节点
    const processedChildren = node.children.map((child: any) => setDeepestLeafDisabled(child, selectedRtIds));

    return {
      ...node,
      children: processedChildren,
    };
  };

  // 左表只能使用前面已经选中的数据源
  const leftTableList = computed(() => {
    const selectedTableTypes = new Set<string>();
    const selectedRtIds = new Set<string>();

    // 收集所有已选的table_type和rt_id
    links.value.forEach((link) => {
      selectedTableTypes.add(link.left_table.table_type);
      selectedTableTypes.add(link.right_table.table_type);
      if (link.left_table.rt_id.length) {
        // 取rt_id数组的最后一个元素
        selectedRtIds.add(link.left_table.rt_id[link.left_table.rt_id.length - 1]);
      }
      if (link.right_table.rt_id.length) {
        // 取rt_id数组的最后一个元素
        selectedRtIds.add(link.right_table.rt_id[link.right_table.rt_id.length - 1]);
      }
    });

    // 从 allConfigTypeTable 中筛选出与收集到的类型匹配的项
    return allConfigTypeTable.value
      .filter(item => selectedTableTypes.has(item.value))
      .map(item => setDeepestLeafDisabled(item, selectedRtIds));
  });

  // 右表不能再选EventLog，如果左表选了，直接隐藏不显示
  const rightTableList = computed(() => {
    // 收集所有已选的rt_id
    const usedRtIds = new Set<string>();
    links.value.forEach((link) => {
      if (link.left_table.rt_id.length) {
        usedRtIds.add(link.left_table.rt_id[link.left_table.rt_id.length - 1]);
      }
      if (link.right_table.rt_id.length) {
        usedRtIds.add(link.right_table.rt_id[link.right_table.rt_id.length - 1]);
      }
    });

    // 过滤掉EventLog类型（如果左表选了EventLog）
    const filteredTables = links.value.some(link => link.left_table.table_type === 'EventLog')
      ? allConfigTypeTable.value.filter(item => item.value !== 'EventLog')
      : [...allConfigTypeTable.value];

    // 设置最深叶子节点的disabled状态（只能选未使用过的rt_id）
    return filteredTables.map(table => ({
      ...table,
      children: table.children?.map(child => ({
        ...child,
        children: child.children?.map(leaf => ({
          ...leaf,
          disabled: usedRtIds.has(leaf.value),
        })),
      })),
    }));
  });

  // 获取tableid
  const {
    run: fetchTable,
  } = useRequest(StrategyManageService.fetchTable, {
    defaultValue: [],
  });


  // 获取全部tableid
  const getAllConfigTypeTable = () => {
    loading.value = true;
    const requests = linkTableTableTypeList.value.map(item => async () => {
      const data = await fetchTable({
        table_type: item.value,
      });
      return [{
        ...item,
        children: data.map(tableItem => ({
          ...tableItem,
          leaf: true,
          disabled: !(tableItem.children && tableItem.children.length) && item.value !== 'EventLog',
        })),
      }];
    });
    // 获取全部table
    Promise.all(requests.map(fn => fn()))
      .then((results) => {
        const flattenedResults = results.reduce((acc, curr) => acc.concat(curr), []);
        allConfigTypeTable.value = flattenedResults;
        loading.value = false;
      });
  };

  // 搜索数据源
  const configTypeTableFilter = (node: Record<string, any>, key: string) => {
    // 转换searchKey为小写以支持大小写不敏感的搜索
    const lowercaseSearchKey = key.toLowerCase();
    return (node.data.label.toLowerCase().includes(lowercaseSearchKey)
      || node.data.value.toLowerCase().includes(lowercaseSearchKey));
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
   */
  const resetLink = (link: LinkDataDetailModel['config']['links'][0]) => ({
    ...link,
    left_table: {
      ...link.left_table,
      rt_id: [],
      system_ids: [],
      table_type: '',
    },
    right_table: {
      ...link.right_table,
      rt_id: [],
      system_ids: [],
      table_type: '',
    },
    link_fields: link.link_fields.map(() => ({
      left_field: { field_name: '', display_name: '' },
      right_field: { field_name: '', display_name: '' },
    })),
  } as LinkDataDetailModel['config']['links'][0]);

  /**
   * 处理选择左表
   * @param value 选择的表类型
   * @param index 当前链接的索引
   */
  const handleSelectLeftTable = (value: Array<string>, index: number) => {
    if (!isInit) return;
    const configType = value[0];

    // 检查是否需要显示提示框的条件
    const shouldShowConfirm = index === 0 && (
      // 其他关联有值
      links.value.some((link, i) => i !== 0 && (
        link.left_table.table_type || link.right_table.table_type
      ))
      // 或者第一个关联的右表有值
      || links.value[0].right_table.table_type
    );

    if (shouldShowConfirm) {
      InfoBox(createInfoBoxConfig({
        onConfirm() {
          const newLinks = links.value.map(item => resetLink(item));
          newLinks[0].left_table.table_type = configType;
          newLinks[0].left_table.rt_id = value;
          links.value = newLinks;
        },
        onClose() {
          // 恢复旧的左表数据（包括rt_id和table_type）
          const newLinks = [...links.value];
          newLinks[0].left_table.rt_id = oldFirstLefTable.value;
          newLinks[0].left_table.table_type = oldFirstLefTable.value[0] || '';
          links.value = newLinks;
        },
      }));
      return;
    }

    // 不需要提示时直接设置值
    links.value[index].left_table.table_type = configType;
    links.value[index].link_fields = links.value[index].link_fields.map(field => ({
      ...field,
      left_field: { field_name: '', display_name: '' },
    }));
  };

  /**
   * 处理选择右表
   * @param index 当前链接的索引
   */
  const handleSelectRightTable = (value: Array<string>, index: number) => {
    if (!isInit) return;
    const configType = value[0];
    links.value[index].right_table.table_type = configType;
    links.value[index].link_fields = links.value[index].link_fields.map(field => ({
      ...field,
      right_field: { field_name: '', display_name: '' },
    }));
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
      getAllConfigTypeTable();
    },
  });

  const handleAdd = () => {
    links.value?.push({
      left_table: {
        rt_id: [],
        table_type: '',
        system_ids: [],
        display_name: '',
      },
      right_table: {
        rt_id: [],
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

  watch(() => links.value[0].left_table.rt_id, (_, old) => {
    oldFirstLefTable.value = old as Array<string>;
  });

  /**
   * 根据rt_id逆向查找完整的级联路径
   * @param rtId 要查找的rt_id
   * @returns 完整的级联路径数组，如['config_type', 'parent_id', 'rt_id']
   */
  const findFullPath = (rtId: string, tableType: string): string[] => {
    if (!rtId) return [];

    // 如果是EventLog类型，直接返回两层路径
    if (tableType === 'EventLog') {
      return [tableType, rtId];
    }

    // 遍历所有配置类型
    for (const configType of allConfigTypeTable.value) {
      // 如果配置类型不匹配则跳过
      if (configType.value !== tableType) continue;

      // 遍历二级子项
      for (const child of configType.children || []) {
        // 如果有三级子项，则遍历查找
        for (const grandChild of child.children || []) {
          if (grandChild.value === rtId) {
            return [configType.value, child.value, rtId];
          }
        }

        // 如果没有三级子项，检查二级子项本身是否匹配
        if (child.value === rtId) {
          return [configType.value, rtId];
        }
      }
    }

    return [];
  };

  defineExpose<Exposes>({
    getValue() {
      return Promise.all([
        ...tableFieldRef.value.map((item: { getValue: () => any }) => item.getValue()),
        ...selectVerifyRef.value.map((item: { getValue: () => any }) => item.getValue()),
      ]);
    },
    async setValue(value: LinkDataDetailModel['config']['links']) {
      // 等待allConfigTypeTable有值
      if (!allConfigTypeTable.value.length) {
        await new Promise<void>((resolve) => {
          const unwatch = watch(allConfigTypeTable, () => {
            if (allConfigTypeTable.value.length) {
              unwatch();
              resolve();
            }
          }, { immediate: true });
        });
      }

      // 处理每个link的rt_id，转换为完整的级联路径
      links.value = value.map((link) => {
        // 创建全新的left_table对象
        const leftTable = {
          ...link.left_table,
          rt_id: Array.isArray(link.left_table.rt_id)
            ? [...link.left_table.rt_id]
            : findFullPath(link.left_table.rt_id as string, link.left_table.table_type),
        };

        // 创建全新的right_table对象
        const rightTable = {
          ...link.right_table,
          rt_id: Array.isArray(link.right_table.rt_id)
            ? [...link.right_table.rt_id]
            : findFullPath(link.right_table.rt_id as string, link.right_table.table_type),
        };

        return {
          ...link,
          left_table: leftTable,
          right_table: rightTable,
        };
      });

      nextTick(() => {
        isInit = true;
      });
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
    width: calc(100% - 44px);

    .left-name,
    .right-name {
      :deep(.bk-form-item) {
        margin-bottom: 0;
      }

      .view-icon {
        position: absolute;
        top: 9px;
        right: 22px;
        font-size: 14px;
        color: #3a84ff;
        cursor: pointer;
      }
    }

    .select-group-grid {
      display: grid;
      grid-template-columns: auto 1fr;
    }

    :deep(.bk-infobox-title) {
      margin-top: 0;
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
