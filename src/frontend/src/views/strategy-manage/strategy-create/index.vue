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
  <!-- 步进条 -->
  <teleport to="#teleport-nav-step">
    <bk-steps
      v-model:cur-step="currentStep"
      class="strategy-upgrade-step"
      :line-type="isEditMode ? 'solid' : 'dashed'"
      :steps="steps" />
  </teleport>

  <keep-alive>
    <component
      :is="renderCom"
      ref="comRef"
      :edit-data="editData"
      :form-data="formData"
      :is-edit-data-loading="isEditDataLoading"
      :select="formData.configs.select"
      :strategy-name="formData.strategy_name"
      :strategy-type="formData.strategy_type"
      style="margin-bottom: 24px;"
      @cancel="handleCancel"
      @next-step="(step: any, params: any) => handleNextStep(step, params)"
      @previous-step="(step: number, params: any) => handlePreviousStep(step, params)"
      @save-current-step="handleSaveCurrentStep"
      @show-preview="showPreview = true"
      @submit-data="handleSubmit" />
  </keep-alive>

  <!-- 保存中 loading：Dialog 实现，esc 不关闭、无底部按钮 -->
  <bk-dialog
    v-model:is-show="showSaveDialog"
    :close-icon="false"
    :esc-close="false"
    :quick-close="false"
    show-mask
    width="400">
    <div class="save-dialog-body">
      <bk-loading
        loading
        mode="spin"
        size="small"
        theme="primary" />
      <div class="save-dialog-text">
        {{ isEditMode ? t('更新中,请稍后...') : t('创建中,请稍后...') }}
      </div>
    </div>
    <template #footer />
  </bk-dialog>

  <audit-sideslider
    ref="sidesliderRef"
    v-model:isShow="showPreview"
    :show-footer="false"
    :title="t('风险单预览')"
    :width="960">
    <div>
      <preview :risk-data="formData" />
    </div>
  </audit-sideslider>
</template>

<script setup lang='ts'>
  import { InfoBox } from 'bkui-vue';
  import _ from 'lodash';
  import {
    computed,
    onMounted,
    ref,
    toRaw,
    watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';

  import MetaManageService from '@service/meta-manage';
  import StrategyManageService from '@service/strategy-manage';

  import StrategyModel from '@model/strategy/strategy';
  import StrategyFieldEvent from '@model/strategy/strategy-field-event';

  import eventReport from './components/event-report/index.vue';
  import Preview from './components/preview/index.vue';
  import Step1 from './components/step1/index.vue';
  import Step2 from './components/step2/index.vue';
  import Step3 from './components/step3/index.vue';

  import useMessage from '@/hooks/use-message';
  import useRequest from '@/hooks/use-request';


  interface IFormData {
    strategy_id?: number,
    strategy_name: string,
    tags: Array<string>,
    description: string,
    control_id: string,
    control_version?: number,
    configs: Record<string, any>,
    status: string,
    risk_level: string,
    risk_hazard: string,
    risk_guidance: string,
    risk_title: string,
    strategy_type: string,
    event_data_field_configs: StrategyFieldEvent['event_data_field_configs'],
    event_basic_field_configs: StrategyFieldEvent['event_basic_field_configs'],
    event_evidence_field_configs: StrategyFieldEvent['event_evidence_field_configs'],
    risk_meta_field_config: StrategyFieldEvent['risk_meta_field_config'],
    processor_groups: Array<any>,
    notice_groups: Array<any>,
    report_enabled: boolean,
    report_auto_render: boolean,
    report_config: Record<string, any>,
  }

  const router = useRouter();
  const route = useRoute();
  const { messageSuccess } = useMessage();
  const { t } = useI18n();

  const comMap = {
    1: Step1,
    2: Step2,
    3: eventReport,
    4: Step3,
  };
  const steps = [
    { title: t('风险发现') },
    { title: t('单据展示') },
    { title: t('事件调查报告') },
    { title: t('其他配置') },
  ];
  const normalizeStep = (step: unknown): 1 | 2 | 3 | 4 => {
    const n = Number(step);
    if ([1, 2, 3, 4].includes(n)) {
      return n as 1 | 2 | 3 | 4;
    }
    return 1;
  };

  const initialStep = normalizeStep(route.query.step || 1);
  const targetStep = ref<1 | 2 | 3 | 4>(initialStep);
  const currentStep = ref<1 | 2 | 3 | 4>(1);
  const comRef = ref();

  const renderCom = computed(() => comMap[currentStep.value as keyof typeof comMap]);

  let isSwitchSuccess = false;
  const isEditMode = route.name === 'strategyEdit';
  const isCloneMode = route.name === 'strategyClone';

  const showPreview = ref(false);
  const controlTypeId = ref('');// 方案类型id
  const editData = ref(new StrategyModel());
  // 编辑态：标签 ID -> 名称，用于提交前将 tags 转为名称（接口返回的是 ID，提交需名称）
  const tagIdToNameMap = ref<Record<string, string>>({});
  let tagMapPromise: Promise<void> | null = null;
  const ensureTagMapLoaded = () => {
    if (Object.keys(tagIdToNameMap.value).length > 0) return Promise.resolve();
    if (!tagMapPromise) {
      tagMapPromise = MetaManageService.fetchTags().then((data: Array<{ tag_id: string; tag_name: string }>) => {
        data.forEach((item) => {
          if (item.tag_id !== '-1') {
            tagIdToNameMap.value[item.tag_id] = item.tag_name;
          }
        });
      });
    }
    return tagMapPromise;
  };
  const formData = ref<IFormData>({
    strategy_name: '',
    tags: [],
    description: '',
    control_id: '',
    configs: {},
    status: '',
    risk_level: '',
    risk_hazard: '',
    risk_guidance: '',
    risk_title: '',
    strategy_type: '',
    event_data_field_configs: [],
    event_basic_field_configs: [],
    event_evidence_field_configs: [],
    risk_meta_field_config: [],
    processor_groups: [],
    notice_groups: [],
    report_enabled: false,
    report_auto_render: false,
    report_config: {},
  });
  // 进入编辑时的初始表单快照（只在编辑态使用，用于还原）
  const initialFormData = ref<IFormData | null>(null);
  // 编辑状态获取数据
  const {
    run: fetchStrategyInfo,
    loading: isEditDataLoading,
  } = useRequest(StrategyManageService.fetchStrategyInfo, {
    defaultValue: new StrategyModel(),
    // 编辑态：接口返回 tags 为 ID，这里统一转换为名称，保证表单和各步骤内部拿到的都是名称
    onSuccess: async (data) => {
      // // eslint-disable-next-line prefer-destructuring
      editData.value = data;
      editData.value.event_basic_field_configs = editData.value.event_basic_field_configs.map((item) => {
        if (item.drill_config && !Array.isArray(item.drill_config)) {
          // eslint-disable-next-line no-param-reassign
          item.drill_config = [item.drill_config];
          item.drill_config.forEach((drill) => {
            if (!drill.drill_name) {
              // eslint-disable-next-line no-param-reassign
              drill.drill_name = '';
            }
          });
        }
        return item;
      });
      editData.value.event_data_field_configs = editData.value.event_data_field_configs.map((item) => {
        if (item.drill_config && !Array.isArray(item.drill_config)) {
          // eslint-disable-next-line no-param-reassign
          item.drill_config = [item.drill_config];
          item.drill_config.forEach((drill) => {
            if (!drill.drill_name) {
              // eslint-disable-next-line no-param-reassign
              drill.drill_name = '';
            }
          });
        }
        return item;
      });
      editData.value.event_evidence_field_configs = editData.value.event_evidence_field_configs.map((item) => {
        if (item.drill_config && !Array.isArray(item.drill_config)) {
          // eslint-disable-next-line no-param-reassign
          item.drill_config = [item.drill_config];
          item.drill_config.forEach((drill) => {
            if (!drill.drill_name) {
              // eslint-disable-next-line no-param-reassign
              drill.drill_name = '';
            }
          });
        }
        return item;
      });
      editData.value.risk_meta_field_config = editData.value.risk_meta_field_config.map((item) => {
        if (item.drill_config && !Array.isArray(item.drill_config)) {
          // eslint-disable-next-line no-param-reassign
          item.drill_config = [item.drill_config];
          item.drill_config.forEach((drill) => {
            if (!drill.drill_name) {
              // eslint-disable-next-line no-param-reassign
              drill.drill_name = '';
            }
          });
        }
        return item;
      });
      // 确保标签映射已加载后，再用接口返回的数据初始化表单（将 tags 从 ID 转为名称）
      await ensureTagMapLoaded();
      const d = editData.value;
      const normalizedTags = (d.tags ?? []).map((item: string) => tagIdToNameMap.value[String(item)] ?? item);
      d.tags = normalizedTags;
      // 编辑态：用接口返回的完整策略数据初始化 formData，保证任意步骤点「提交」时提交的是全量数据
      formData.value = {
        strategy_name: d.strategy_name ?? '',
        // 此处使用名称而非 ID
        tags: normalizedTags,
        description: d.description ?? '',
        control_id: d.control_id ?? '',
        control_version: d.control_version,
        configs: _.cloneDeep(d.configs ?? {}),
        status: d.status ?? '',
        risk_level: d.risk_level ?? '',
        risk_hazard: d.risk_hazard ?? '',
        risk_guidance: d.risk_guidance ?? '',
        risk_title: d.risk_title ?? '',
        strategy_type: d.strategy_type ?? '',
        event_data_field_configs: _.cloneDeep(d.event_data_field_configs ?? []),
        event_basic_field_configs: _.cloneDeep(d.event_basic_field_configs ?? []),
        event_evidence_field_configs: _.cloneDeep(d.event_evidence_field_configs ?? []),
        risk_meta_field_config: _.cloneDeep(d.risk_meta_field_config ?? []),
        processor_groups: Array.isArray(d.processor_groups) ? [...d.processor_groups] : [],
        notice_groups: Array.isArray(d.notice_groups) ? [...d.notice_groups] : [],
        report_enabled: d.report_enabled ?? false,
        report_auto_render: d.report_auto_render ?? false,
        report_config: _.cloneDeep(d.report_config ?? {}),
      };
      if (d.strategy_id) {
        formData.value.strategy_id = d.strategy_id;
      }
      // 进入编辑时记录一份接口返回的原始值快照（用于还原），其中 tags 已是名称
      if (isEditMode && !initialFormData.value) {
        initialFormData.value = _.cloneDeep(formData.value);
      }
      // 确保先在第 1 步挂载并完成表单初始化，再跳转到目标步骤
      currentStep.value = targetStep.value;
    },
  });

  // 保存中的 Dialog 显示状态，等接口请求结束后再关闭
  const showSaveDialog = ref(false);
  const saveDialogOpenedByDoSave = ref(false);
  // 是否在保存成功后停留在当前页，仅刷新本页数据（不返回列表）
  const stayOnPageAfterSave = ref(false);
  // 从「下一步」弹窗触发保存时，保存成功后需要前往的目标步骤
  const pendingStepAfterSave = ref<1 | 2 | 3 | 4 | null>(null);

  // 保存接口
  const {
    run: saveStrategy,
    loading: isSaveLoading,
  } = useRequest(isEditMode
    ? StrategyManageService.updateStrategy
    : StrategyManageService.saveStrategy, {
    defaultValue: {},
    onSuccess: (data) => {
      // 编辑态：来自「下一步」弹窗的保存，要求不返回列表，只刷新当前页数据
      if (isEditMode && stayOnPageAfterSave.value) {
        stayOnPageAfterSave.value = false;
        window.changeConfirm = false;
        // 更新进入编辑时的快照为当前已保存的数据，后续对比以新快照为准
        if (formData.value) {
          initialFormData.value = _.cloneDeep(formData.value);
        }
        // 保存成功后再切换到目标步骤
        if (pendingStepAfterSave.value) {
          currentStep.value = pendingStepAfterSave.value;
          pendingStepAfterSave.value = null;
        }
        messageSuccess(t('保存成功'));
        return;
      }
      if (isEditMode && formData.value.status === 'running') {
        window.changeConfirm = false;
        router.push({
          name: 'strategyList',
        });
        messageSuccess(t('编辑成功'));
        return;
      }
      const SendSwitchStrategy = (toggle: boolean) => {
        messageSuccess(isEditMode ? t('编辑成功') : t('新建成功'));
        fetchSwitchStrategy({
          strategy_id: data.strategy_id,
          toggle,
        }).then(() => {
          if (isSwitchSuccess) return;
          window.changeConfirm = false;
          router.push({
            name: 'strategyList',
          });
        });
      };
      // 常规策略
      if (controlTypeId.value === 'BKM' && (!isEditMode || !(formData.value.status === 'running'))) {
        isSwitchSuccess = false;
        InfoBox({
          title: t('是否启用该策略'),
          subTitle: t('启用策略将开始按照策略进行审计并输出异常事件，请确认是否启用该策略'),
          confirmText: t('启用'),
          cancelText: t('暂不启用'),
          headerAlign: 'center',
          contentAlign: 'center',
          footerAlign: 'center',
          onConfirm() {
            SendSwitchStrategy(true);
          },
          onClose() {
            SendSwitchStrategy(false);
          },
        });
      } else {
        messageSuccess(isEditMode ? t('编辑成功') : t('新建成功'));
        window.changeConfirm = false;
        router.push({
          name: 'strategyList',
        });
      }
    },
  });

  // 等保存接口请求完成（loading 变为 false）后再关闭 Dialog
  watch(isSaveLoading, (loading) => {
    if (!loading && saveDialogOpenedByDoSave.value) {
      showSaveDialog.value = false;
      saveDialogOpenedByDoSave.value = false;
    }
  });

  // 启用该策略
  const {
    run: fetchSwitchStrategy,
  } = useRequest(StrategyManageService.fetchSwitchStrategy, {
    defaultValue: {},
    onSuccess: () => {
      window.changeConfirm = false;
      router.push({
        name: 'strategyList',
      });
      isSwitchSuccess = true;
    },
  });

  // 提交前统一把 tags 从 ID 转为名称（编辑接口返回 tags 为 ID，提交需名称；未进过第一步时 formData.tags 仍是 ID）
  const normalizeSubmitParams = (params: Record<string, any>) => {
    const next = _.cloneDeep(params);
    if (next.tags?.length && tagIdToNameMap.value && Object.keys(tagIdToNameMap.value).length > 0) {
      next.tags = next.tags.map((item: string) => tagIdToNameMap.value[String(item)] ?? item);
    }
    return next;
  };

  // 下一步/提交共用：将当前表单与步骤回传 params 合并成“完整数据结构”（数组按整体替换，避免 merge 按索引合并）
  const buildMergedFormData = (params: any) => {
    const base = _.cloneDeep(toRaw(formData.value));
    const patch = toRaw(params ?? {});
    return _.mergeWith(base, patch, (_objValue, srcValue) => (Array.isArray(srcValue) ? srcValue : undefined));
  };

  const doSave = async () => {
    await ensureTagMapLoaded();
    const params = normalizeSubmitParams(formData.value);
    saveDialogOpenedByDoSave.value = true;
    showSaveDialog.value = true;
    saveStrategy(params);
  };

  // 提交
  const handleSubmit = () => {
    // ai策略
    if (controlTypeId.value !== 'BKM') {
      InfoBox({
        title: t('策略提交确认'),
        subTitle: isEditMode ? t('本次将提交所有已修改的内容') : t('策略一旦提交，审计中心会开启策略配置的相关检测，若有风险命中策略会立即输出风险，请仔细检查策略配置是否正确以免输出错误风险。'),
        confirmText: t('提交'),
        cancelText: t('取消'),
        headerAlign: 'center',
        contentAlign: 'center',
        footerAlign: 'center',
        onConfirm() {
          doSave();
        },
      });
    } else {
      doSave();
    }
  };

  // 递归移除对象/数组中的 null、undefined 字段，使快照与当前值在语义上一致（无该键 与 键值为 null/undefined 视为相同）
  const cleanNull = (val: any): any => {
    if (_.isNil(val)) return val;
    if (Array.isArray(val)) {
      return val.map(item => cleanNull(item));
    }
    if (typeof val === 'object') {
      const next: Record<string, any> = {};
      Object.keys(val).forEach((k) => {
        const v = (val as any)[k];
        if (v === null || v === undefined) {
          return;
        }
        next[k] = cleanNull(v);
      });
      return next;
    }
    return val;
  };

  // 对比用：先 cleanNull 再按键名排序后序列化，避免「有 having: null」与「无 having 键」或键序不同导致误判
  const stringifyForCompare = (val: any): string => {
    // 深度提取原始值，确保Proxy对象被正确转换
    const deepToRaw = (obj: any): any => {
      if (obj && typeof obj === 'object') {
        const raw = toRaw(obj);
        if (Array.isArray(raw)) {
          return raw.map(item => deepToRaw(item));
        }
        if (raw && typeof raw === 'object') {
          const result: Record<string, any> = {};
          Object.keys(raw).forEach((key) => {
            result[key] = deepToRaw(raw[key]);
          });
          return result;
        }
        return raw;
      }
      return obj;
    };

    const raw = deepToRaw(val);
    if (_.isNil(raw)) return '';
    const cleaned = cleanNull(raw);
    if (typeof cleaned === 'string' || typeof cleaned === 'number' || typeof cleaned === 'boolean') {
      return String(cleaned);
    }

    const stableStringify = (v: any): string => {
      if (_.isNil(v)) return '';

      if (Array.isArray(v)) {
        // 改进的数组处理逻辑：深度比较数组元素
        if (v.length === 0) return '[]';

        // 判断数组元素类型
        const isPrimitiveArray = v.every(item => item === null
          || typeof item === 'string'
          || typeof item === 'number'
          || typeof item === 'boolean');

        const isObjectArray = v.every(item => item !== null && typeof item === 'object' && !Array.isArray(item));

        if (isPrimitiveArray) {
          // 基础类型数组：直接排序后序列化
          const sorted = [...v].sort();
          return `[${sorted.map(item => JSON.stringify(item)).join(',')}]`;
        } if (isObjectArray) {
          // 对象数组：深度排序每个对象的键，然后按对象内容排序
          const sortedObjects = v.map((obj) => {
            if (typeof obj !== 'object' || obj === null) return obj;
            const sortedKeys = Object.keys(obj).sort();
            const sortedObj: Record<string, any> = {};
            sortedKeys.forEach((key) => {
              sortedObj[key] = obj[key];
            });
            return sortedObj;
          });

          // 按对象的JSON字符串排序整个数组
          const stringifiedObjects = sortedObjects.map(obj => JSON.stringify(obj));
          stringifiedObjects.sort();

          return `[${stringifiedObjects.join(',')}]`;
        }
        // 混合类型或嵌套数组：递归处理每个元素
        const parts = v.map(item => stableStringify(item));
        parts.sort();
        return `[${parts.join(',')}]`;
      }

      if (typeof v === 'object') {
        const keys = Object.keys(v).sort();
        const parts = keys.map(k => `${JSON.stringify(k)}:${stableStringify(v[k])}`);
        return `{${parts.join(',')}}`;
      }

      return JSON.stringify(v);
    };

    try {
      return stableStringify(cleaned);
    } catch (e) {
      // 如果序列化失败，使用更简单的比较方法
      try {
        return JSON.stringify(cleaned, (key, value) => {
          if (Array.isArray(value)) {
            return [...value].sort();
          }
          return value;
        });
      } catch (fallbackError) {
        return String(cleaned);
      }
    }
  };

  // 仅保留 a/b 同时存在的“公共字段”用于对比（对象递归取交集；数组按索引递归取交集）
  // - 若数组长度不同：超出对方长度的元素保留在结果里，用于检测增删
  // - 基础类型：直接返回 a
  const pickCommonFields = (a: any, b: any): any => {
    if (Array.isArray(a)) {
      if (!Array.isArray(b)) return a;
      return a.map((item, idx) => (idx < b.length ? pickCommonFields(item, b[idx]) : item));
    }
    if (a && typeof a === 'object' && !Array.isArray(a)) {
      if (!(b && typeof b === 'object') || Array.isArray(b)) return a;
      const next: Record<string, any> = {};
      Object.keys(a).forEach((k) => {
        if (Object.prototype.hasOwnProperty.call(b, k)) {
          next[k] = pickCommonFields(a[k], b[k]);
        }
      });
      return next;
    }
    return a;
  };

  const isSameByCommonFields = (currentVal: any, snapshotVal: any): boolean => {
    const currentPicked = pickCommonFields(currentVal, snapshotVal);
    const snapshotPicked = pickCommonFields(snapshotVal, currentVal);
    return stringifyForCompare(currentPicked) === stringifyForCompare(snapshotPicked);
  };

  const hasStepChanged = (fullParams: any, params: any): boolean => {
    const paramsKeys = Object.keys(params ?? {});
    if (!(isEditMode && initialFormData.value && paramsKeys.length > 0)) return false;

    return paramsKeys.some((key) => {
      const currentVal = fullParams?.[key];
      const snapshotVal = (initialFormData.value as any)?.[key];

      // 两侧任一侧不存在则不对比（只对比公共字段）
      if (_.isNil(currentVal) || _.isNil(snapshotVal)) return false;

      // 空值不触发"未提交修改"弹窗
      if (_.isNil(currentVal) || currentVal === '') return false;

      return !isSameByCommonFields(currentVal, snapshotVal);
    });
  };
  const handlePreviousStep = async (step: number, params: any) => {
    // 与下一步逻辑一致：对比“完整数据结构”中当前步骤回传字段的变化
    await ensureTagMapLoaded();
    const fullParams = normalizeSubmitParams(buildMergedFormData(params));
    const hasChanged = hasStepChanged(fullParams, params);

    if (hasChanged) {
      InfoBox({
        title: t('此步骤存在未提交的修改'),
        subTitle: t('本次将提交所有已修改的内容'),
        confirmText: t('提交'),
        cancelText: t('不提交'),
        closeIcon: false,
        headerAlign: 'center',
        contentAlign: 'center',
        footerAlign: 'center',
        onConfirm() {
          Object.assign(formData.value, params);
          if (isEditMode) {
            stayOnPageAfterSave.value = true;
            pendingStepAfterSave.value = normalizeStep(step);
            doSave();
          } else {
            currentStep.value = normalizeStep(step);
          }
        },
        onClose() {
          Object.assign(formData.value, params);
          currentStep.value = normalizeStep(step);
        },
      });
      return;
    }

    Object.assign(formData.value, params);
    currentStep.value = normalizeStep(step);
  };
  const handleNextStep = async (step: number, params: any) => {
    await ensureTagMapLoaded();
    const fullParams = normalizeSubmitParams(buildMergedFormData(params));
    const hasChanged = hasStepChanged(fullParams, params);


    if (hasChanged) {
      InfoBox({
        title: t('此步骤存在未提交的修改'),
        subTitle: t('本次将提交所有已修改的内容'),
        confirmText: t('提交'),
        cancelText: t('不提交'),
        closeIcon: false,
        headerAlign: 'center',
        contentAlign: 'center',
        footerAlign: 'center',
        onConfirm() {
          Object.assign(formData.value, params);
          if (isEditMode) {
            stayOnPageAfterSave.value = true;
            pendingStepAfterSave.value = normalizeStep(step);
            doSave();
          } else {
            currentStep.value = normalizeStep(step);
          }
        },
        onClose() {
          Object.assign(formData.value, params);
          currentStep.value = normalizeStep(step);
        },
      });
      return;
    }

    Object.assign(formData.value, params);
    currentStep.value = normalizeStep(step);
  };

  // 提交：合并当前步骤数据后提交，效果与「其他配置」的提交按钮一致
  const handleSaveCurrentStep = (params: any) => {
    Object.assign(formData.value, params);
    handleSubmit();
  };

  const handleCancel = () => {
    router.push({
      name: 'strategyList',
    });
  };

  onMounted(() => {
    if (isEditMode || isCloneMode) {
      fetchStrategyInfo({
        strategy_id: route.params.id,
      });
      // 编辑/克隆态预拉标签列表，用于提交前将 tags ID 转名称
      ensureTagMapLoaded();
    }
  });

</script>
<style scoped>
.strategy-upgrade-step {
  width: 650px;
  margin: 0 auto;
  transform: translateX(-86px);

  :deep(.bk-step ) {
    display: flex;

    .bk-step-content {
      display: flex;
    }
  }
}

.save-dialog-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 80px;
  padding: 16px 0;
}

.save-dialog-text {
  margin-top: 16px;
  font-size: 14px;
  color: #63656e;
  text-align: center;
}
</style>
