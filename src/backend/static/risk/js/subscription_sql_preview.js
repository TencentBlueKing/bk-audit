(function () {
  const gettextFn = window.gettext || function (text) { return text; };

  function getCsrfToken() {
    const name = "csrftoken";
    const cookies = document.cookie ? document.cookie.split(";") : [];
    for (let cookie of cookies) {
      cookie = cookie.trim();
      if (cookie.startsWith(name + "=")) {
        return decodeURIComponent(cookie.substring(name.length + 1));
      }
    }
    return "";
  }

  function showMessage(container, message, level = "info") {
    container.innerHTML = "";
    if (!message) {
      return;
    }
    const div = document.createElement("div");
    div.className = `messagelist ${level}`;
    div.innerText = message;
    container.appendChild(div);
  }

  function toggleSection(section, visible) {
    if (!section) {
      return;
    }
    section.classList.toggle("hidden", !visible);
  }

  function formatDateTimeLocal(value) {
    if (!value) {
      return null;
    }
    const date = new Date(value);
    if (isNaN(date.getTime())) {
      return null;
    }
    return date.getTime();
  }

  function renderSQL(section, querySql, countSql) {
    section.querySelector(".query-sql").textContent = querySql || "";
    section.querySelector(".count-sql").textContent = countSql || "";
  }

  function renderResults(section, results = [], total) {
    const summary = section.querySelector(".results-summary");
    summary.textContent = gettextFn("返回 {count} 条记录，总计 {total} 条").replace("{count}", results.length).replace("{total}", total ?? "--");
    const wrapper = section.querySelector(".results-table-wrapper");
    wrapper.innerHTML = "";
    if (!results.length) {
      wrapper.textContent = gettextFn("暂无数据");
      return;
    }
    const table = document.createElement("table");
    table.className = "listing";
    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    Object.keys(results[0]).forEach((key) => {
      const th = document.createElement("th");
      th.textContent = key;
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);
    const tbody = document.createElement("tbody");
    results.forEach((item) => {
      const row = document.createElement("tr");
      Object.keys(results[0]).forEach((key) => {
        const cell = document.createElement("td");
        const value = item[key];
        cell.textContent = typeof value === "object" ? JSON.stringify(value) : value ?? "";
        row.appendChild(cell);
      });
      tbody.appendChild(row);
    });
    table.appendChild(tbody);
    wrapper.appendChild(table);
  }

  function bindPreviewForm() {
    const form = document.querySelector("#risk-preview-form");
    if (!form) {
      return;
    }
    const executeBtn = document.querySelector("#risk-preview-execute");
    const messages = document.querySelector("#risk-preview-messages");
    const sqlSection = document.querySelector("#risk-preview-sql");
    const resultSection = document.querySelector("#risk-preview-results");

    async function submit(execute) {
      const apiUrl = form.dataset.apiUrl;
    const page = parseInt(form.page.value, 10) || 1;
    const pageSize = parseInt(form.page_size.value, 10) || 10;
    const payload = {
      token: form.dataset.subscriptionToken,
      start_time: formatDateTimeLocal(form.start_time.value),
      end_time: formatDateTimeLocal(form.end_time.value),
      page,
      page_size: pageSize,
      raw: !execute,
    };
      if (!payload.start_time || !payload.end_time) {
        showMessage(messages, gettextFn("请填写完整的开始时间与结束时间"), "error");
        return;
      }
      showMessage(messages, gettextFn("请求中..."), "info");
      toggleSection(sqlSection, false);
      toggleSection(resultSection, false);
      try {
        const response = await fetch(apiUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrfToken(),
          },
          body: JSON.stringify(payload),
          credentials: "same-origin",
        });
        if (!response.ok) {
          throw new Error(gettextFn("接口返回错误：") + response.statusText);
        }
        const data = await response.json();
        showMessage(messages, gettextFn("生成成功"), "success");
        renderSQL(sqlSection, data.data?.query_sql || data.query_sql, data.data?.count_sql || data.count_sql);
        toggleSection(sqlSection, true);
        if (execute) {
          const results = data.data?.results || data.results || [];
          const total = data.data?.total ?? data.total;
          renderResults(resultSection, results, total);
          toggleSection(resultSection, true);
        }
      } catch (error) {
        console.error(error);
        showMessage(messages, error.message || String(error), "error");
      }
    }

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      submit(false);
    });
    if (executeBtn) {
      executeBtn.addEventListener("click", (event) => {
        event.preventDefault();
        submit(true);
      });
    }
  }

  document.addEventListener("DOMContentLoaded", bindPreviewForm);
})();
