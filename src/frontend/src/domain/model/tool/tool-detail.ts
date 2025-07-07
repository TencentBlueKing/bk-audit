export default class ToolDetail {
  uid: string;
  name: string;
  tool_type: string;
  version: number;
  description: string;
  namespace: string;
  config: {
        sql: string;
        output_fields: Array<{
            raw_name: string;
            field_down: string;
            description: string;
            display_name: string;
        }>;
        input_variable: Array<{
            raw_name: string;
            required: boolean;
            description: string;
            display_name: string;
            field_category: string;
        }>;
        referenced_tables: Array<{
            alias: string | null;
            table_name: string;
        }>;
    };

  constructor(payload = {} as ToolDetail) {
    this.uid = payload.uid;
    this.name = payload.name;
    this.tool_type = payload.tool_type;
    this.version = payload.version;
    this.description = payload.description;
    this.namespace = payload.namespace;
    this.config = payload.config;
  }
}
