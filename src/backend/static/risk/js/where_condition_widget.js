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
    const fieldSelect = row.querySelector(".condition-field");
    const panel = row.querySelector(".condition-drill-panel");
    if (!fieldSelect || !panel) {
      return;
    }
    const option = fieldSelect.selectedOptions[0];
    const keysInput = panel.querySelector(".condition-drill-keys");
    const typeSelect = panel.querySelector(".condition-drill-type");
    const previousField = row.dataset.currentField || "";
    const currentField = fieldSelect.value || "";
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
    const fieldSelect = row.querySelector(".condition-field");
    const operatorSelect = row.querySelector(".condition-operator");
    const valueInput = row.querySelector(".condition-value");
    const keysInput = row.querySelector(".condition-drill-keys");
    const typeSelect = row.querySelector(".condition-drill-type");

    fieldSelect.innerHTML = "";
    fieldOptions.forEach((opt) => {
      const option = document.createElement("option");
      option.value = opt.raw_name;
      option.dataset.fieldType = opt.field_type;
      option.dataset.supportsDrill = String(!!opt.supports_drill);
      option.dataset.defaultReturnType = opt.default_return_type || opt.field_type;
      option.dataset.drillExamples = JSON.stringify(opt.drill_examples || []);
      option.textContent = opt.label || opt.name;
      fieldSelect.appendChild(option);
    });
    operatorSelect.innerHTML = "";
    operatorOptions.forEach((opt) => {
      const option = document.createElement("option");
      option.value = opt[0];
      option.textContent = opt[1];
      operatorSelect.appendChild(option);
    });
    applyFieldTypeOptions(typeSelect, fieldTypeOptions);

    if (condition?.field?.raw_name) {
      fieldSelect.value = condition.field.raw_name;
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
    const row = createElement(
        `<div class="condition-row" data-type="condition">
         <select class="condition-field"></select>
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
    row.querySelector(".condition-field").addEventListener("change", () => updateDrillPanel(row));
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
        const field = child.querySelector(".condition-field").value;
        const operator = child.querySelector(".condition-operator").value;
        const value = child.querySelector(".condition-value").value.trim();
        if (!field || !operator) {
          return;
        }
        const isMultiValue = ["include", "exclude", "between"].includes(operator);
        const condition = {
          field: {
            table: "t",
            raw_name: field,
            display_name: field,
            field_type: child.querySelector(".condition-field").selectedOptions[0]?.dataset.fieldType || "string",
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
        const fieldOption = child.querySelector(".condition-field").selectedOptions[0];
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
    const textarea = root.querySelector(".risk-where-condition-json");
    const builder = root.querySelector(".risk-where-condition-builder");
    const groupsContainer = builder.querySelector(".risk-where-condition-groups");
    const fieldOptions = getJsonFromTarget(root, "fieldOptionsTarget") || [];
    const operatorOptions = getJsonFromTarget(root, "operatorOptionsTarget") || [];
    const fieldTypeOptions = parseFieldTypeOptions(getJsonFromTarget(root, "fieldTypeOptionsTarget") || []);
    const initialValue = parseJSON(textarea.value) || defaultNode();
    groupsContainer.innerHTML = "";
    renderGroup(groupsContainer, initialValue, fieldOptions, operatorOptions, fieldTypeOptions, true);
    setMode(root, "builder");

      root.querySelectorAll(".risk-where-mode-btn").forEach((btn) => {
      btn.addEventListener("click", (event) => {
        event.preventDefault();
        const mode = btn.dataset.mode || "builder";
        if (mode === "builder") {
          const parsed = parseJSON(textarea.value);
          if (parsed) {
            groupsContainer.innerHTML = "";
            renderGroup(groupsContainer, parsed, fieldOptions, operatorOptions, fieldTypeOptions, true);
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

    builder.addEventListener("click", (event) => {
      const btn = event.target.closest("button");
      if (!btn) {
        return;
      }
      const group = btn.closest(".risk-where-group");
        if (btn.classList.contains("add-condition")) {
        event.preventDefault();
        const row = createConditionRow(fieldOptions, operatorOptions, fieldTypeOptions);
        group.querySelector(".condition-items").appendChild(row);
      } else if (btn.classList.contains("add-group")) {
        event.preventDefault();
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
    });

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
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".risk-where-condition-widget").forEach((widget) => initWidget(widget));
  });
})();
