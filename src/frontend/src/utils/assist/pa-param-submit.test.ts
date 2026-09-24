import {
  buildSubmitPaParams,
  isPaParamHidden,
  matchesPaParamHideCondition,
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
