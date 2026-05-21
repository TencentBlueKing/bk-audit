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
  <bk-sideslider
    :is-show="isShow"
    :title="sliderTitle"
    :width="800"
    @closed="handleClose">
    <template #header>
      <div class="scene-detail-header">
        <div class="header-left">
          <span class="header-title">{{ t('场景详情') }}</span>
          <span class="header-divider">|</span>
          <show-tooltips-text
            class="header-scene-info"
            :data="`${detailData.name}（${detailData.scene_id}）`" />
        </div>
        <div class="header-right">
          <bk-button
            outline
            theme="primary"
            @click="handleEdit">
            {{ t('编辑') }}
          </bk-button>
          <bk-button
            outline
            @click="handleToggleStatus">
            {{ detailData.status === 'enabled' ? t('停用') : t('启用') }}
          </bk-button>
          <bk-popover
            :disabled="detailData.status !== 'enabled'"
            placement="top">
            <bk-button
              class="mr8"
              :disabled="detailData.status === 'enabled'"
              outline
              @click="handleDelete">
              {{ t('删除') }}
            </bk-button>
            <template #content>
              {{ t('删除场景需先停用场景') }}
            </template>
          </bk-popover>
        </div>
      </div>
    </template>
    <template #default>
      <div class="scene-detail-content">
        <bk-loading
          :loading="isLoading"
          mode="spin"
          size="small">
          <!-- 基础信息 -->
          <div class="info-section">
            <div class="section-title">
              {{ t('基础信息') }}
            </div>
            <div class="info-list">
              <div class="info-item">
                <span class="info-label">{{ t('场景 ID') }}：</span>
                <span class="info-value">{{ detailData.scene_id }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">{{ t('场景名称') }}：</span>
                <span class="info-value">
                  {{ detailData.name }}
                  <audit-icon
                    v-bk-tooltips="t('跳转至场景')"
                    class="ml8 jump-link"
                    type="jump-link"
                    @click="handleJumpToScene" />
                </span>
              </div>
              <div class="info-item">
                <span class="info-label">{{ t('场景描述') }}：</span>
                <span class="info-value">{{ detailData.description || '--' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">{{ t('场景管理员') }}：</span>
                <span class="info-value">{{ formatManagers(detailData.managers) }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">{{ t('场景使用者') }}：</span>
                <span class="info-value">{{ formatUsers(detailData.users) }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">{{ t('启用状态') }}：</span>
                <span class="info-value">
                  <bk-tag :theme="detailData.status === 'enabled' ? 'success' : ''">
                    {{ detailData.status === 'enabled' ? t('启用') : t('停用') }}
                  </bk-tag>
                </span>
              </div>
              <div class="info-item">
                <span class="info-label">{{ t('更新人') }}：</span>
                <span class="info-value">{{ detailData.updated_by }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">{{ t('更新时间') }}：</span>
                <span class="info-value">{{ detailData.updated_at }}</span>
              </div>
            </div>
          </div>

          <!-- 关联系统 -->
          <div class="info-section">
            <div class="section-title">
              {{ t('关联系统') }}
              <bk-tag class="count-tag">
                {{ displaySystems.length }}
              </bk-tag>
            </div>
            <div class="system-list">
              <bk-tag
                v-for="(system, index) in displaySystems"
                :key="index"
                class="system-tag">
                {{ system.name }}
              </bk-tag>
            </div>
          </div>

          <!-- 关联数据表 -->
          <div class="info-section">
            <div class="section-title">
              {{ t('关联数据表') }}
              <bk-tag class="count-tag">
                {{ detailData.tables.length }}
              </bk-tag>
            </div>
            <div class="table-list">
              <bk-tag
                v-for="table in detailData.tables"
                :key="table.table_id"
                class="table-tag">
                {{ textTableTag(table.table_id) }}
              </bk-tag>
            </div>
          </div>
        </bk-loading>
      </div>
    </template>
  </bk-sideslider>
</template>

<script setup lang="ts">
  import {
    computed,
    ref,
    watch,
  } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRouter } from 'vue-router';

  import MetaManageService from '@service/meta-manage';
  import SceneManageService from '@service/scene-manage';
  import StrategyManageService from '@service/strategy-manage';

  import SceneModel from '@model/scene/scene';
  import CommonDataModel from '@model/strategy/common-data';

  import ShowTooltipsText from '@components/show-tooltips-text/index.vue';

  import useRequest from '@/hooks/use-request';
  import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

  interface Props {
    isShow: boolean;
    sceneId: string | number;
  }

  interface Emits {
    (e: 'update:isShow', value: boolean): void;
    (e: 'edit', scene: SceneModel): void;
    (e: 'toggle-status', scene: SceneModel): void;
    (e: 'delete', scene: SceneModel): void;
  }


  const props = defineProps<Props>();
  const emits = defineEmits<Emits>();
  const isLoading = ref(false);
  const { t } = useI18n();
  const router = useRouter();

  const detailData = ref<SceneModel>(new SceneModel());
  const sliderTitle = computed(() => t('场景详情'));
  // 有权限的系统列表（is_all_systems 时展示）
  const permissionSystems = ref<Array<{ system_id: string; name: string }>>([]);

  // 当 is_all_systems 为 true 时展示有权限的系统，否则展示关联的系统
  const displaySystems = computed(() => {
    const isAllSystems = detailData.value.systems?.some(s => s.is_all_systems);
    if (isAllSystems) {
      return permissionSystems.value;
    }
    return (detailData.value.systems || []).map(s => ({ system_id: s.system_id, name: textSystemTag(s.system_id) }));
  });

  const textSystemTag = (id: string) => {
    const item = permissionSystems.value.find(item => item.system_id === id);
    return item ? item.name : id;
  };

  // 级联表数据，用于反查 table_id 对应的显示名
  interface FlatTableItem { pathName: string; value: string }
  const flatTableList = ref<FlatTableItem[]>([]);

  const textTableTag = (tableId: string) => {
    const found = flatTableList.value.find(item => item.value === tableId);
    return found ? found.pathName : tableId;
  };

  const {
    run: fetchTable,
  } = useRequest(StrategyManageService.fetchTable, {
    defaultValue: [],
  });

  const {
    run: fetchStrategyCommon,
  } = useRequest(StrategyManageService.fetchStrategyCommon, {
    defaultValue: new CommonDataModel(),
    onSuccess: (data) => {
      type ConfigTypeItem = { label: string; value: string };
      // eslint-disable-next-line max-len
      const targetTypes = (data.rule_audit_config_type as ConfigTypeItem[]).filter(item => item.value !== 'EventLog' && item.value !== 'LinkTable');
      const requests = targetTypes.map((typeItem: ConfigTypeItem) => {
        const req = fetchTable({ table_type: typeItem.value, scene_id: getSceneSystemParams().scope_id });
        return req.then((tableData: any[]) => {
          const flat: FlatTableItem[] = [];
          tableData.forEach((group: any) => {
            if (group.children && group.children.length) {
              group.children.forEach((child: any) => {
                flat.push({
                  value: child.value,
                  pathName: `${typeItem.label}/${group.label}/${child.label}`,
                });
              });
            } else {
              flat.push({ value: group.value, pathName: `${typeItem.label}/${group.label}` });
            }
          });
          return flat;
        });
      });
      Promise.all(requests).then((results) => {
        flatTableList.value = results.reduce((acc, curr) => acc.concat(curr), []);
      });
    },
  });
  // 格式化管理员显示
  const formatManagers = (managers: string[]) => {
    if (!managers || managers.length === 0) return '--';
    return managers.join('、');
  };

  // 格式化使用者显示
  const formatUsers = (users: string[]) => {
    if (!users || users.length === 0) return '-';
    return users.join('、');
  };

  // 编辑
  const handleEdit = () => {
    emits('edit', detailData.value);
  };

  // 切换状态
  const handleToggleStatus = () => {
    emits('toggle-status', detailData.value);
  };

  // 删除
  const handleDelete = () => {
    emits('delete', detailData.value);
  };

  // 跳转到场景
  const handleJumpToScene = () => {
    const routeData = router.resolve({
      name: 'sceneInfo',
      query: {
        scene_id: String(detailData.value.scene_id),
      },
    });
    window.open(routeData.href, '_blank');
  };

  // 关闭
  const handleClose = () => {
    emits('update:isShow', false);
  };

  // 获取有权限的系统列表（用于 is_all_systems 时展示）
  const {
    run: fetchPermissionSystems,
  } = useRequest(MetaManageService.fetchSystemWithAction, {
    defaultValue: [] as any[],
    onSuccess: (data: any[]) => {
      permissionSystems.value = data.map((item: any) => ({ system_id: item.system_id, name: item.name }));
    },
  });


  // 获取场景详情
  const {
    run: fetchSceneDetail,
  } = useRequest(SceneManageService.fetchSceneDetail, {
    defaultValue: {} as SceneModel,
    onSuccess: (res) => {
      isLoading.value = false;
      detailData.value = res;
    },
  });

  // 加载详情数据
  const loadDetail = () => {
    isLoading.value = true;
    fetchStrategyCommon();
    fetchPermissionSystems({
      action_ids: 'view_system,edit_system',
      audit_status__in: 'accessed',
      namespace: 'default',
      order_type: 'asc',
      sort_keys: 'name',
      with_favorite: false,
      with_system_status: false,
    }).then(() => {
      fetchSceneDetail(props.sceneId as any);
    });
  };

  // 供父组件调用，刷新详情数据
  const refresh = () => {
    if (props.isShow) {
      loadDetail();
    }
  };

  defineExpose({ refresh });

  // 监听 isShow 变化加载数据
  watch(() => props.isShow, (newIsShow) => {
    if (newIsShow) {
      loadDetail();
    }
  });
</script>

<style lang="postcss" scoped>
.scene-detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;

  .header-left {
    display: flex;
    align-items: center;

    .header-title {
      width: 70px;
      font-weight: 700;
    }

    .header-divider {
      margin: 0 8px;
      color: #dcdee5;
    }

    .header-scene-info {
      color: #63656e;
    }
  }

  .header-right {
    display: flex;
    gap: 8px;
  }
}

.scene-detail-content {
  padding: 24px 40px;

  .info-section {
    margin-bottom: 24px;

    .section-title {
      display: flex;
      align-items: center;
      margin-bottom: 16px;
      font-size: 14px;
      font-weight: 700;
      color: #313238;

      .count-tag {
        margin-left: 8px;
      }
    }

    .info-list {
      .info-item {
        display: flex;
        margin-bottom: 16px;
        font-size: 12px;
        line-height: 20px;

        .info-label {
          flex-shrink: 0;
          width: 100px;
          color: #63656e;
          text-align: right;
        }

        .info-value {
          display: flex;
          flex: 1;
          align-items: center;
          color: #313238;

          .jump-link {
            color: #3a84ff;
            cursor: pointer;

            &:hover {
              color: #699df4;
            }
          }
        }
      }
    }

    .system-list,
    .table-list {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;

      .system-tag,
      .table-tag {
        margin: 0;
      }
    }
  }
}
</style>
