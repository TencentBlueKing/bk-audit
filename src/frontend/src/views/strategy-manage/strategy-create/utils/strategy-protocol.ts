/*
  TencentBlueKing is pleased to support the open source community by making
  蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
*/

import _ from 'lodash';
import type { RouteLocationNormalizedLoaded } from 'vue-router';

import { getStrategyBindingScope } from '../../utils/strategy-routes';

import { getSceneSystemParams } from '@/utils/assist/scene-system-params';

type FlatCondition = {
  field?: string;
  operator?: string;
  value?: string;
};

type DispatchConditions = Record<string, any> | FlatCondition[] | AssignConditionForm | undefined;

export type AssignConditionRow = {
  field: string;
  operator: string;
  value: string;
};

export type AssignConditionGroup = {
  connector: 'and' | 'or';
  conditions: AssignConditionRow[];
};

export type AssignConditionForm = {
  connector: 'and' | 'or';
  groups: AssignConditionGroup[];
};

export const createDefaultAssignConditionForm = (): AssignConditionForm => ({
  connector: 'and',
  groups: [{
    connector: 'and',
    conditions: [{ field: '', operator: 'eq', value: '' }],
  }],
});

export const isAssignConditionForm = (value: unknown): value is AssignConditionForm => (
  !!value
  && typeof value === 'object'
  && Array.isArray((value as AssignConditionForm).groups)
);

const parseDispatchConditionRow = (node: Record<string, any> | null | undefined): AssignConditionRow => {
  if (!node || typeof node !== 'object') {
    return { field: '', operator: 'eq', value: '' };
  }
  const nestedCondition = node.condition;
  const condition = (nestedCondition && typeof nestedCondition === 'object') ? nestedCondition : node;
  const { field, operator, filter, filters, value } = condition;
  const fieldName = typeof field === 'object' && field
    ? (field.raw_name || field.field_name || '')
    : (field ?? '');
  return {
    field: String(fieldName || ''),
    operator: operator ?? 'eq',
    value: filter ?? filters?.[0] ?? value ?? '',
  };
};

export type AssignWhereCondition = {
  field: Record<string, any>;
  operator: string;
  filter: string;
  filters: string[];
};

export type AssignWhereGroup = {
  connector: 'and' | 'or';
  index: number;
  conditions: Array<{ condition: AssignWhereCondition }>;
};

export type AssignWhere = {
  connector: 'and' | 'or';
  conditions: AssignWhereGroup[];
};

const emptyAssignField = () => ({
  table: '',
  raw_name: '',
  display_name: '',
  field_type: '',
  aggregate: null,
  keys: [] as string[],
  remark: '',
  spec_field_type: '',
  property: {},
});

export const createEmptyAssignWhere = (): AssignWhere => ({
  connector: 'and',
  conditions: [{
    connector: 'and',
    index: 0,
    conditions: [{
      condition: {
        field: emptyAssignField(),
        operator: '',
        filter: '',
        filters: [],
      },
    }],
  }],
});

const getConditionFieldRaw = (field: unknown) => {
  if (!field) return '';
  if (typeof field === 'string') return field;
  const record = field as Record<string, any>;
  return record.raw_name || record.field_name || record.value || '';
};

const findTableFieldByRaw = (
  raw: string,
  tableFields: Array<Record<string, any>> = [],
): Record<string, any> | undefined => {
  if (!raw) return undefined;
  const aliases = [
    raw,
    raw.replace(/^event_data\./, ''),
    raw.replace(/^event_basic\./, ''),
    raw.replace(/^event_evidence\./, ''),
    raw.replace(/^event\.(data|basic|evidence)\./, ''),
    raw.split('.').pop() || '',
  ].filter((item, index, list) => item && list.indexOf(item) === index);

  const matchField = (
    fields: Array<Record<string, any>>,
    visited: WeakSet<object> = new WeakSet(),
  ): Record<string, any> | undefined => {
    if (!Array.isArray(fields)) return undefined;
    const found = fields.find((field) => {
      if (!field || typeof field !== 'object') return false;
      const fieldRaw = field.raw_name || field.value || '';
      const fieldDisplay = field.display_name || field.label || field.alias || '';
      return aliases.includes(fieldRaw) || aliases.includes(fieldDisplay);
    });
    if (found) return found;
    return fields.reduce<Record<string, any> | undefined>((acc, field) => {
      if (acc || !field || typeof field !== 'object' || visited.has(field)) return acc;
      visited.add(field);
      const subKeys = field.property?.sub_keys;
      return Array.isArray(subKeys) ? matchField(subKeys, visited) : undefined;
    }, undefined);
  };

  return matchField(tableFields);
};

export const resolveAssignField = (
  field: unknown,
  tableFields: Array<Record<string, any>> = [],
) => {
  if (field && typeof field === 'object') {
    const current = field as Record<string, any>;
    const raw = getConditionFieldRaw(current);
    const found = findTableFieldByRaw(raw, tableFields);
    if (!found) {
      return {
        ...emptyAssignField(),
        ...current,
        raw_name: raw || current.raw_name || '',
        display_name: current.display_name || raw,
      };
    }
    const displayName = current.display_name && current.display_name !== raw
      ? current.display_name
      : (found.display_name || found.label || current.display_name || raw);
    return {
      ...found,
      ...current,
      table: current.table || found.table || '',
      raw_name: found.raw_name || found.value || raw,
      display_name: displayName,
      field_type: current.field_type || found.field_type || '',
      property: current.property || found.property || {},
    };
  }

  const raw = String(field || '');
  if (!raw) return emptyAssignField();
  const found = findTableFieldByRaw(raw, tableFields);
  if (found) {
    return {
      ...found,
      raw_name: found.raw_name || found.value || raw,
      display_name: found.display_name || found.label || raw,
    };
  }
  return {
    ...emptyAssignField(),
    raw_name: raw.split('.').pop() || raw,
    display_name: raw.split('.').pop() || raw,
  };
};

const emptyLeafAssignCondition = (): { condition: AssignWhereCondition } => ({
  condition: {
    field: emptyAssignField(),
    operator: '',
    filter: '',
    filters: [],
  },
});

const toLeafAssignCondition = (
  node: Record<string, any> | null | undefined,
  tableFields: Array<Record<string, any>> = [],
): { condition: AssignWhereCondition } => {
  if (!node || typeof node !== 'object') {
    return emptyLeafAssignCondition();
  }
  const nestedCondition = node.condition;
  const condition = (nestedCondition && typeof nestedCondition === 'object') ? nestedCondition : node;
  const operator = condition.operator || '';
  const sourceFilters = Array.isArray(condition.filters) ? condition.filters : [];
  let filter = String(condition.filter ?? '');
  let filters: string[] = sourceFilters.map((item: unknown) => String(item));
  if (operator === 'eq') {
    filter = String(condition.filter ?? condition.value ?? '');
    filters = [];
  } else if (!filters.length && condition.value) {
    filters = [String(condition.value)];
  }
  return {
    condition: {
      field: resolveAssignField(condition.field, tableFields),
      operator,
      filter,
      filters,
    },
  };
};

const isAssignWhere = (value: unknown): value is AssignWhere => (
  !!value
  && typeof value === 'object'
  && Array.isArray((value as AssignWhere).conditions)
  && !Array.isArray((value as AssignConditionForm).groups)
);

export const toAssignWhere = (
  conditions: DispatchConditions,
  tableFields: Array<Record<string, any>> = [],
): AssignWhere => {
  if (isAssignConditionForm(conditions)) {
    return {
      connector: conditions.connector,
      conditions: (conditions.groups || []).map((group, index) => ({
        connector: group?.connector || 'and',
        index,
        conditions: group?.conditions?.length
          ? group.conditions.map(row => toLeafAssignCondition({
            field: row?.field,
            operator: row?.operator,
            filter: row?.value,
            value: row?.value,
          }, tableFields))
          : [emptyLeafAssignCondition()],
      })),
    };
  }
  if (!conditions || typeof conditions !== 'object') return createEmptyAssignWhere();
  if (Array.isArray(conditions)) {
    return {
      connector: 'and',
      conditions: [{
        connector: 'and',
        index: 0,
        conditions: conditions.length
          ? conditions.map(item => toLeafAssignCondition(item, tableFields))
          : [emptyLeafAssignCondition()],
      }],
    };
  }
  const list = Array.isArray(conditions.conditions) ? conditions.conditions : [];
  if (!list.length) return createEmptyAssignWhere();
  const isNestedGroups = list.some((item: Record<string, any>) => Array.isArray(item?.conditions));
  if (isNestedGroups) {
    return {
      connector: (conditions.connector || 'and') as 'and' | 'or',
      conditions: list.map((group: Record<string, any>, index: number) => {
        const rows = (Array.isArray(group?.conditions) ? group.conditions : []).map((item: Record<string, any>) => (
          toLeafAssignCondition(item, tableFields)
        ));
        return {
          connector: (group?.connector || 'and') as 'and' | 'or',
          index: group?.index ?? index,
          conditions: rows.length ? rows : [emptyLeafAssignCondition()],
        };
      }),
    };
  }
  return {
    connector: (conditions.connector || 'and') as 'and' | 'or',
    conditions: [{
      connector: (conditions.connector || 'and') as 'and' | 'or',
      index: 0,
      conditions: list.map((item: Record<string, any>) => toLeafAssignCondition(item, tableFields)),
    }],
  };
};

export const enrichAssignWhereFields = (
  where: AssignWhere,
  tableFields: Array<Record<string, any>> = [],
): AssignWhere => {
  if (!where?.conditions?.length) return createEmptyAssignWhere();
  if (!tableFields.length) return where;
  return {
    connector: where.connector || 'and',
    conditions: where.conditions.map((group, index) => ({
      connector: group?.connector || 'and',
      index: group?.index ?? index,
      conditions: (group?.conditions?.length ? group.conditions : [emptyLeafAssignCondition()]).map(item => ({
        condition: {
          ...(item?.condition || emptyLeafAssignCondition().condition),
          field: resolveAssignField(item?.condition?.field, tableFields),
        },
      })),
    })),
  };
};

export const assignWhereToDispatch = (where: AssignWhere | undefined) => {
  if (!where?.conditions?.length) return {};
  const conditions = where.conditions
    .map((group, index) => ({
      connector: group.connector || 'and',
      index: group.index ?? index,
      conditions: (group.conditions || [])
        .filter((item) => {
          const raw = getConditionFieldRaw(item.condition?.field);
          return !!(raw && item.condition?.operator);
        })
        .map(item => ({
          condition: {
            field: item.condition.field,
            operator: item.condition.operator,
            filter: item.condition.filter ?? '',
            filters: item.condition.filters ?? [],
          },
        })),
    }))
    .filter(group => group.conditions.length);
  if (!conditions.length) return {};
  return {
    connector: where.connector || 'and',
    conditions,
  };
};

const hasValidAssignWhere = (where: unknown) => {
  if (!isAssignWhere(where)) return false;
  return (where.conditions || []).some(group => (group?.conditions || []).some((item) => {
    const raw = getConditionFieldRaw(item?.condition?.field);
    return !!(raw && item?.condition?.operator);
  }));
};

export const dispatchToAssignConditionForm = (conditions: DispatchConditions): AssignConditionForm => {
  if (isAssignConditionForm(conditions)) {
    return {
      connector: conditions.connector,
      groups: conditions.groups.map(group => ({
        connector: group.connector,
        conditions: group.conditions.map(row => ({ ...row })),
      })),
    };
  }
  if (!conditions || typeof conditions !== 'object') {
    return createDefaultAssignConditionForm();
  }
  if (Array.isArray(conditions)) {
    const rows = conditions.length
      ? conditions.map(item => parseDispatchConditionRow(item))
      : [{ field: '', operator: 'eq', value: '' }];
    return {
      connector: 'and',
      groups: [{ connector: 'and', conditions: rows }],
    };
  }
  const outerConnector = (conditions.connector || 'and') as 'and' | 'or';
  const list = Array.isArray(conditions.conditions) ? conditions.conditions : [];
  if (!list.length) {
    return createDefaultAssignConditionForm();
  }
  const isNestedGroups = list.some((item: Record<string, any>) => Array.isArray(item?.conditions));
  if (isNestedGroups) {
    return {
      connector: outerConnector,
      groups: list.map((group: Record<string, any>) => {
        const rows = (Array.isArray(group?.conditions) ? group.conditions : []).map(parseDispatchConditionRow);
        return {
          connector: (group?.connector || 'and') as 'and' | 'or',
          conditions: rows.length ? rows : [{ field: '', operator: 'eq', value: '' }],
        };
      }),
    };
  }
  const rows = list.map(parseDispatchConditionRow);
  return {
    connector: outerConnector,
    groups: [{
      connector: outerConnector,
      conditions: rows.length ? rows : [{ field: '', operator: 'eq', value: '' }],
    }],
  };
};

export const assignConditionFormToDispatch = (form: AssignConditionForm | undefined) => {
  if (!form?.groups?.length) return {};
  const groups = form.groups
    .map(group => ({
      connector: group.connector,
      conditions: group.conditions
        .filter(row => row.field && row.operator)
        .map(row => ({
          condition: {
            field: row.field,
            operator: row.operator,
            filter: row.value,
          },
        })),
    }))
    .filter(group => group.conditions.length);
  if (!groups.length) return {};

  if (groups.length === 1) {
    const [onlyGroup] = groups;
    return {
      connector: onlyGroup.connector,
      conditions: onlyGroup.conditions,
    };
  }

  return {
    connector: form.connector,
    conditions: groups.map(group => ({
      connector: group.connector,
      conditions: group.conditions,
    })),
  };
};

export const hasValidAssignCondition = (form: AssignConditionForm | AssignWhere | unknown) => {
  if (isAssignConditionForm(form)) {
    return form.groups.some(group => group.conditions.some(row => row.field && row.operator));
  }
  return hasValidAssignWhere(form);
};

type EventFieldConfigLike = {
  field_name?: string;
  display_name?: string;
  description?: string;
};

export type StrategyEventOutputField = {
  raw_name: string;
  display_name: string;
  description: string;
  target_field_type: 'basic' | 'data' | 'evidence';
};

export type StrategyEventFieldOption = {
  id: string;
  name: string;
};

/** 与单据展示（step2 event-table）outputFields 保持一致 */
export const buildStrategyEventOutputFields = (params: {
  event_basic_field_configs?: EventFieldConfigLike[];
  event_data_field_configs?: EventFieldConfigLike[];
  event_evidence_field_configs?: EventFieldConfigLike[];
  strategy_type?: string;
}): StrategyEventOutputField[] => {
  const mapField = (
    item: EventFieldConfigLike,
    targetFieldType: StrategyEventOutputField['target_field_type'],
  ): StrategyEventOutputField => ({
    raw_name: item.field_name || '',
    display_name: item.display_name || '',
    description: item.description || '',
    target_field_type: targetFieldType,
  });

  const basicFields = (params.event_basic_field_configs || []).map(item => mapField(item, 'basic'));
  const dataFields = (params.event_data_field_configs || []).map(item => mapField(item, 'data'));
  const evidenceFields = params.strategy_type === 'rule'
    ? (params.event_evidence_field_configs || []).map(item => mapField(item, 'evidence'))
    : [];

  return basicFields
    .concat(dataFields, evidenceFields)
    .filter(field => field.raw_name);
};

export const buildStrategyEventFieldOptions = (params: {
  event_basic_field_configs?: EventFieldConfigLike[];
  event_data_field_configs?: EventFieldConfigLike[];
  event_evidence_field_configs?: EventFieldConfigLike[];
  strategy_type?: string;
}): StrategyEventFieldOption[] => {
  const seen = new Set<string>();
  return buildStrategyEventOutputFields(params).reduce<StrategyEventFieldOption[]>((acc, field) => {
    if (seen.has(field.raw_name)) {
      return acc;
    }
    seen.add(field.raw_name);
    const label = formatFieldDisplayLabel(field.display_name, field.raw_name);
    acc.push({
      id: field.raw_name,
      name: label,
    });
    return acc;
  }, []);
};

type SelectFieldLike = {
  raw_name?: string;
  display_name?: string;
  value?: string;
  label?: string;
  alias?: string;
  field_name?: string;
  field_type?: string;
  spec_field_type?: string;
  property?: {
    sub_keys?: SelectFieldLike[];
  };
};

const pickFieldRawName = (field: SelectFieldLike) => (
  field.raw_name || field.field_name || field.value || ''
);

const pickFieldDisplayName = (field: SelectFieldLike) => (
  field.display_name || field.label || field.alias || ''
);

/** 收集数据源字段中文名，包含 JSON 嵌套路径（如 event.data.created_by） */
export const collectFieldDisplayNames = (
  fields: SelectFieldLike[] = [],
  parentPath = '',
): Map<string, string> => {
  const map = new Map<string, string>();
  const setName = (raw: string, display: string) => {
    if (!raw || !display || display === raw || map.has(raw)) {
      return;
    }
    map.set(raw, display);
  };

  fields.forEach((field) => {
    const raw = pickFieldRawName(field);
    const display = pickFieldDisplayName(field);
    const segment = field.value || raw;
    const path = parentPath ? `${parentPath}.${segment}` : raw;

    setName(raw, display);
    setName(path, display);
    if (segment && segment !== raw) {
      setName(segment, display);
    }

    const subKeys = field.property?.sub_keys;
    if (subKeys?.length) {
      const nextParent = parentPath ? path : (raw || segment);
      collectFieldDisplayNames(subKeys, nextParent).forEach((name, key) => setName(key, name));
    }
  });

  return map;
};

const resolveSelectFieldDisplayName = (
  rawName: string,
  ownDisplayName: string,
  displayNameByRaw: Map<string, string>,
) => {
  if (ownDisplayName && ownDisplayName !== rawName) {
    return ownDisplayName;
  }
  if (displayNameByRaw.has(rawName)) {
    return displayNameByRaw.get(rawName) || rawName;
  }
  const lastSegment = rawName.split('.').pop() || '';
  if (lastSegment && lastSegment !== rawName && displayNameByRaw.has(lastSegment)) {
    return displayNameByRaw.get(lastSegment) || rawName;
  }
  return ownDisplayName || rawName;
};

/** 展示格式：中文名(raw_name)；display_name 已带后缀时不再重复拼接 */
export const formatFieldDisplayLabel = (displayName?: string, rawName?: string) => {
  const name = String(displayName || '');
  const raw = String(rawName || '');
  if (!name) return raw;
  if (!raw || name === raw) return name;
  const suffix = `(${raw})`;
  if (name.endsWith(suffix)) return name;
  return `${name}${suffix}`;
};

/** 预期结果字段可能是 raw_name、中文名或 中文名(raw_name)，编辑回显都要认 */
export const isSameSelectField = (
  selectItem: SelectFieldLike,
  fieldKey?: string | null,
) => {
  if (fieldKey === undefined || fieldKey === null || fieldKey === '') return false;
  const key = String(fieldKey);
  const raw = pickFieldRawName(selectItem);
  const display = pickFieldDisplayName(selectItem);
  const formatted = formatFieldDisplayLabel(display, raw);
  return key === raw
    || key === display
    || key === formatted
    || (!!raw && (key.endsWith(`(${raw})`) || formatted === `${key}(${raw})`));
};

export const findSelectField = <T extends SelectFieldLike>(
  select: T[] = [],
  fieldKey?: string | null,
) => select.find(item => isSameSelectField(item, fieldKey));

const formatSelectFieldLabel = (displayName: string, rawName: string) => (
  formatFieldDisplayLabel(displayName, rawName)
);

/** 标准字段统一成「中文名(raw_name)」；用户自定义别名保持原样 */
const toStandardFieldDisplayName = (
  rawName: string,
  ownDisplayName: string,
  displayNameByRaw: Map<string, string>,
) => {
  const resolved = resolveSelectFieldDisplayName(rawName, ownDisplayName, displayNameByRaw);
  const lastSegment = rawName.split('.').pop() || '';
  const schemaDisplay = displayNameByRaw.get(rawName)
    || (lastSegment && lastSegment !== rawName ? displayNameByRaw.get(lastSegment) : '')
    || '';
  const formattedSchema = schemaDisplay
    ? formatFieldDisplayLabel(schemaDisplay, rawName)
    : '';
  const isStandard = !resolved
    || resolved === rawName
    || resolved === schemaDisplay
    || resolved === formattedSchema;
  if (isStandard) {
    return formatFieldDisplayLabel(schemaDisplay || resolved, rawName);
  }
  return resolved;
};

/** 用数据源字段回填中文名和类型图标（编辑回显的 select 不含 spec_field_type） */
export const enrichFieldDisplayNames = <T extends SelectFieldLike>(
  fields: T[] = [],
  tableFields: SelectFieldLike[] = [],
): T[] => {
  const displayNameByRaw = collectFieldDisplayNames(tableFields);
  return fields.map((field) => {
    const rawName = pickFieldRawName(field);
    if (!rawName) {
      return { ...field };
    }
    const schema = findTableFieldByRaw(rawName, tableFields as Array<Record<string, any>>);
    const subKeys = field.property?.sub_keys;
    const hasSubKeys = Array.isArray(subKeys) && subKeys.length > 0;
    return {
      ...field,
      display_name: toStandardFieldDisplayName(
        rawName,
        pickFieldDisplayName(field),
        displayNameByRaw,
      ),
      spec_field_type: field.spec_field_type
        || schema?.spec_field_type
        || schema?.field_type
        || field.field_type
        || '',
      field_type: field.field_type || schema?.field_type || '',
      property: hasSubKeys ? field.property : (schema?.property || field.property),
    };
  });
};

/** 分派规则命中条件：仅使用风险发现规则中的预期结果字段（configs.select）
 * 展示格式与风险发现规则一致：中文名(raw_name)；值为 raw_name，便于搜索中英文
 */
export const buildStrategySelectFieldOptions = (
  select: SelectFieldLike[] = [],
  tableFields: SelectFieldLike[] = [],
): StrategyEventFieldOption[] => {
  const displayNameByRaw = collectFieldDisplayNames([
    ...tableFields,
    ...select,
  ]);
  const seen = new Set<string>();
  return select.reduce<StrategyEventFieldOption[]>((acc, field) => {
    const rawName = pickFieldRawName(field);
    if (!rawName || seen.has(rawName)) {
      return acc;
    }
    seen.add(rawName);

    const displayName = resolveSelectFieldDisplayName(
      rawName,
      pickFieldDisplayName(field),
      displayNameByRaw,
    );

    acc.push({
      id: rawName,
      name: formatSelectFieldLabel(displayName, rawName),
    });
    return acc;
  }, []);
};

type RouteLike = Pick<RouteLocationNormalizedLoaded, 'name' | 'meta'> | null | undefined;

export const isEmptyDispatchConditions = (conditions: Record<string, any> | null | undefined) => {
  if (!conditions) return true;
  try {
    if (Array.isArray(conditions)) {
      return !conditions.some(item => getConditionFieldRaw(item?.field || item?.condition?.field));
    }
    if (isAssignConditionForm(conditions)) {
      return !hasValidAssignCondition(conditions);
    }
    if (!Array.isArray(conditions.conditions) || !conditions.conditions.length) return true;
    return !hasValidAssignWhere(toAssignWhere(conditions));
  } catch {
    return true;
  }
};

export const toDispatchConditions = (flat: FlatCondition[] | AssignConditionForm | Record<string, any> | undefined) => (
  assignWhereToDispatch(toAssignWhere(flat))
);

export const fromDispatchConditions = (conditions: DispatchConditions): FlatCondition[] => {
  const form = dispatchToAssignConditionForm(conditions);
  return form.groups.flatMap(group => group.conditions);
};

const mapAssignModeToDispatch = (mode?: string) => (mode === 'direct' ? 'direct' : 'after_confirm');

const mapDispatchModeToAssign = (mode?: string) => (mode === 'direct' ? 'direct' : 'confirm');

const toTargetSceneId = (rule: Record<string, any>) => {
  if (rule.target_scene_id !== undefined && rule.target_scene_id !== null && rule.target_scene_id !== '') {
    const num = Number(rule.target_scene_id);
    return Number.isNaN(num) ? rule.target_scene_id : num;
  }
  let ids = rule.scene_ids;
  if (!Array.isArray(ids)) {
    const hasSceneId = rule.scene_id !== undefined && rule.scene_id !== null && rule.scene_id !== '';
    ids = hasSceneId ? [rule.scene_id] : [];
  }
  const first = ids.find((id: string | number) => id !== '' && id !== null && id !== undefined);
  if (first === undefined) return undefined;
  const num = Number(first);
  return Number.isNaN(num) ? first : num;
};

const toDispatchRule = (rule: Record<string, any>, isDefault: boolean, isEdit = false) => {
  const conditions = isDefault
    ? {}
    : toDispatchConditions(rule.conditions);
  return {
    ...(isEdit && rule.rule_id ? { rule_id: rule.rule_id } : {}),
    rule_name: rule.rule_name || rule.name || (isDefault ? '默认分派规则' : '分派规则'),
    conditions,
    target_scene_id: toTargetSceneId(rule),
    processor: rule.processor ?? rule.processors ?? [],
    follower: rule.follower ?? rule.notice_users ?? [],
    confirmer: rule.confirmer ?? rule.confirmers ?? [],
    dispatch_mode: rule.dispatch_mode || mapAssignModeToDispatch(rule.assign_mode),
  };
};

/** 条件分派规则在前，默认分派规则在后，与页面顺序一致 */
const buildDispatchRules = (params: Record<string, any>, isPlatform: boolean) => {
  if (!isPlatform) {
    return [];
  }
  const isEdit = !!params.strategy_id;
  if (Array.isArray(params.dispatch_rules) && params.dispatch_rules.length && !params.assign_rules?.length) {
    return params.dispatch_rules.map((rule: Record<string, any>) => (
      toDispatchRule(rule, isEmptyDispatchConditions(toDispatchConditions(rule.conditions)), isEdit)
    ));
  }
  const list: Array<Record<string, any>> = [];
  (params.assign_rules || []).forEach((rule: Record<string, any>) => {
    list.push(toDispatchRule(rule, false, isEdit));
  });
  if (params.default_assign_rule && Object.keys(params.default_assign_rule).length) {
    list.push(toDispatchRule({
      ...params.default_assign_rule,
      name: params.default_assign_rule.rule_name || params.default_assign_rule.name || '默认分派规则',
    }, true, isEdit));
  }
  return list;
};

/** 从分派规则收集可见场景 ID（去重，保持出现顺序） */
const collectVisibilitySceneIds = (params: Record<string, any>): Array<string | number> => {
  const ids: Array<string | number> = [];
  const seen = new Set<string | number>();

  const addId = (value: unknown) => {
    const normalized = normalizeSceneId(value);
    if (normalized === undefined || seen.has(normalized)) {
      return;
    }
    seen.add(normalized);
    ids.push(normalized);
  };

  const addFromRule = (rule: Record<string, any> | undefined) => {
    if (!rule) return;
    if (Array.isArray(rule.scene_ids) && rule.scene_ids.length) {
      rule.scene_ids.forEach(addId);
      return;
    }
    addId(toTargetSceneId(rule));
  };

  (params.assign_rules || []).forEach(addFromRule);
  addFromRule(params.default_assign_rule);

  if (!ids.length && Array.isArray(params.dispatch_rules)) {
    params.dispatch_rules.forEach((rule: Record<string, any>) => {
      if (Array.isArray(rule.scene_ids) && rule.scene_ids.length) {
        rule.scene_ids.forEach(addId);
      } else {
        addId(toTargetSceneId(rule));
      }
    });
  }

  return ids;
};

const buildVisibility = (params: Record<string, any>, isPlatform: boolean) => {
  if (!isPlatform) {
    return undefined;
  }
  return {
    visibility_type: 'specific_scenes' as const,
    scene_ids: collectVisibilitySceneIds(params),
  };
};

/** 是否包含真正选了字段的过滤条件（空「请选择」占位不算） */
export const hasFilledWhereConditions = (where?: { conditions?: any[] } | null) => (
  (where?.conditions || []).some((group: any) => (
    (Array.isArray(group?.conditions) ? group.conditions : []).some((item: any) => {
      const field = item?.condition?.field ?? item?.field;
      return Boolean(getConditionFieldRaw(field));
    })
  ))
);

type WhereCandidate = { conditions?: unknown[] } | null | undefined;

const pickWhereValue = (...candidates: WhereCandidate[]) => (
  candidates.find(item => hasFilledWhereConditions(item)) ?? null
);

const pickWhereHaving = (rule: Record<string, any>, fallbackConfigs?: Record<string, any>) => {
  const configs = rule.configs || {};
  return {
    where: pickWhereValue(
      rule.conditions?.where,
      configs.where,
      fallbackConfigs?.where,
    ),
    having: pickWhereValue(
      rule.conditions?.having,
      configs.having,
      fallbackConfigs?.having,
    ),
  };
};

type WhereLike = {
  connector?: string;
  conditions?: Array<Record<string, any>> | unknown[];
};

const conditionGroupKey = (group: Record<string, any>) => {
  const children = Array.isArray(group?.conditions) ? group.conditions : [];
  const childKeys = children.map((child) => {
    const condition = child?.condition ?? child ?? {};
    const field = condition.field && typeof condition.field === 'object' ? condition.field : {};
    return [
      field.raw_name || '',
      field.aggregate ?? '',
      condition.operator || '',
      condition.filter ?? '',
      JSON.stringify(condition.filters ?? []),
    ].join('|');
  }).join(';');
  return `${group?.index ?? ''}::${childKeys}`;
};

/** 展示用：把 having 合并进 where，已存在的条件组不重复追加 */
export const mergeHavingIntoWhere = <T extends WhereLike>(
  where?: T | null,
  having?: T | null,
): T => {
  const connector = (where?.connector || having?.connector || 'and') as T['connector'];
  const whereConditions = [...((where?.conditions ?? []) as Array<Record<string, any>>)];
  const havingConditions = [...((having?.conditions ?? []) as Array<Record<string, any>>)];
  if (!havingConditions.length) {
    return {
      ...(where || {}),
      connector,
      conditions: whereConditions,
    } as T;
  }
  const seen = new Set(whereConditions.map(conditionGroupKey));
  const merged = [...whereConditions];
  havingConditions.forEach((group) => {
    const key = conditionGroupKey(group);
    if (seen.has(key)) {
      return;
    }
    seen.add(key);
    merged.push(group);
  });
  merged.sort((a, b) => (Number(a?.index) || 0) - (Number(b?.index) || 0));
  return {
    ...(where || {}),
    connector,
    conditions: merged,
  } as T;
};

/** 回显前把已混入 where 的 having 组拆回去，避免 setWhere 再合并一次变成三条 */
export const excludeHavingFromWhere = <T extends WhereLike>(
  where?: T | null,
  having?: T | null,
): T | null | undefined => {
  if (!where?.conditions?.length || !having?.conditions?.length) {
    return where;
  }
  const havingKeys = new Set((having.conditions as Array<Record<string, any>>).map(conditionGroupKey));
  return {
    ...where,
    conditions: (where.conditions as Array<Record<string, any>>)
      .filter(group => !havingKeys.has(conditionGroupKey(group))),
  } as T;
};

const buildRules = (params: Record<string, any>, isScene: boolean) => {
  const source = params.rules?.length
    ? params.rules
    : [{
      name: '规则1',
      risk_title: params.risk_title,
      risk_level: params.risk_level,
      risk_hazard: params.risk_hazard,
      risk_guidance: params.risk_guidance,
      configs: params.configs,
      processor: params.processor ?? params.processor_groups,
      follower: params.follower ?? params.notice_groups,
    }];
  const isEdit = !!params.strategy_id;

  const fallbackProcessor = params.processor_groups?.length
    ? params.processor_groups
    : (params.default_assign_rule?.processors
      ?? params.default_assign_rule?.processor
      ?? []);
  const fallbackFollower = params.notice_groups?.length
    ? params.notice_groups
    : (params.default_assign_rule?.notice_users
      ?? params.default_assign_rule?.follower
      ?? []);

  return source.map((rule: Record<string, any>, index: number) => {
    const { where, having } = pickWhereHaving(rule, index === 0 ? params.configs : undefined);
    let processor: Array<string | number> = [];
    let follower: Array<string | number> = [];
    if (isScene) {
      processor = rule.processor?.length ? rule.processor : fallbackProcessor;
      follower = rule.follower?.length ? rule.follower : fallbackFollower;
    }
    return {
      ...(isEdit && rule.rule_id ? { rule_id: rule.rule_id } : {}),
      rule_name: rule.rule_name || rule.name || `规则${index + 1}`,
      conditions: {
        where,
        having,
      },
      risk_title: rule.risk_title ?? '',
      risk_level: rule.risk_level ?? 'HIGH',
      risk_hazard: rule.risk_hazard ?? '',
      risk_guidance: rule.risk_guidance ?? '',
      processor,
      follower,
    };
  });
};

const stripConfigs = (configs: Record<string, any> | undefined) => {
  if (!configs) return configs || {};
  const next = _.cloneDeep(configs);
  delete next.where;
  delete next.having;
  delete next.table_fields;
  return next;
};

const normalizeSceneId = (value: unknown): string | number | undefined => {
  if (value === undefined || value === null || value === '') {
    return undefined;
  }
  const num = Number(value);
  return Number.isNaN(num) ? value as string | number : num;
};

/** 场景策略提交时解析 scene_id（兼容详情未返回、表单为空字符串等情况） */
export const resolveStrategySceneId = (
  params: Record<string, any>,
  route?: RouteLike,
): string | number | undefined => (
  normalizeSceneId(params.scene_id)
  ?? normalizeSceneId(getStrategyBindingScope(route).scene_id)
  ?? normalizeSceneId(getSceneSystemParams().scope_id)
);

/** 新建/编辑提交：将向导表单转为新协议 body */
export const buildStrategyCreatePayload = (
  params: Record<string, any>,
  route?: RouteLike,
) => {
  const next = _.cloneDeep(params);
  const scope = getStrategyBindingScope(route);
  const isEdit = !!next.strategy_id;
  const bindingType = params.binding_type || scope.binding_type;
  const isSceneBinding = bindingType === 'scene_binding';

  if (!isEdit) {
    next.binding_type = bindingType;
    if (isSceneBinding) {
      const sceneId = resolveStrategySceneId(params, route);
      if (sceneId !== undefined) {
        next.scene_id = sceneId;
      } else {
        delete next.scene_id;
      }
    } else {
      delete next.scene_id;
    }
  } else {
    delete next.binding_type;
    delete next.bind_type;
    delete next.scene_id;
  }

  const isScene = isSceneBinding;

  const isRuleStrategy = !next.strategy_type || next.strategy_type === 'rule';
  if (isRuleStrategy) {
    next.rules = buildRules(next, isScene);
    next.configs = stripConfigs(next.configs);
    // 风险详情 / 列表 / 导出仍读取策略级字段，需与发现规则保持一致
    const firstRule = next.rules[0];
    if (firstRule) {
      next.risk_title = firstRule.risk_title ?? next.risk_title ?? '';
      next.risk_level = firstRule.risk_level ?? next.risk_level ?? 'HIGH';
      next.risk_hazard = firstRule.risk_hazard ?? next.risk_hazard ?? '';
      next.risk_guidance = firstRule.risk_guidance ?? next.risk_guidance ?? '';
    }
  }

  next.dispatch_rules = buildDispatchRules(next, scope.isPlatform);

  const visibility = buildVisibility(next, scope.isPlatform);
  if (visibility) {
    next.visibility = visibility;
  } else {
    delete next.visibility;
  }

  delete next.assign_rules;
  delete next.default_assign_rule;
  delete next.processor_groups;
  delete next.notice_groups;
  delete next.visibility_type;
  delete next.scene_ids;
  delete next.system_ids;

  return next;
};

const fromDispatchRuleToForm = (rule: Record<string, any> = {}) => ({
  rule_id: rule.rule_id,
  name: rule.rule_name || rule.name,
  conditions: toAssignWhere(rule.conditions),
  scene_ids: rule.target_scene_id !== undefined && rule.target_scene_id !== null && rule.target_scene_id !== ''
    ? [rule.target_scene_id]
    : (rule.scene_ids ?? []),
  processors: rule.processor ?? rule.processors ?? [],
  notice_users: rule.follower ?? rule.notice_users ?? [],
  assign_mode: mapDispatchModeToAssign(rule.dispatch_mode || rule.assign_mode),
  confirmers: rule.confirmer ?? rule.confirmers ?? [],
});

/** 详情回填：新协议字段转回向导内部结构 */
export const parseStrategyDetailToForm = (d: Record<string, any>) => {
  let assignRules = d.assign_rules;
  let defaultAssignRule = d.default_assign_rule;

  if (d.dispatch_rules?.length) {
    try {
      const mapped = d.dispatch_rules
        .filter((item: Record<string, any>) => !!item)
        .map((item: Record<string, any>) => fromDispatchRuleToForm(item));
      const defaultIndex = d.dispatch_rules.findIndex((item: Record<string, any>) => (
        isEmptyDispatchConditions(item?.conditions)
      ));
      const resolvedDefaultIndex = defaultIndex >= 0 ? defaultIndex : mapped.length - 1;
      defaultAssignRule = mapped[resolvedDefaultIndex];
      assignRules = mapped.filter((_: Record<string, any>, index: number) => index !== resolvedDefaultIndex);
    } catch {
      assignRules = d.assign_rules;
      defaultAssignRule = d.default_assign_rule;
    }
  }

  const rules = (d.rules?.length ? d.rules : null)?.map((rule: Record<string, any>, index: number) => ({
    id: rule.id ?? rule.rule_id ?? rule.strategy_rule_id,
    rule_id: rule.rule_id ?? rule.id ?? rule.strategy_rule_id,
    name: rule.rule_name || rule.name || `规则${index + 1}`,
    rule_name: rule.rule_name || rule.name,
    risk_title: rule.risk_title ?? d.risk_title ?? '',
    risk_level: rule.risk_level ?? d.risk_level ?? 'HIGH',
    risk_hazard: rule.risk_hazard ?? d.risk_hazard ?? '',
    risk_guidance: rule.risk_guidance ?? d.risk_guidance ?? '',
    processor: rule.processor ?? [],
    follower: rule.follower ?? [],
    conditions: {
      where: rule.conditions?.where ?? rule.configs?.where ?? (index === 0 ? d.configs?.where : null),
      having: rule.conditions?.having ?? rule.configs?.having ?? (index === 0 ? d.configs?.having : null),
    },
    configs: {
      ...(d.configs || {}),
      ...(rule.configs || {}),
      where: rule.conditions?.where ?? rule.configs?.where ?? (index === 0 ? d.configs?.where : undefined),
      having: rule.conditions?.having ?? rule.configs?.having ?? (index === 0 ? d.configs?.having : undefined),
    },
  })) ?? (d.configs?.where || d.risk_title ? [{
    name: '规则1',
    risk_title: d.risk_title ?? '',
    risk_level: d.risk_level ?? 'HIGH',
    risk_hazard: d.risk_hazard ?? '',
    risk_guidance: d.risk_guidance ?? '',
    conditions: {
      where: d.configs?.where ?? null,
      having: d.configs?.having ?? null,
    },
  }] : undefined);

  const firstRule = rules?.[0];
  const bindingType = d.binding_type;
  const sceneId = normalizeSceneId(d.scene_id)
    ?? (bindingType === 'scene_binding' || bindingType === undefined
      ? normalizeSceneId(getSceneSystemParams().scope_id)
      : undefined);
  return {
    rules,
    assign_rules: assignRules ?? [],
    default_assign_rule: defaultAssignRule ?? {},
    dispatch_rules: d.dispatch_rules,
    binding_type: bindingType,
    visibility: d.visibility,
    scene_id: sceneId,
    risk_title: firstRule?.risk_title ?? d.risk_title ?? '',
    risk_level: firstRule?.risk_level ?? d.risk_level ?? '',
    risk_hazard: firstRule?.risk_hazard ?? d.risk_hazard ?? '',
    risk_guidance: firstRule?.risk_guidance ?? d.risk_guidance ?? '',
  };
};
