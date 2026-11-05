/* منطق مشترک سایت. همه‌ی متن‌های دریافتی از داده، قبل از نمایش escape می‌شوند. */
const NF1 = new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const NF0 = new Intl.NumberFormat("fa-IR");
const DATE_FMT = new Intl.DateTimeFormat("fa-IR-u-ca-persian", { year: "numeric", month: "long", day: "numeric" });
const MONTH_FMT = new Intl.DateTimeFormat("fa-IR-u-ca-persian", { year: "2-digit", month: "short" });

const fa1 = (n) => (n == null ? "—" : NF1.format(n));
const fa0 = (n) => NF0.format(n);
const faDate = (iso) => { const d = new Date(iso); return isNaN(d) ? "" : DATE_FMT.format(d); };
const faMonth = (ym) => MONTH_FMT.format(new Date(ym + "-15T12:00:00Z"));

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function safeUrl(u) {
  try { const x = new URL(u); return x.protocol === "https:" || x.protocol === "http:" ? x.href : ""; } catch { return ""; }
}
function num(n, lo = 0, hi = 10) { n = Number(n); return Number.isFinite(n) ? Math.min(hi, Math.max(lo, n)) : 0; }

function ruler(score, big = false) {
  const v = num(score);
  return `<div class="ruler${big ? " big" : ""}" role="img" aria-label="نمره ${fa1(v)} از ۱۰">` +
    `<span class="fill" style="width:${v * 10}%"></span><span class="mark" style="left:${v * 10}%"></span></div>`;
}

async function loadScores() {
  try {
    const r = await fetch("data/scores.json", { cache: "no-store" });
    if (!r.ok) throw new Error(r.status);
    return await r.json();
  } catch (e) {
    document.querySelector("main").innerHTML =
      '<p class="empty">داده بارگذاری نشد. اگر صفحه را مستقیم از روی فایل باز کرده‌اید، آن را از طریق یک وب‌سرور باز کنید ' +
      "(مثلاً با دستور <code>python3 -m http.server</code> داخل پوشه‌ی docs).</p>";
    throw e;
  }
}

function fillChrome(data) {
  const s = data.meta.site || {};
  document.title = (document.body.dataset.title ? document.body.dataset.title + " | " : "") + (s.title || "");
  document.querySelectorAll("[data-site-title]").forEach((el) => (el.textContent = s.title || ""));
  document.querySelectorAll("[data-site-subtitle]").forEach((el) => (el.textContent = s.subtitle || ""));
  document.querySelectorAll("[data-disclaimer]").forEach((el) => (el.textContent = s.disclaimer || ""));
  document.querySelectorAll("[data-stamp]").forEach((el) => (el.textContent = "آخرین به‌روزرسانی: " + faDate(data.meta.generated_at)));
  document.querySelectorAll("[data-contact]").forEach((el) => {
    const m = s.contact_email || "";
    el.innerHTML = /^[^\s@<>"']+@[^\s@<>"']+$/.test(m)
      ? `گزارش خطا یا درخواست اصلاح: <a href="mailto:${esc(m)}">${esc(m)}</a>` : "";
  });
  const banners = [];
  if (data.meta.demo) banners.push("این داده‌ها آزمایشی‌اند و درباره‌ی هیچ شخص واقعی نیستند.");
  if (data.rubric.template) banners.push("معیارهای این نسخه هنوز نمونه‌اند و نمره‌ها اعتبار ندارند.");
  const box = document.querySelector("[data-banners]");
  if (box) box.innerHTML = banners.map((b) => `<div class="banner" role="note">${esc(b)}</div>`).join("");
}

const KIND = { statement: "سخن", action: "اقدام", unclear: "نامشخص" };
const STATUS = { approved: ["تأییدشده", ""], auto: ["تحلیل خودکار", "auto"] };

/* ---------------------------------------------------------------- index */
function pageIndex(data) {
  const crits = data.rubric.criteria;
  const critTitle = Object.fromEntries(crits.map((c) => [c.id, c.title]));
  const list = document.getElementById("board");
  const rest = document.getElementById("insufficient");
  const q = document.getElementById("q");
  const sortSel = document.getElementById("sort");
  const note = document.getElementById("sorting");
  sortSel.innerHTML = '<option value="overall">نمره‌ی کلی</option>' +
    crits.map((c) => `<option value="${esc(c.id)}">${esc(c.title)}</option>`).join("");

  const val = (p, key) => (key === "overall" ? p.overall : p.criteria[key]?.avg ?? null);

  function row(p, pos, key) {
    const v = val(p, key);
    const mini = crits.filter((c) => p.criteria[c.id])
      .map((c) => `<span>${esc(c.title)}: <b>${fa1(p.criteria[c.id].avg)}</b></span>`).join("");
    return `<li class="row"><a href="person.html?id=${encodeURIComponent(p.id)}">
      <span class="rank">${pos ? fa0(pos) : "·"}</span>
      <span class="who"><strong>${esc(p.name)}</strong><small>${esc(p.title)}</small></span>
      <span class="meter"><span class="num">${fa1(v)}</span>${v == null ? "" : ruler(v)}</span>
      <span class="mini">${mini}<span>${fa0(p.counted_items)} مورد</span></span></a></li>`;
  }

  function render() {
    const key = sortSel.value, term = q.value.trim();
    const match = (p) => !term || p.name.includes(term) || p.title.includes(term);
    const ranked = data.people.filter((p) => p.eligible && match(p) && val(p, key) != null)
      .sort((a, b) => val(b, key) - val(a, key) || a.name.localeCompare(b.name, "fa"));
    list.innerHTML = ranked.length ? ranked.map((p, i) => row(p, i + 1, key)).join("")
      : '<li class="empty">موردی برای نمایش نیست.</li>';
    const noData = data.people.filter((p) => p.eligible && match(p) && val(p, key) == null).length;
    note.textContent = "ترتیب بر اساس: " + (key === "overall" ? "نمره‌ی کلی" : critTitle[key]) +
      (noData ? `. ${fa0(noData)} نفر برای این معیار داده‌ای ندارند و نمایش داده نمی‌شوند.` : "");
    const low = data.people.filter((p) => !p.eligible && match(p));
    rest.innerHTML = low.length
      ? `<h2 class="sec">داده‌ی ناکافی</h2><p class="hint">برای رتبه‌گرفتن، دست‌کم ${fa0(data.meta.method.min_items)} مورد تأییدشده یا با اطمینان بالا لازم است.</p>
         <ol class="board">${low.map((p) => row(p, null, "overall")).join("")}</ol>` : "";
  }
  q.addEventListener("input", render);
  sortSel.addEventListener("change", render);
  render();
}

/* --------------------------------------------------------------- person */
function pageDetail(data) {
  const id = new URLSearchParams(location.search).get("id");
  const p = data.people.find((x) => x.id === id);
  const main = document.querySelector("main");
  if (!p) { main.innerHTML = '<p class="empty">این شخص پیدا نشد. <a href="index.html">بازگشت به فهرست</a></p>'; return; }
  document.title = p.name + " | " + (data.meta.site.title || "");
  const crits = Object.fromEntries(data.rubric.criteria.map((c) => [c.id, c]));
  const handle = /^[A-Za-z0-9_]{1,15}$/.test(p.twitter) && !p.twitter.startsWith("sample") ? p.twitter : "";
  const contact = data.meta.site.contact_email || "";

  const critBlocks = data.rubric.criteria.filter((c) => p.criteria[c.id]).map((c) => {
    const a = p.criteria[c.id];
    return `<div class="crit-block"><h3>${esc(c.title)}</h3>
      <div class="meter"><span class="num">${fa1(a.avg)}</span>${ruler(a.avg)}</div>
      <div class="meta">بر پایه‌ی ${fa0(a.n)} مورد</div></div>`;
  }).join("");

  const maxBar = 10;
  const trend = p.trend.length > 1 ? `<h2 class="sec">روند ماهانه</h2>
    <div class="trend" role="img" aria-label="میانگین نمره‌ی ماهانه">${p.trend.map((t) =>
      `<div class="bar" title="${fa1(t.avg)}" style="height:${num(t.avg) / maxBar * 100}%"></div>`).join("")}</div>
    <div class="trend-labels">${p.trend.map((t) => `<span>${esc(faMonth(t.month))}</span>`).join("")}</div>` : "";

  const items = p.items.map((it) => {
    const [stLabel, stCls] = STATUS[it.status] || ["", ""];
    const href = safeUrl(it.url);
    const subject = encodeURIComponent("گزارش خطا: " + p.name + " | " + it.title);
    const rows = Object.entries(it.criteria).filter(([cid]) => crits[cid]).map(([cid, c]) =>
      `<div class="ev-crit"><span class="ct">${esc(crits[cid].title)}: ${fa0(c.score)} از ۱۰</span>
       ${c.quote ? `<q>${esc(c.quote)}</q>` : ""}
       ${c.quote && !c.quote_verified ? '<span class="unverified">عین این نقل‌قول در متن منبع پیدا نشد.</span>' : ""}
       <div class="why">${esc(c.reason)}</div></div>`).join("");
    return `<li class="ev"><div class="ev-head">
        <span>${esc(faDate(it.date))}</span><span>${esc(it.source)}</span>
        <span>${esc(KIND[it.kind] || "")}</span><span class="badge ${stCls}">${esc(stLabel)}</span></div>
      <h3>${href ? `<a href="${esc(href)}" rel="noopener noreferrer nofollow">${esc(it.title)}</a>` : esc(it.title)}</h3>
      ${it.summary ? `<div>${esc(it.summary)}</div>` : ""}${rows}
      ${it.note ? `<div class="hint">یادداشت ویراستار: ${esc(it.note)}</div>` : ""}
      ${contact && /^[^\s@<>"']+@[^\s@<>"']+$/.test(contact)
        ? `<div class="report"><a href="mailto:${esc(contact)}?subject=${subject}">گزارش خطا درباره‌ی این مورد</a></div>` : ""}</li>`;
  }).join("");

  main.innerHTML = `<a class="back" href="index.html">بازگشت به فهرست</a>
    <div class="person-head"><h1>${esc(p.name)}</h1><p>${esc(p.title)}${handle ? `، <a href="https://x.com/${esc(handle)}" rel="noopener noreferrer nofollow">@${esc(handle)}</a>` : ""}</p></div>
    <div class="overall"><div class="meter"><span class="num">${fa1(p.overall)}</span>${p.overall == null ? "" : ruler(p.overall, true)}</div>
      <p class="hint">نمره‌ی کلی از ۰ تا ۱۰. ${p.rank ? "رتبه‌ی " + fa0(p.rank) : "داده‌ی ناکافی برای رتبه"}، ${fa0(p.counted_items)} مورد در محاسبه${p.pending_items ? "، " + fa0(p.pending_items) + " مورد در انتظار بازبینی (محاسبه نشده)" : ""}.</p></div>
    ${critBlocks}${trend}
    <h2 class="sec">مستندات</h2>
    ${items ? `<ul class="evidence">${items}</ul>` : '<p class="empty">هنوز مورد تأییدشده‌ای ثبت نشده است.</p>'}`;
}

/* ---------------------------------------------------------------- about */
function pageAbout(data) {
  const m = data.meta.method, r = data.rubric;
  const principles = r.principles.length
    ? `<h2 class="sec">اصول مبنا</h2><ul class="plain">${r.principles.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : "";
  const crits = r.criteria.map((c) => `<div class="crit-def"><h3>${esc(c.title)}</h3>
    <p>${esc(c.description)}</p>
    <ul class="anchors">${Object.entries(c.anchors || {}).map(([k, v]) => `<li><b>${esc(k.replace("-", "–"))}</b><span>${esc(v)}</span></li>`).join("")}</ul>
    <p class="hint">وزن در نمره‌ی کلی: ${fa0(c.weight)} · کاربرد: ${c.applies_to.map((k) => KIND[k] || k).join("، ")}</p></div>`).join("");
  document.getElementById("about").innerHTML = `${principles}
    <h2 class="sec">معیارها</h2><p class="hint">${esc(r.scale_note)}</p>${crits}
    <h2 class="sec">روش محاسبه</h2>
    <ul class="plain">
      <li>خبرها و گفته‌های ثبت‌شده با تحلیل خودکار متن و بر اساس معیارهای بالا نمره می‌گیرند. هر نمره نقل‌قول، دلیل و پیوند منبع دارد.</li>
      <li>نمره‌ی هر معیار میانگین وزنی است. موارد تازه‌تر وزن بیشتری دارند و وزن هر مورد هر ${fa0(m.half_life_days)} روز نصف می‌شود.</li>
      <li>مواردی که ویراستار تأیید کرده با وزن کامل حساب می‌شوند. موارد خودکار به نسبت میزان اطمینان تحلیل وزن می‌گیرند.</li>
      <li>مواردی که اطمینان تحلیل کمتر از ${fa0(m.min_confidence * 100)}٪ است یا نقل‌قولشان در متن منبع پیدا نشده، تا بازبینی انسانی ${m.count_low_confidence ? "با وزن کمتر حساب می‌شوند" : "در محاسبه نمی‌آیند و منتشر نمی‌شوند"}.</li>
      <li>رتبه فقط برای کسانی است که دست‌کم ${fa0(m.min_items)} مورد حساب‌شده دارند.</li>
      <li>ویراستار می‌تواند هر نمره را اصلاح یا حذف کند. اصلاحات در پرونده‌ی همان مورد ثبت می‌شود.</li>
    </ul>
    <h2 class="sec">محدودیت‌ها</h2>
    <ul class="plain">
      <li>تحلیل خودکار ممکن است کنایه، نقل‌قول از دیگران یا بافتار را اشتباه بخواند.</li>
      <li>فقط متنی که منبع منتشر کرده خوانده می‌شود؛ سخنی که رسانه‌ها گزارش نکرده‌اند دیده نمی‌شود.</li>
      <li>نمره نشان‌دهنده‌ی انطباق با معیارهای همین صفحه است، نه قضاوتی درباره‌ی درستی آن‌ها.</li>
    </ul>`;
}

(async function () {
  const data = await loadScores();
  fillChrome(data);
  const page = document.body.dataset.page;
  if (page === "index") pageIndex(data);
  else if (page === "person") pageDetail(data);
  else if (page === "about") pageAbout(data);
})();
