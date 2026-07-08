/**
 * 平台工具创建/编辑 - 提交载荷组装与回显解析
 */
import _ from 'lodash';

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

  let resolvedSceneIds: number[] = [];
  let resolvedSystemIds: string[] = [];

  if (visibilityType === 'specific_scenes' || visibilityType === 'scenes_and_systems') {
    resolvedSceneIds = sceneIds;
  }
  if (visibilityType === 'specific_systems' || visibilityType === 'scenes_and_systems') {
    resolvedSystemIds = systemIds;
  }

  return {
    visibility_type: visibilityType,
    scene_ids: resolvedSceneIds,
    system_ids: resolvedSystemIds,
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
export function buildPlatformToolSubmitPayload(formData: FormData, isEditMode: boolean) {
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

  return data;
}
