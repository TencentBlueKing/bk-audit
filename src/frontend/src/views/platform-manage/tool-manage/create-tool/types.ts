/**
 * 工具创建/编辑 - 公共类型定义
 */

/** 场景/系统级参数默认值覆盖（后端 config.default_value_overrides） */
export interface DefaultValueOverrides {
  scenes?: Record<string, Record<string, any>>;
  systems?: Record<string, Record<string, any>>;
}

/** 可见范围（后端 visibility） */
export interface VisibilityScopePayload {
  visibility_type: FormData['visibility_type'];
  scene_ids: number[];
  system_ids: string[];
}

// 表单数据接口
export interface FormData {
  uid?: string; // 工具uid
  scene_id?: string; // 场景ID，场景级工具创建/编辑时使用
  scope_id?: string; // 作用域ID，用于接口传参
  source?: string;
  users?: string[];
  name: string;
  tags: string[];
  description: string;
  tool_type: string;
  updated_at: string;
  updated_by: string;
  is_bkvision: boolean;
  updated_time: string | null;
  data_search_config_type: string;
  // 可见范围（平铺字段，提交时组装为 visibility 对象）
  visibility_type: 'all_visible' | 'all_scenes' | 'all_systems' | 'specific_scenes' | 'specific_systems' | 'scenes_and_systems';
  scene_ids: number[]; // 审计场景 ID 列表
  system_ids: string[]; // 接入系统 ID 列表（与 meta 接口 id / system_id 一致）
  // 各场景/系统的参数覆盖配置 key: `${type}-${id}` (scene-1 / system-5)
  scene_param_overrides?: Record<string, SceneParamOverride>;
  // 提交时的 visibility 字段（符合后端协议）
  visibility?: VisibilityScopePayload;
  // 提交时的 namespace 字段（后端协议字段名，对应表单的 source）
  namespace?: string;
  config: {
    referenced_tables: Array<{
      table_name: string | null;
      alias: string | null;
      permission: {
        result: boolean;
      };
    }>;
    input_variable: Array<{
      raw_name: string;
      display_name: string;
      description: string;
      required: boolean;
      is_show?: boolean;
      field_category: string;
      default_value: any;
      raw_default_value?: any;
      is_default_value?: boolean;
      choices: Array<{
        key: string;
        name: string;
      }>;
    }>;
    output_fields: Array<{
      raw_name: string;
      display_name: string;
      description: string;
      drill_config: Array<{
        tool: {
          uid: string;
          version: number;
        };
        drill_name: string;
        config: Array<{
          source_field: string;
          target_value_type: string;
          target_value: string;
        }>;
      }>;
      enum_mappings: {
        collection_id: string;
        mappings: Array<{
          key: string;
          name: string;
        }>;
      };
    }>;
    sql: string;
    uid: string;
    default_value_overrides?: DefaultValueOverrides;
    output_config: {
      enable_grouping: boolean;
      groups: Array<{
        name: string;
        output_fields: any[];
      }>;
      enable_pagination?: boolean;
      pagination_config?: Array<{
        list_field: string;
        total_field: string;
        page_param: {
          raw_name: string;
          var_name: string;
        };
        page_size_param: {
          raw_name: string;
          var_name: string;
        };
        default_page: number;
        default_page_size: number;
        position: string;
      }>;
      result_schema?: {
        tree_data?: string | any[] | Record<string, any>;
      };
    };
  };
}

// 图表列表模型
export interface ChartListModel {
  uid: string;
  name: string;
  share: Array<{
    uid: string;
    name: string;
  }>;
}

// 场景/系统级参数覆盖配置
export interface SceneParamOverride {
  target_id: number | string; // 场景 scene_id（number）或系统 system_id（string）
  target_type: 'scene' | 'system';
  target_name: string;     // 显示名称
  override_param_keys: string[]; // 选中的参数 raw_name 列表
  param_default_values: Record<string, any>; // key=raw_name, value=默认值
}
