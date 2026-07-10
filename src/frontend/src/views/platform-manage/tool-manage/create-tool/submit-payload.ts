/**
 * 平台工具创建/编辑 - 提交载荷组装与回显解析
 */
import _ from 'lodash';

import type { PlatformToolSubmitPayload } from '@model/tool/tool-manage-types';

import type { DefaultValueOverrides, FormData, SceneParamOverride, VisibilityScopePayload } from './types';

/** 将表单中的场景/系统参数覆盖配置转为后端 config.default_value_overrides 结构 */
export function buildDefaultValueOverrides(overrides?: Record<string, SceneParamOverride>): DefaultValueOverrides {
  const result: DefaultValueOverrides = {
    scenes: {},
    systems: {},
  };

  if (!overrides) {
    return result;
  }

  Object.values(overrides).forEach((item) => {
    if (!item.override_param_keys?.length) {
      return;
    }

    const paramValues: Record<string, any> = {};
    item.override_param_keys.forEach((key) => {
      const value = item.param_default_values?.[key];
      if (value !== undefined && value !== '') {
        paramValues[key] = value;
      }
    });

    if (!Object.keys(paramValues).length) {
      return;
    }

    const idKey = String(item.target_id);
    if (item.target_type === 'scene') {
      result.scenes![idKey] = paramValues;
    } else {
      result.systems![idKey] = paramValues;
    }
  });

  return result;
}

/** 将后端 config.default_value_overrides 解析为表单 scene_param_overrides */
export function parseDefaultValueOverrides(
  overrides: DefaultValueOverrides | undefined,
  sceneList: Array<{ id: number; name: string }>,
  systemList: Array<{ id: number | string; name: string }>,
): Record<string, SceneParamOverride> {
  const result: Record<string, SceneParamOverride> = {};

  if (overrides?.scenes) {
    Object.entries(overrides.scenes).forEach(([idStr, paramValues]) => {
      const id = Number(idStr);
      const keys = Object.keys(paramValues || {});
      if (!keys.length) {
        return;
      }
      result[`scene-${id}`] = {
        target_id: id,
        target_type: 'scene',
        target_name: sceneList.find(scene => scene.id === id)?.name || idStr,
        override_param_keys: keys,
        param_default_values: { ...paramValues },
      };
    });
  }

  if (overrides?.systems) {
    Object.entries(overrides.systems).forEach(([idStr, paramValues]) => {
      const keys = Object.keys(paramValues || {});
      if (!keys.length) {
        return;
      }
      result[`system-${idStr}`] = {
        target_id: idStr,
        target_type: 'system',
        target_name: systemList.find(system => String(system.id) === idStr)?.name || idStr,
        override_param_keys: keys,
        param_default_values: { ...paramValues },
      };
    });
  }

  return result;
}

/** 根据当前可见范围计算有效的参数覆盖目标 key（scene-{id} / system-{id}） */
function getValidOverrideTargetKeys(
  visibilityType: FormData['visibility_type'],
  sceneIds: number[],
  systemIds: string[],
): string[] {
  if (visibilityType === 'all_visible'
    || visibilityType === 'all_scenes'
    || visibilityType === 'all_systems') {
    return [];
  }
  if (!sceneIds.length && !systemIds.length) {
    return [];
  }

  const keys: string[] = [];
  if (visibilityType === 'specific_scenes' || visibilityType === 'scenes_and_systems') {
    sceneIds.forEach(id => keys.push(`scene-${id}`));
  }
  if (visibilityType === 'specific_systems' || visibilityType === 'scenes_and_systems') {
    systemIds.forEach(id => keys.push(`system-${id}`));
  }
  return keys;
}

type InputVariableItem = FormData['config']['input_variable'][number];

/** 读取第一步参数的原始默认值（与 scene-param-config 展示逻辑一致） */
export function getInputVariableDefault(param: Pick<InputVariableItem, 'default_value' | 'raw_default_value'>): any {
  if (param.default_value !== undefined && param.default_value !== '') {
    return param.default_value;
  }
  if (param.raw_default_value !== undefined && param.raw_default_value !== '') {
    return param.raw_default_value;
  }
  return param.default_value ?? '';
}

/** 构建第一步参数默认值快照，用于判断第二步覆盖值是否仍为第一步自动代入 */
export function buildInputDefaultSnapshot(inputVariables: InputVariableItem[]): Record<string, any> {
  const snapshot: Record<string, any> = {};
  (inputVariables || []).forEach((param) => {
    if (param.raw_name) {
      snapshot[param.raw_name] = getInputVariableDefault(param);
    }
  });
  return snapshot;
}

const isSameDefaultValue = (left: any, right: any) => _.isEqual(left, right);

/**
 * 将 scene_param_overrides 与第一步最新参数、当前可见范围对齐：
 * - 移除已删除的参数覆盖
 * - 移除已取消选中的场景/系统
 * - 更新目标名称
 * - 若覆盖值仍等于进入第二步前的第一步默认值，则同步为最新默认值
 */
export function reconcileSceneParamOverrides(
  overrides: Record<string, SceneParamOverride> | undefined,
  inputVariables: FormData['config']['input_variable'],
  visibilityType: FormData['visibility_type'],
  sceneIds: number[],
  systemIds: string[],
  sceneList: Array<{ id: number; name: string }>,
  systemList: Array<{ id: number | string; name: string }>,
  previousInputDefaults?: Record<string, any>,
): Record<string, SceneParamOverride> {
  const validTargetKeys = getValidOverrideTargetKeys(visibilityType, sceneIds, systemIds);
  if (!validTargetKeys.length) {
    return {};
  }

  const validParamKeys = new Set((inputVariables || []).map(v => v.raw_name).filter(Boolean));
  const existing = overrides || {};
  const result: Record<string, SceneParamOverride> = {};
  const currentDefaultMap = buildInputDefaultSnapshot(inputVariables || []);

  validTargetKeys.forEach((key) => {
    const isScene = key.startsWith('scene-');
    const rawId = key.replace(/^(scene|system)-/, '');
    const targetId = isScene ? Number(rawId) : rawId;
    const existingItem = existing[key];
    const overrideKeys = (existingItem?.override_param_keys || []).filter(k => validParamKeys.has(k));
    const paramDefaultValues: Record<string, any> = {};

    overrideKeys.forEach((paramKey) => {
      const newDefault = currentDefaultMap[paramKey];
      const existingValue = existingItem?.param_default_values?.[paramKey];

      if (existingValue === undefined) {
        paramDefaultValues[paramKey] = newDefault;
        return;
      }

      if (previousInputDefaults
        && isSameDefaultValue(existingValue, previousInputDefaults[paramKey])) {
        paramDefaultValues[paramKey] = newDefault;
        return;
      }

      paramDefaultValues[paramKey] = existingValue;
    });

    const targetName = isScene
      ? sceneList.find(scene => scene.id === targetId)?.name || String(targetId)
      : systemList.find(system => String(system.id) === String(targetId))?.name || String(targetId);

    result[key] = {
      target_id: targetId,
      target_type: isScene ? 'scene' : 'system',
      target_name: targetName,
      override_param_keys: overrideKeys,
      param_default_values: paramDefaultValues,
    };
  });

  return result;
}

/**
 * 是否需要在提交时传递 visibility。
 * 未选择任何可见范围时不传，由后端默认 all_visible。
 */
export function shouldSubmitVisibilityPayload(formData: Pick<FormData, 'visibility_type' | 'scene_ids' | 'system_ids'>): boolean {
  const visibilityType = formData.visibility_type;
  if (visibilityType === 'all_visible'
    || visibilityType === 'all_scenes'
    || visibilityType === 'all_systems') {
    return true;
  }
  return (formData.scene_ids?.length ?? 0) > 0 || (formData.system_ids?.length ?? 0) > 0;
}

const EMPTY_DEFAULT_VALUE_OVERRIDES: DefaultValueOverrides = { scenes: {}, systems: {} };

const ALL_VISIBLE_VISIBILITY: VisibilityScopePayload = {
  visibility_type: 'all_visible',
  scene_ids: [],
  system_ids: [],
};

/** 组装 visibility 对象（scene_ids / system_ids 数组，符合后端协议） */
export function buildVisibilityPayload(formData: Pick<FormData, 'visibility_type' | 'scene_ids' | 'system_ids'>): VisibilityScopePayload {
  const sceneIds = formData.scene_ids || [];
  const systemIds = (formData.system_ids || []).map(id => String(id));
  const visibilityType = formData.visibility_type;

  if (visibilityType === 'all_visible') {
    return {
      visibility_type: 'all_visible',
      scene_ids: [],
      system_ids: [],
    };
  }

  if (visibilityType === 'all_scenes') {
    return {
      visibility_type: 'all_scenes',
      scene_ids: [],
      system_ids: systemIds,
    };
  }

  if (visibilityType === 'all_systems') {
    return {
      visibility_type: 'all_systems',
      scene_ids: sceneIds,
      system_ids: [],
    };
  }

  if (visibilityType === 'specific_scenes') {
    return {
      visibility_type: 'specific_scenes',
      scene_ids: sceneIds,
      system_ids: [],
    };
  }

  if (visibilityType === 'specific_systems') {
    return {
      visibility_type: 'specific_systems',
      scene_ids: [],
      system_ids: systemIds,
    };
  }

  // scenes_and_systems：某一维 ids 为空表示该维度为「全部」
  return {
    visibility_type: 'scenes_and_systems',
    scene_ids: sceneIds,
    system_ids: systemIds,
  };
}

/** 将列表筛选选中的可见范围项转为查询参数（与 buildVisibilityPayload 规则一致） */
export function buildVisibilitySearchParams(selectedIds: string[]): VisibilityScopePayload | null {
  if (!selectedIds.length) {
    return null;
  }

  if (selectedIds.includes('all_visible')) {
    return buildVisibilityPayload({
      visibility_type: 'all_visible',
      scene_ids: [],
      system_ids: [],
    });
  }

  const sceneIds = selectedIds
    .filter(id => id.startsWith('scene_'))
    .map(id => Number(id.replace('scene_', '')))
    .filter(id => !Number.isNaN(id));
  const systemIds = selectedIds
    .filter(id => id.startsWith('system_'))
    .map(id => String(id.replace('system_', '')));
  const hasAllScenes = selectedIds.includes('all_scenes');
  const hasAllSystems = selectedIds.includes('all_systems');

  let visibilityType: FormData['visibility_type'];
  if (hasAllScenes && hasAllSystems) {
    visibilityType = 'all_visible';
  } else if (hasAllScenes) {
    visibilityType = 'all_scenes';
  } else if (hasAllSystems) {
    visibilityType = 'all_systems';
  } else if (sceneIds.length && !systemIds.length) {
    visibilityType = 'specific_scenes';
  } else if (!sceneIds.length && systemIds.length) {
    visibilityType = 'specific_systems';
  } else if (sceneIds.length && systemIds.length) {
    visibilityType = 'scenes_and_systems';
  } else {
    return null;
  }

  return buildVisibilityPayload({
    visibility_type: visibilityType,
    scene_ids: sceneIds,
    system_ids: systemIds,
  });
}

interface VisibilityLike {
  visibility_type?: string;
  scenes?: Record<string, Record<string, any>>;
  systems?: Record<string, Record<string, any>>;
  scene_ids?: number[];
  system_ids?: Array<number | string>;
}

/** 将 visibility 回填到表单平铺字段（兼容 scenes/systems 对象与 scene_ids/system_ids 数组） */
export function applyVisibilityToFormData(visibility?: VisibilityLike) {
  if (!visibility?.visibility_type) {
    return null;
  }

  const sceneIds = visibility.scenes
    ? Object.keys(visibility.scenes).map(id => Number(id))
    : (visibility.scene_ids || []);
  const systemIds = visibility.systems
    ? Object.keys(visibility.systems)
    : (visibility.system_ids || []).map(id => String(id));

  return {
    scene_ids: sceneIds,
    system_ids: systemIds,
    visibility_type: visibility.visibility_type as FormData['visibility_type'],
  };
}

/** 构建平台工具创建/更新请求体 */
export function buildPlatformToolSubmitPayload(formData: FormData, isEditMode: boolean): PlatformToolSubmitPayload {
  const data = _.cloneDeep(formData) as Record<string, any>;
  const hasVisibilitySelection = shouldSubmitVisibilityPayload(data as FormData);
  const defaultValueOverrides = hasVisibilitySelection
    ? buildDefaultValueOverrides(data.scene_param_overrides)
    : EMPTY_DEFAULT_VALUE_OVERRIDES;

  data.config = {
    ...data.config,
    default_value_overrides: defaultValueOverrides,
  };

  if (hasVisibilitySelection) {
    data.visibility = buildVisibilityPayload(data as FormData);
  } else if (isEditMode) {
    // 编辑时清空可见范围：后端仅在收到 visibility 时更新绑定，需显式重置为全部可见
    data.visibility = ALL_VISIBLE_VISIBILITY;
  }
  data.namespace = data.namespace || data.source || 'default';

  if (!isEditMode) {
    data.status = data.status || 'unpublished';
    data.version = data.version || 1;
  }

  delete data.source;
  delete data.users;
  delete data.is_bkvision;
  delete data.updated_at;
  delete data.updated_by;
  delete data.visibility_type;
  delete data.scene_ids;
  delete data.system_ids;
  delete data.scene_param_overrides;
  delete data.scope_id;
  delete data.scene_id;

  return data as PlatformToolSubmitPayload;
}
