(function () {
  const gettextFn = window.gettext || function (text) { return text; };

  function parseJSON(value) {
    if (!value) {
      return null;
    }
    try {
      return JSON.parse(value);
    } catch (err) {
      console.warn("Invalid JSON condition:", err);
      return null;
    }
  }

  function defaultNode() {
    return {
      connector: "and",
      conditions: [],
    };
  }

  const DEFAULT_DRILL_PLACEHOLDER = '["path","to","value"]';

  function createElement(html) {
    const template = document.createElement("template");
    template.innerHTML = html.trim();
    return template.content.firstChild;
  }

  function getJsonFromTarget(root, attrName) {
    const targetId = root.dataset[attrName];
    if (!targetId) {
      return null;
    }
    const node = document.getElementById(targetId);
    if (!node) {
      return null;
    }
    try {
      return JSON.parse(node.textContent || "");
    } catch (error) {
      console.warn("Failed to parse JSON data for", targetId, error);
      return null;
    }
  }

  function applyFieldTypeOptions(select, fieldTypeOptions) {
    if (!select) {
      return;
    }
    select.innerHTML = "";
    (fieldTypeOptions || []).forEach((opt) => {
      const option = document.createElement("option");
      option.value = opt.value;
      option.textContent = opt.label || opt.value;
      select.appendChild(option);
    });
  }

  function parseFieldTypeOptions(raw) {
    return (raw || []).map((item) => ({
      value: item[0],
      label: item[1],
    }));
  }

  function updateDrillPanel(row, opts = {}) {
    const { preserveValues = false } = opts;
    const fieldElement = row.querySelector(".condition-field");
    const panel = row.querySelector(".condition-drill-panel");
    if (!fieldElement || !panel) {
      return;
    }
    
    // 如果是 input 元素，直接隐藏 drill panel
    if (fieldElement.tagName === "INPUT") {
      panel.style.display = "none";
      row.dataset.drillActive = "false";
      return;
    }
    
    // 以下逻辑仅适用于 select 元素
    const option = fieldElement.selectedOptions[0];
    const keysInput = panel.querySelector(".condition-drill-keys");
    const typeSelect = panel.querySelector(".condition-drill-type");
    const previousField = row.dataset.currentField || "";
    const currentField = fieldElement.value || "";
    const fieldChanged = previousField && previousField !== currentField;
    const supportsDrill = option?.dataset.supportsDrill === "true";
    row.dataset.currentField = currentField;

    if (!supportsDrill) {
      panel.style.display = "none";
      row.dataset.drillActive = "false";
      if (!preserveValues || fieldChanged) {
        keysInput.value = "";
        typeSelect.value = "";
      }
      return;
    }

    panel.style.display = "";
    row.dataset.drillActive = "true";
    const example = option.dataset.drillExamples;
    keysInput.placeholder = example && example !== "[]" ? example : DEFAULT_DRILL_PLACEHOLDER;
    if (fieldChanged && !preserveValues) {
      keysInput.value = "";
      typeSelect.value = "";
    }
    if (!typeSelect.value) {
      typeSelect.value = option.dataset.defaultReturnType || option.dataset.fieldType || "string";
    }
  }

  function createGroupElement(isRoot) {
      const group = createElement(
      `<div class="risk-where-group${isRoot ? " root" : ""}">
         <div class="group-header">
             <label>${gettextFn("连接符")}</label>
           <select class="group-connector">
             <option value="and">AND</option>
             <option value="or">OR</option>
           </select>
             ${isRoot ? "" : `<button type="button" class="button link delete-group">${gettextFn("删除组")}</button>`}
         </div>
         <div class="group-body">
           <div class="condition-items"></div>
           <div class="group-actions">
               <button type="button" class="button add-condition">${gettextFn("添加条件")}</button>
               <button type="button" class="button add-group">${gettextFn("添加子组")}</button>
           </div>
         </div>
       </div>`
    );
    return group;
  }

  function populateConditionRow(row, fieldOptions, operatorOptions, fieldTypeOptions, condition) {
    const fieldElement = row.querySelector(".condition-field");
    const fieldTypeSelect = row.querySelector(".condition-field-type");
    const operatorSelect = row.querySelector(".condition-operator");
    const valueInput = row.querySelector(".condition-value");
    const keysInput = row.querySelector(".condition-drill-keys");
    const typeSelect = row.querySelector(".condition-drill-type");

    // 如果是 select 元素，填充选项
    if (fieldElement.tagName === "SELECT") {
      fieldElement.innerHTML = "";
      fieldOptions.forEach((opt) => {
        const option = document.createElement("option");
        option.value = opt.raw_name;
        option.dataset.fieldType = opt.field_type;
        option.dataset.supportsDrill = String(!!opt.supports_drill);
        option.dataset.defaultReturnType = opt.default_return_type || opt.field_type;
        option.dataset.drillExamples = JSON.stringify(opt.drill_examples || []);
        option.textContent = opt.label || opt.name;
        fieldElement.appendChild(option);
      });
    }
    
    // 如果有字段类型选择器，填充选项
    if (fieldTypeSelect && fieldTypeOptions.length > 0) {
      fieldTypeSelect.innerHTML = "";
      fieldTypeOptions.forEach((opt) => {
        const option = document.createElement("option");
        option.value = opt.value;
        option.textContent = opt.label;
        fieldTypeSelect.appendChild(option);
      });
      // 设置默认值
      if (condition?.field?.field_type) {
        fieldTypeSelect.value = condition.field.field_type;
      } else {
        fieldTypeSelect.value = "string"; // 默认字符串类型
      }
    }
    
    operatorSelect.innerHTML = "";
    operatorOptions.forEach((opt) => {
      const option = document.createElement("option");
      option.value = opt[0];
      option.textContent = opt[1];
      operatorSelect.appendChild(option);
    });
    applyFieldTypeOptions(typeSelect, fieldTypeOptions);

    if (condition?.field?.raw_name) {
      fieldElement.value = condition.field.raw_name;
    }
    if (condition?.operator) {
      operatorSelect.value = condition.operator;
    }
    if (condition?.filters?.length) {
      valueInput.value = condition.filters.join(",");
    } else if (condition?.filter !== undefined) {
      valueInput.value = condition.filter;
    }
    if (condition?.field?.keys?.length) {
      keysInput.value = JSON.stringify(condition.field.keys);
    }
    if (condition?.field?.field_type) {
      typeSelect.value = condition.field.field_type;
    }
  }

  function createConditionRow(fieldOptions, operatorOptions, fieldTypeOptions, condition) {
    // 如果没有 fieldOptions，使用文本输入框；否则使用下拉选择框
    const useInputField = fieldOptions.length === 0;
    const fieldInputHtml = useInputField
      ? `<input type="text" class="condition-field" placeholder="${gettextFn("字段名，如 system_id")}" />`
      : `<select class="condition-field"></select>`;
    
    // 如果使用 input 字段，添加字段类型选择器
    const fieldTypeSelectHtml = useInputField && fieldTypeOptions.length > 0
      ? `<select class="condition-field-type" title="${gettextFn("字段类型")}"></select>`
      : '';
    
    const row = createElement(
        `<div class="condition-row" data-type="condition">
         ${fieldInputHtml}
         ${fieldTypeSelectHtml}
         <select class="condition-operator"></select>
           <input type="text" class="condition-value" placeholder="${gettextFn("值，多个使用逗号分隔")}" />
          <button type="button" class="button link delete-condition">${gettextFn("删除")}</button>
          <div class="condition-drill-panel">
              <label>${gettextFn("JSON Path (列表)")}</label>
              <input type="text" class="condition-drill-keys" placeholder='${DEFAULT_DRILL_PLACEHOLDER}' />
              <label>${gettextFn("返回类型")}</label>
              <select class="condition-drill-type"></select>
          </div>
       </div>`
    );
    populateConditionRow(row, fieldOptions, operatorOptions, fieldTypeOptions, condition);
    updateDrillPanel(row, { preserveValues: true });
    
    const fieldElement = row.querySelector(".condition-field");
    // 只为 select 元素添加 change 事件监听器
    if (fieldElement.tagName === "SELECT") {
      fieldElement.addEventListener("change", () => updateDrillPanel(row));
    }
    
    return row;
  }

  function renderGroup(targetContainer, node, fieldOptions, operatorOptions, fieldTypeOptions, isRoot) {
    const group = createGroupElement(isRoot);
    const connectorSelect = group.querySelector(".group-connector");
    connectorSelect.value = node.connector || "and";
    const itemsContainer = group.querySelector(".condition-items");
    (node.conditions || []).forEach((child) => {
      if (child.condition) {
        const row = createConditionRow(fieldOptions, operatorOptions, fieldTypeOptions, child.condition);
        itemsContainer.appendChild(row);
      } else if (child.conditions) {
        renderGroup(itemsContainer, child, fieldOptions, operatorOptions, fieldTypeOptions, false);
      }
    });
    targetContainer.appendChild(group);
  }

  function serializeGroup(groupElement) {
    const connector = groupElement.querySelector(".group-connector").value || "and";
    const node = {
      connector,
      conditions: [],
    };
    const items = groupElement.querySelectorAll(":scope > .group-body > .condition-items > *");
    items.forEach((child) => {
      if (child.classList.contains("condition-row")) {
        const fieldElement = child.querySelector(".condition-field");
        const fieldTypeSelect = child.querySelector(".condition-field-type");
        const field = fieldElement.value;
        const operator = child.querySelector(".condition-operator").value;
        const value = child.querySelector(".condition-value").value.trim();
        if (!field || !operator) {
          return;
        }
        const isMultiValue = ["include", "exclude", "between"].includes(operator);
        
        // 根据元素类型获取 field_type
        let fieldType = "string"; // 默认值
        if (fieldElement.tagName === "SELECT") {
          // 从下拉框的 selected option 获取
          fieldType = fieldElement.selectedOptions[0]?.dataset.fieldType || "string";
        } else if (fieldTypeSelect) {
          // 如果有字段类型选择器，使用其值
          fieldType = fieldTypeSelect.value || "string";
        }
        
        const condition = {
          field: {
            table: "t",
            raw_name: field,
            display_name: field,
            field_type: fieldType,
          },
          operator,
        };
        if (["isnull", "notnull"].includes(operator)) {
          // no value needed
        } else if (isMultiValue) {
          condition.filters = value ? value.split(",").map((item) => item.trim()).filter(Boolean) : [];
        } else {
          condition.filter = value;
        }
        
        // Drill 功能仅在 select 元素时支持
        if (fieldElement.tagName === "SELECT") {
          const fieldOption = fieldElement.selectedOptions[0];
          const supportsDrill = fieldOption?.dataset.supportsDrill === "true";
          const keysInput = child.querySelector(".condition-drill-keys");
          const typeSelect = child.querySelector(".condition-drill-type");
          const defaultFieldType = fieldOption?.dataset.fieldType || "string";
          condition.field.field_type = defaultFieldType;
          if (supportsDrill && keysInput) {
            const rawKeys = keysInput.value.trim();
            if (rawKeys) {
              let parsedKeys;
              try {
                parsedKeys = JSON.parse(rawKeys);
              } catch (error) {
                throw new Error(gettextFn('JSON path 需要是 JSON 数组，例如 ["login","ip"]'));
              }
              if (!Array.isArray(parsedKeys) || parsedKeys.some((item) => typeof item !== "string" || !item.trim())) {
                throw new Error(gettextFn("JSON path 需要是仅包含字符串的数组"));
              }
              condition.field.keys = parsedKeys.map((item) => item.trim());
              const selectedType = (typeSelect && typeSelect.value) || fieldOption.dataset.defaultReturnType || defaultFieldType;
              condition.field.field_type = selectedType || defaultFieldType;
            }
          }
        }
        
        node.conditions.push({"condition": condition});
      } else if (child.classList.contains("risk-where-group")) {
        node.conditions.push(serializeGroup(child));
      }
    });
    return node;
  }

  function setMode(root, mode) {
    root.dataset.mode = mode;
    const textarea = root.querySelector(".risk-where-condition-json");
    const builder = root.querySelector(".risk-where-condition-builder");
    if (mode === "json") {
      textarea.style.display = "block";
      textarea.style.minHeight = "160px";
      builder.style.display = "none";
    } else {
      textarea.style.display = "none";
      builder.style.display = "";
    }
  }

  function initWidget(root) {
    console.log('[WhereConditionWidget] initWidget called for:', root);
    
    // 强制重新初始化克隆的 Widget
    // Django Admin 的克隆会保留 data-* 属性，但不会克隆事件监听器
    // 通过检查 builder 是否有实际的事件监听器来判断
    const builder = root.querySelector(".risk-where-condition-builder");
    const isCloned = root.dataset.initialized === 'true' && !builder.onclick && !builder._hasClickListener;
    
    if (root.dataset.initialized === 'true' && !isCloned) {
      console.log('[WhereConditionWidget] Widget already properly initialized, skipping');
      return;
    }
    
    if (isCloned) {
      console.log('[WhereConditionWidget] Detected cloned widget, re-initializing');
      // 清除克隆的标记
      root.dataset.initialized = 'false';
      root.querySelectorAll('.risk-where-mode-btn').forEach(btn => {
        delete btn.dataset.listeners;
      });
    }
    
    console.log('[WhereConditionWidget] Initializing widget');
    root.dataset.initialized = 'true';

    const textarea = root.querySelector(".risk-where-condition-json");
    const groupsContainer = builder.querySelector(".risk-where-condition-groups");
    
    console.log('[WhereConditionWidget] Elements found:', {
      textarea: !!textarea,
      builder: !!builder,
      groupsContainer: !!groupsContainer
    });
    
    const fieldOptions = getJsonFromTarget(root, "fieldOptionsTarget") || [];
    const operatorOptions = getJsonFromTarget(root, "operatorOptionsTarget") || [];
    const fieldTypeOptions = parseFieldTypeOptions(getJsonFromTarget(root, "fieldTypeOptionsTarget") || []);
    
    console.log('[WhereConditionWidget] Options:', {
      fieldOptions: fieldOptions.length,
      operatorOptions: operatorOptions.length,
      fieldTypeOptions: fieldTypeOptions.length
    });
    
    const initialValue = parseJSON(textarea.value) || defaultNode();
    groupsContainer.innerHTML = "";
    renderGroup(groupsContainer, initialValue, fieldOptions, operatorOptions, fieldTypeOptions, true);
    setMode(root, "builder");

      root.querySelectorAll(".risk-where-mode-btn").forEach((btn) => {
      btn.dataset.listeners = "true"; // 标记已添加监听器
      btn.addEventListener("click", (event) => {
        event.preventDefault();
        const mode = btn.dataset.mode || "builder";
        if (mode === "builder") {
          // 切换到结构化模式：从 JSON 解析
          const parsed = parseJSON(textarea.value);
          if (parsed) {
            groupsContainer.innerHTML = "";
            renderGroup(groupsContainer, parsed, fieldOptions, operatorOptions, fieldTypeOptions, true);
          }
        } else if (mode === "json") {
          // 切换到 JSON 模式：序列化当前结构化数据
          let rootGroup = groupsContainer.querySelector(".risk-where-group.root");
          if (rootGroup) {
            try {
              const payload = serializeGroup(rootGroup);
              textarea.value = JSON.stringify(payload, null, 2);
            } catch (error) {
              console.error("序列化失败:", error);
            }
          }
        }
          setMode(root, mode);
          root.querySelectorAll(".risk-where-mode-btn").forEach((button) => button.classList.remove("active"));
          btn.classList.add("active");
      });
    });
      const defaultBtn = root.querySelector('.risk-where-mode-btn[data-mode="builder"]');
      if (defaultBtn) {
        defaultBtn.classList.add("active");
      }

    console.log('[WhereConditionWidget] Adding click listener to builder');
    const clickHandler = (event) => {
      const btn = event.target.closest("button");
      if (!btn) {
        return;
      }
      console.log('[WhereConditionWidget] Button clicked:', btn.className);
      const group = btn.closest(".risk-where-group");
        if (btn.classList.contains("add-condition")) {
        event.preventDefault();
        console.log('[WhereConditionWidget] Adding condition row');
        const row = createConditionRow(fieldOptions, operatorOptions, fieldTypeOptions);
        group.querySelector(".condition-items").appendChild(row);
      } else if (btn.classList.contains("add-group")) {
        event.preventDefault();
        console.log('[WhereConditionWidget] Adding group');
        renderGroup(
          group.querySelector(".condition-items"),
          defaultNode(),
          fieldOptions,
          operatorOptions,
          fieldTypeOptions,
          false
        );
      } else if (btn.classList.contains("delete-group")) {
        event.preventDefault();
        group.remove();
      } else if (btn.classList.contains("delete-condition")) {
        event.preventDefault();
        btn.closest(".condition-row").remove();
      }
    };
    builder.addEventListener("click", clickHandler);
    builder._hasClickListener = true; // 标记已添加事件监听器

    const adminForm = root.closest("form");
      if (adminForm) {
      adminForm.addEventListener("submit", (event) => {
        if (root.dataset.mode === "json") {
          return;
        }
          let rootGroup = groupsContainer.querySelector(".risk-where-group.root");
          if (!rootGroup) {
            renderGroup(groupsContainer, defaultNode(), fieldOptions, operatorOptions, fieldTypeOptions, true);
            rootGroup = groupsContainer.querySelector(".risk-where-group.root");
          }
          try {
            const payload = serializeGroup(rootGroup);
            textarea.value = JSON.stringify(payload, null, 2);
          } catch (error) {
            event.preventDefault();
            window.alert(error.message || gettextFn("请检查条件配置"));
          }
      });
    }
    
    console.log('[WhereConditionWidget] Widget initialized successfully');
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".risk-where-condition-widget").forEach((widget) => initWidget(widget));
  });

  // ============================================
  // 支持 Django Admin 内联表单动态添加
  // ============================================
  
  console.log('[WhereConditionWidget] Setting up dynamic initialization');
  
  // 方案 1: Django Admin 的 formset:added 事件（推荐）
  if (typeof django !== 'undefined' && django.jQuery) {
    console.log('[WhereConditionWidget] Django jQuery available, listening for formset:added');
    django.jQuery(document).on('formset:added', function(event, $row) {
      console.log('[WhereConditionWidget] formset:added event triggered, row:', $row[0]);
      $row.find('.risk-where-condition-widget').each(function() {
        console.log('[WhereConditionWidget] Found widget in new row, initializing');
        initWidget(this);
      });
    });
  } else {
    console.log('[WhereConditionWidget] Django jQuery not available, relying on MutationObserver');
  }

  // 方案 2: MutationObserver（兜底方案，适用于所有场景）
  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      mutation.addedNodes.forEach((node) => {
        if (node.nodeType === 1) { // Element node
          // 检查新添加的节点本身是否是 Widget
          if (node.classList && node.classList.contains('risk-where-condition-widget')) {
            console.log('[WhereConditionWidget] MutationObserver: widget node added directly');
            initWidget(node);
          }
          // 检查新添加的节点中是否包含 Widget
          if (node.querySelectorAll) {
            const widgets = node.querySelectorAll('.risk-where-condition-widget');
            if (widgets.length > 0) {
              console.log('[WhereConditionWidget] MutationObserver: found', widgets.length, 'widget(s) in added node');
              widgets.forEach((widget) => {
                initWidget(widget);
              });
            }
          }
        }
      });
    });
  });

  // 监听 body 下的所有子节点变化
  document.addEventListener("DOMContentLoaded", () => {
    console.log('[WhereConditionWidget] Starting MutationObserver');
    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
  });
})();
