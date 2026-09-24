import {
  nextTick,
  reactive,
  watch,
} from 'vue';

import {
  buildSubmitPaParams,
  isPaParamHidden,
  isUserInput,
  matchesPaParamHideCondition,
  syncPaParamVisibility,
} from './pa-param-submit';

const params = {
  '${hidden}': { field: '', value: 'stale-value' },
  '${visible}': { field: '', value: '' },
  '${output}': { field: '', value: 'runtime-value' },
};
const metas = [
  {
    key: '${hidden}',
    source_type: 'custom',
    show_type: 'show',
    is_condition_hide: true,
    is_hide: true,
  },
  {
    key: '${visible}',
    source_type: 'custom',
    show_type: 'show',
    is_condition_hide: true,
    is_hide: false,
  },
  {
    key: '${output}',
    source_type: 'component_outputs',
    show_type: 'hide',
    is_condition_hide: false,
    is_hide: false,
  },
];
const expected = {
  '${visible}': { field: '', value: '' },
};
const actual = buildSubmitPaParams(params, metas);

if (JSON.stringify(actual) !== JSON.stringify(expected)) {
  throw new Error(`参数过滤结果不符合预期: ${JSON.stringify(actual)}`);
}

const missingControllerMatches = matchesPaParamHideCondition(
  { constant_key: '${missing}', operator: '=', value: '' },
  params,
);
if (missingControllerMatches) {
  throw new Error('控制参数缺失时不应命中隐藏条件');
}

const nullControllerMatches = matchesPaParamHideCondition(
  { constant_key: '${null}', operator: '=', value: '' },
  { '${null}': { field: '', value: null } },
);
if (nullControllerMatches) {
  throw new Error('控制参数值为 null 时不应命中隐藏条件');
}

const matchingControllerMatches = matchesPaParamHideCondition(
  { constant_key: '${visible}', operator: '=', value: '' },
  params,
);
if (!matchingControllerMatches) {
  throw new Error('控制参数存在且值相等时应命中隐藏条件');
}

const differentValueMatchesNotEqual = matchesPaParamHideCondition(
  { constant_key: '${visible}', operator: '!=', value: 'custom' },
  params,
);
if (!differentValueMatchesNotEqual) {
  throw new Error('控制参数值不同时应命中 != 隐藏条件');
}

const equalValueMatchesNotEqual = matchesPaParamHideCondition(
  { constant_key: '${visible}', operator: '!=', value: '' },
  params,
);
if (equalValueMatchesNotEqual) {
  throw new Error('控制参数值相同时不应命中 != 隐藏条件');
}

const missingControllerMatchesNotEqual = matchesPaParamHideCondition(
  { constant_key: '${missing}', operator: '!=', value: 'custom' },
  params,
);
if (missingControllerMatchesNotEqual) {
  throw new Error('控制参数 key 缺失时不应命中 != 隐藏条件');
}

const nullControllerMatchesNotEqual = matchesPaParamHideCondition(
  { constant_key: '${null}', operator: '!=', value: 'custom' },
  { '${null}': { field: '', value: null } },
);
if (!nullControllerMatchesNotEqual) {
  throw new Error('控制参数 key 存在且值为 null 时应命中 != 隐藏条件');
}

const anyConditionMatches = isPaParamHidden(
  [
    { constant_key: '${visible}', operator: '=', value: 'custom' },
    { constant_key: '${hidden}', operator: '!=', value: 'custom' },
  ],
  params,
);
if (!anyConditionMatches) {
  throw new Error('多条隐藏条件中任意一条命中时应隐藏参数');
}

const noConditionMatches = isPaParamHidden(
  [
    { constant_key: '${visible}', operator: '=', value: 'custom' },
    { constant_key: '${hidden}', operator: '!=', value: 'stale-value' },
  ],
  params,
);
if (noConditionMatches) {
  throw new Error('多条隐藏条件全部不命中时不应隐藏参数');
}

const arrayValueMatchesString = matchesPaParamHideCondition(
  { constant_key: '${array}', operator: '=', value: 'one' },
  { '${array}': { field: '', value: ['one'] } },
);
if (arrayValueMatchesString) {
  throw new Error('数组与字符串不应因 String 转换而被判定为相等');
}

if (!isUserInput({ source_type: 'custom', show_type: 'show' })) {
  throw new Error('custom + show 应被识别为用户入参');
}
if (isUserInput({ source_type: 'component_outputs', show_type: 'show' })) {
  throw new Error('非 custom 参数不应被识别为用户入参');
}

const editableParams: Record<string, { field?: unknown; value?: unknown }> = {
  '${controller}': { field: '', value: 'hide' },
  '${target}': { field: '', value: 'stale-value' },
};
const editableMetas = [
  {
    key: '${controller}',
    source_type: 'custom',
    show_type: 'show',
  },
  {
    key: '${target}',
    source_type: 'custom',
    show_type: 'show',
    hide_condition: [
      { constant_key: '${controller}', operator: '=', value: 'hide' },
    ],
    default_value: 'stale-value',
    is_hide: false,
  },
];
syncPaParamVisibility(editableParams, editableMetas);
if (!editableMetas[1].is_hide) {
  throw new Error('初次回显时应计算条件隐藏状态');
}
if (JSON.stringify(editableParams['${target}']) !== JSON.stringify({ field: '', value: 'stale-value' })) {
  throw new Error('隐藏参数应保留本地值，避免改变链式条件计算');
}
if (editableMetas[1].default_value !== 'stale-value') {
  throw new Error('隐藏参数不应改写本地 default_value');
}
if (Object.prototype.hasOwnProperty.call(buildSubmitPaParams(editableParams, editableMetas), '${target}')) {
  throw new Error('隐藏参数不应出现在提交 payload 中');
}

editableParams['${controller}'].value = 'show';
delete editableParams['${target}'];
syncPaParamVisibility(editableParams, editableMetas);
if (editableMetas[1].is_hide || !Object.prototype.hasOwnProperty.call(editableParams, '${target}')) {
  throw new Error('参数重新显示时应补建空参数对象');
}
if (JSON.stringify(editableParams['${target}']) !== JSON.stringify({ field: '', value: '' })) {
  throw new Error('重新显示的参数应使用空值初始化');
}

const chainedParams = {
  '${controller}': { field: '', value: 'hide' },
  '${first}': { field: '', value: 'old' },
  '${second}': { field: '', value: 'stale-value' },
};
const chainedMetas = [
  {
    key: '${first}',
    source_type: 'custom',
    show_type: 'show',
    hide_condition: [{ constant_key: '${controller}', operator: '=', value: 'hide' }],
    is_hide: false,
  },
  {
    key: '${second}',
    source_type: 'custom',
    show_type: 'show',
    hide_condition: [{ constant_key: '${first}', operator: '=', value: 'old' }],
    is_hide: false,
  },
];
syncPaParamVisibility(chainedParams, chainedMetas);
if (!chainedMetas.every(meta => meta.is_hide)) {
  throw new Error('链式条件应基于同步前快照计算，不应依赖元数据顺序');
}

const emptyValuePayload = buildSubmitPaParams(
  {
    '${empty}': { field: '', value: '' },
    '${zero}': { field: '', value: 0 },
    '${false}': { field: '', value: false },
    '${array}': { field: '', value: [] },
  },
  ['${empty}', '${zero}', '${false}', '${array}'].map(key => ({
    key,
    source_type: 'custom',
    show_type: 'show',
    is_hide: false,
  })),
);
if (Object.keys(emptyValuePayload).length !== 4) {
  throw new Error('已渲染参数的空值、0、false 和空数组都应保留');
}

const verifyReactiveVisibility = async () => {
  const reactiveParams = reactive({
    '${controller}': { field: '', value: 'hide' },
    '${first}': { field: '', value: 'old' },
    '${second}': { field: '', value: 'stale-value' },
  });
  const reactiveMetas = reactive([
    {
      key: '${first}',
      source_type: 'custom',
      show_type: 'show',
      hide_condition: [{ constant_key: '${controller}', operator: '=', value: 'hide' }],
      is_hide: false,
    },
    {
      key: '${second}',
      source_type: 'custom',
      show_type: 'show',
      hide_condition: [{ constant_key: '${first}', operator: '=', value: 'old' }],
      is_hide: false,
    },
  ]);
  const stop = watch(
    () => reactiveParams,
    paParams => syncPaParamVisibility(paParams, reactiveMetas),
    { deep: true },
  );
  syncPaParamVisibility(reactiveParams, reactiveMetas);
  await nextTick();
  await nextTick();
  stop();
  if (!reactiveMetas.every(meta => meta.is_hide)) {
    throw new Error('Vue deep watcher 更新周期后链式显隐结果不应改变');
  }
};

void verifyReactiveVisibility().catch((error) => {
  setTimeout(() => {
    throw error;
  });
});
