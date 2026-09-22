/* Клиент чата Content Radar: без сборки и внешних зависимостей.
   Ответ агента приходит в Markdown, поэтому рендерим его локальным парсером:
   сначала экранируем HTML, потом применяем разметку — так нельзя внедрить теги. */

const form = document.getElementById("form");
const input = document.getElementById("input");
const send = document.getElementById("send");
const messages = document.getElementById("messages");
const badges = document.getElementById("badges");
const presets = document.getElementById("presets");
const log = document.getElementById("log");

const SOURCES = ["youtube", "vk", "instagram"];

const PRESETS = [
  "Что сейчас залетает в вайб-кодинге? Проверь YouTube, VK и Instagram",
  "Найди 5 постов по хештегу #aiagents в Instagram",
  "Найди 20 лучших роликов про AI-агентов за 30 дней",
];

/* ---------- Markdown ---------- */

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/* Инлайновая разметка: код, ссылки, жирный, курсив. */
function renderInline(text) {
  let out = escapeHtml(text);
  const parts = out.split(/(<code>[\s\S]*?<\/code>)/g);
  // Внутри инлайн-кода разметку не трогаем, поэтому сначала прячем его в маркеры.
  const vault = [];
  out = out.replace(/`([^`\n]+)`/g, (_, code) => {
    vault.push(code);
    return `\u0000${vault.length - 1}\u0000`;
  });
  out = out.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    (_, label, url) =>
      `<a href="${url}" target="_blank" rel="noopener noreferrer">${label}</a>`,
  );
  out = out.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/__([^_\n]+)__/g, "<strong>$1</strong>");
  out = out.replace(/(^|[\s(])\*([^*\n]+)\*/g, "$1<em>$2</em>");
  out = out.replace(/(^|[\s(])_([^_\n]+)_/g, "$1<em>$2</em>");
  // Голые ссылки делаем кликабельными (уже готовые <a ...> не задеваем).
  out = out.replace(
    /(^|[\s(])(https?:\/\/[^\s<)]+)/g,
    (_, pre, url) =>
      `${pre}<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`,
  );
  out = out.replace(/\u0000(\d+)\u0000/g, (_, index) => `<code>${vault[Number(index)]}</code>`);
  return out;
}

function splitTableRow(line) {
  return line
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function renderTable(header, rows) {
  const head = header.map((cell) => `<th>${renderInline(cell)}</th>`).join("");
  const body = rows
    .map(
      (row) =>
        `<tr>${row.map((cell) => `<td>${renderInline(cell)}</td>`).join("")}</tr>`,
    )
    .join("");
  return `<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function isTableSeparator(line) {
  return Boolean(line) && /^\|[\s:|-]+\|$/.test(line.trim());
}

/* Блочная разметка: заголовки, списки, цитаты, код, таблицы, абзацы. */
function renderMarkdown(markdown) {
  const lines = String(markdown || "").replace(/\r\n?/g, "\n").split("\n");
  const out = [];
  // list — тег текущего списка верхнего уровня; innerUl — открыт ли вложенный ul.
  let list = null;
  let innerUl = false;
  let code = null;
  let quote = [];
  let para = [];

  const flushPara = () => {
    if (para.length) {
      out.push(`<p>${para.map(renderInline).join("<br>")}</p>`);
      para = [];
    }
  };
  const flushQuote = () => {
    if (quote.length) {
      out.push(`<blockquote>${quote.map(renderInline).join("<br>")}</blockquote>`);
      quote = [];
    }
  };
  const closeList = () => {
    if (!list) return;
    if (innerUl) {
      out.push("</ul>");
      innerUl = false;
    }
    out.push(`</${list}>`);
    list = null;
  };
  const flushAll = () => {
    flushPara();
    flushQuote();
    closeList();
  };

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    const trimmed = line.trim();

    if (code !== null) {
      if (trimmed.startsWith("```")) {
        out.push(`<pre><code>${escapeHtml(code.join("\n"))}</code></pre>`);
        code = null;
      } else {
        code.push(line);
      }
      continue;
    }
    if (trimmed.startsWith("```")) {
      flushAll();
      code = [];
      continue;
    }
    if (!trimmed) {
      // Пустая строка не должна разрывать список: модели часто разделяют
      // пункты пустой строкой («loose list»), и без этого каждый пункт
      // начинал бы нумерацию заново — «1, 1, 1» вместо «1, 2, 3».
      flushPara();
      flushQuote();
      continue;
    }

    if (trimmed.startsWith("|") && isTableSeparator(lines[i + 1])) {
      flushAll();
      const header = splitTableRow(trimmed);
      const rows = [];
      i += 2;
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        rows.push(splitTableRow(lines[i].trim()));
        i += 1;
      }
      i -= 1;
      out.push(renderTable(header, rows));
      continue;
    }

    const heading = trimmed.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      flushAll();
      // Агент чаще всего использует "###" для секций верхнего уровня, поэтому
      // уровни 2–3 сжимаем до h3: иначе заголовки выглядят как обычный текст.
      const marks = heading[1].length;
      const level = marks === 1 ? 2 : marks <= 3 ? 3 : 4;
      out.push(`<h${level}>${renderInline(heading[2])}</h${level}>`);
      continue;
    }

    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
      flushAll();
      out.push("<hr>");
      continue;
    }

    if (trimmed.startsWith(">")) {
      flushPara();
      closeList();
      quote.push(trimmed.replace(/^>\s?/, ""));
      continue;
    }

    const bullet = trimmed.match(/^[-*•+]\s+(.+)$/);
    const numbered = trimmed.match(/^\d+[.)]\s+(.+)$/);
    if (bullet || numbered) {
      flushPara();
      flushQuote();
      const want = bullet ? "ul" : "ol";

      if (!list) {
        out.push(`<${want}>`);
        list = want;
      } else if (list === "ol" && want === "ul") {
        // Подпункт под нумерованным пунктом: вкладываем ul внутрь li,
        // иначе следующий нумерованный пункт начинал бы список заново ("1, 1, 1").
        if (!innerUl) {
          out.push("<ul>");
          innerUl = true;
        }
      } else if (list === "ol" && want === "ol") {
        if (innerUl) {
          out.push("</ul>");
          innerUl = false;
        }
      } else if (list !== want) {
        closeList();
        out.push(`<${want}>`);
        list = want;
      }

      // Закрывающий </li> не пишем: в HTML5 он необязателен,
      // а браузер сам корректно вкладывает вложенный список в нужный пункт.
      out.push(`<li>${renderInline((bullet || numbered)[1])}`);
      continue;
    }

    closeList();
    para.push(trimmed);
  }

  if (code !== null && code.length) {
    out.push(`<pre><code>${escapeHtml(code.join("\n"))}</code></pre>`);
  }
  flushAll();
  return out.join("\n");
}

/* ---------- UI ---------- */

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function isNearBottom() {
  return log.scrollHeight - log.scrollTop - log.clientHeight < 120;
}

function scrollToBottom() {
  log.scrollTop = log.scrollHeight;
}

function addUserMessage(text) {
  messages.appendChild(el("div", "msg user", text));
  scrollToBottom();
}

function addAiMessage() {
  const node = el("div", "msg ai");
  const body = el("div", "answer");
  const status = el("div", "loading");
  status.appendChild(el("span", "spinner"));
  status.appendChild(el("span", "", "Агент обращается к источникам, это может занять 20–60 секунд"));
  body.appendChild(status);
  node.appendChild(body);
  messages.appendChild(node);
  scrollToBottom();
  return { node, body };
}

function addCopyButton(container, text) {
  const row = el("div", "actions");
  const button = el("button", "copy", "Скопировать ответ");
  button.type = "button";
  button.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(text);
      button.textContent = "Скопировано";
    } catch (error) {
      button.textContent = "Не удалось скопировать";
    }
    setTimeout(() => {
      button.textContent = "Скопировать ответ";
    }, 1600);
  });
  row.appendChild(button);
  container.appendChild(row);
}

function renderSources(list) {
  badges.textContent = "";
  (list || []).forEach((item) => {
    const state = item.configured ? "on" : "off";
    const label = `${item.source}: ${item.configured ? "готов" : "не настроен"}`;
    const badge = el("span", `badge ${state}`, label);
    if (item.detail) badge.title = item.detail;
    badges.appendChild(badge);
  });
}

function detailsBlock(title, rows) {
  const box = el("details");
  box.appendChild(el("summary", "", title));
  rows.forEach(([label, value, className]) => {
    const kv = el("div", "kv");
    kv.appendChild(el("b", "", label));
    kv.appendChild(el("span", className || "", value));
    box.appendChild(kv);
  });
  return box;
}

function renderDetails(node, data) {
  if (data.tool_runs && data.tool_runs.length) {
    node.appendChild(
      detailsBlock(
        `Шаги агента (${data.tool_runs.length})`,
        data.tool_runs.map((run) => [
          run.tool,
          run.detail,
          run.status === "ok" ? "status-ok" : "status-error",
        ]),
      ),
    );
  }

  if (data.evidence && data.evidence.length) {
    node.appendChild(
      detailsBlock(
        `Источники и время замеров (${data.evidence.length})`,
        data.evidence.map((item) => {
          const when = new Date(item.observed_at).toLocaleString("ru-RU");
          return [item.source, `${item.summary} · замер: ${when}`];
        }),
      ),
    );
  }
}

function autoGrow(textarea) {
  textarea.style.height = "auto";
  textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`;
}

/* ---------- Логика запроса ---------- */

async function ask(message) {
  // Флаг снимаем до вставки сообщений: сами вставки прокручивают ленту вниз
  // и иначе всегда давали бы «пользователь был внизу».
  const stickToBottom = isNearBottom();
  addUserMessage(message);
  const { node, body } = addAiMessage();
  send.disabled = true;

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, sources: SOURCES, max_results: 15 }),
    });
    const data = await response.json();

    if (!response.ok) {
      body.textContent = "";
      body.appendChild(el("div", "error", data.detail || response.statusText));
      return;
    }

    const reply = (data.reply || "").trim();
    body.innerHTML = reply
      ? renderMarkdown(reply)
      : '<p class="hint">Агент вернул пустой ответ.</p>';
    if (reply) addCopyButton(body, reply);
    renderSources(data.sources);
    renderDetails(node, data);

    // Показываем начало ответа, но только если пользователь был внизу ленты:
    // если он читает предыдущие сообщения, не выдёргиваем его из контекста.
    if (stickToBottom) {
      node.style.scrollMarginTop = "16px";
      node.scrollIntoView({ block: "start" });
    }
  } catch (error) {
    body.textContent = "";
    body.appendChild(el("div", "error", `Сеть недоступна: ${error}`));
  } finally {
    send.disabled = false;
    input.focus();
  }
}

/* ---------- События ---------- */

PRESETS.forEach((text) => {
  const chip = el("button", "chip", text);
  chip.type = "button";
  chip.addEventListener("click", () => ask(text));
  presets.appendChild(chip);
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const value = input.value.trim();
  if (!value) return;
  input.value = "";
  autoGrow(input);
  ask(value);
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

input.addEventListener("input", () => autoGrow(input));

fetch("/api/sources")
  .then((response) => response.json())
  .then((data) => renderSources(data.sources))
  .catch(() => renderSources([]));


