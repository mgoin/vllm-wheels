const PAGE_SIZE = 50;
const number = new Intl.NumberFormat("en-US");

const state = {
    wheels: [],
    filtered: [],
    query: "",
    channel: "",
    source: "",
    variant: "",
    architecture: "",
    python: "",
    sort: "newest",
    page: 1,
};

const elements = {
    search: document.querySelector("#search"),
    source: document.querySelector("#source-filter"),
    variant: document.querySelector("#variant-filter"),
    architecture: document.querySelector("#architecture-filter"),
    python: document.querySelector("#python-filter"),
    sort: document.querySelector("#sort-filter"),
    filters: document.querySelector("#filters"),
    channelTabs: [...document.querySelectorAll(".channel-tab")],
    rows: document.querySelector("#wheel-rows"),
    table: document.querySelector("#table-shell"),
    empty: document.querySelector("#empty-state"),
    summary: document.querySelector("#results-summary"),
    pagination: document.querySelector("#pagination"),
    previous: document.querySelector("#previous-page"),
    next: document.querySelector("#next-page"),
    pageStatus: document.querySelector("#page-status"),
    reset: document.querySelector("#reset-filters"),
    emptyReset: document.querySelector("#empty-reset"),
    share: document.querySelector("#share-view"),
    toast: document.querySelector("#toast"),
    latestVersion: document.querySelector("#latest-version"),
    latestCommand: document.querySelector("#latest-command"),
    copyLatest: document.querySelector("#copy-latest"),
};

let toastTimer;
let searchTimer;

async function init() {
    readUrlState();
    bindEvents();

    try {
        const response = await fetch("data/wheels.json");
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const dataset = await response.json();
        if (dataset.schema_version !== 2 || !Array.isArray(dataset.wheels)) {
            throw new Error("unsupported dataset schema");
        }

        state.wheels = dataset.wheels.map((wheel, index) => ({
            ...wheel,
            _indexOrder: index,
            _searchText: [
                wheel.filename,
                wheel.version,
                wheel.release,
                wheel.commit,
                wheel.source,
                wheel.effective_variant,
                wheel.python_tag,
                wheel.abi_tag,
                wheel.platform_tag,
                wheel.architecture,
                wheel.operating_system,
            ].filter(Boolean).join(" ").toLowerCase(),
        }));

        populateStats(dataset.stats);
        populateQuickInstall(dataset.stats);
        populateFilters();
        populateChannelCounts();
        syncControls();
        applyFilters({ updateUrl: false });
    } catch (error) {
        elements.summary.textContent = `Could not load wheel data: ${error.message}`;
        elements.empty.hidden = false;
        elements.empty.querySelector("strong").textContent = "The index is unavailable.";
        elements.empty.querySelector("p").textContent = "Try refreshing the page in a moment.";
        elements.emptyReset.hidden = true;
    }
}

function bindEvents() {
    elements.search.addEventListener("input", () => {
        window.clearTimeout(searchTimer);
        searchTimer = window.setTimeout(() => {
            state.query = elements.search.value.trim();
            state.page = 1;
            applyFilters();
        }, 120);
    });

    for (const [element, key] of [
        [elements.source, "source"],
        [elements.variant, "variant"],
        [elements.architecture, "architecture"],
        [elements.python, "python"],
        [elements.sort, "sort"],
    ]) {
        element.addEventListener("change", () => {
            state[key] = element.value;
            state.page = 1;
            applyFilters();
        });
    }

    elements.channelTabs.forEach((button) => {
        button.addEventListener("click", () => {
            state.channel = button.dataset.channel;
            state.page = 1;
            syncControls();
            applyFilters();
        });
    });

    elements.previous.addEventListener("click", () => changePage(-1));
    elements.next.addEventListener("click", () => changePage(1));
    elements.reset.addEventListener("click", resetFilters);
    elements.emptyReset.addEventListener("click", resetFilters);
    elements.share.addEventListener("click", shareView);
    elements.copyLatest.addEventListener("click", () => {
        copyText(elements.latestCommand.textContent, "Install command copied");
    });

    elements.rows.addEventListener("click", (event) => {
        const button = event.target.closest("[data-copy-command]");
        if (!button) return;
        const wheel = state.wheels.find((item) => item.id === button.dataset.copyCommand);
        if (wheel) copyText(wheel.install_command, "Install command copied");
    });

    document.addEventListener("keydown", (event) => {
        const target = event.target;
        const isEditing = target instanceof HTMLInputElement
            || target instanceof HTMLTextAreaElement
            || target instanceof HTMLSelectElement;
        if (event.key === "/" && !isEditing) {
            event.preventDefault();
            elements.search.focus();
        }
    });

    window.addEventListener("popstate", () => {
        readUrlState();
        syncControls();
        applyFilters({ updateUrl: false });
    });
}

function readUrlState() {
    const params = new URLSearchParams(window.location.search);
    state.query = params.get("q") || "";
    state.channel = params.get("channel") || "";
    state.source = params.get("source") || "";
    state.variant = params.get("variant") || "";
    state.architecture = params.get("arch") || "";
    state.python = params.get("python") || "";
    state.sort = params.get("sort") || "newest";
    state.page = Math.max(1, Number.parseInt(params.get("page") || "1", 10) || 1);
}

function syncControls() {
    elements.search.value = state.query;
    elements.source.value = state.source;
    elements.variant.value = state.variant;
    elements.architecture.value = state.architecture;
    elements.python.value = state.python;
    elements.sort.value = state.sort;
    elements.channelTabs.forEach((button) => {
        const active = button.dataset.channel === state.channel;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-pressed", String(active));
    });
}

function populateStats(stats) {
    document.querySelector("#stat-wheels").textContent = number.format(stats.total_records);
    document.querySelector("#stat-releases").textContent = number.format(stats.release_versions);
    document.querySelector("#stat-variants").textContent = number.format(
        Object.keys(stats.variants || {}).length,
    );
    document.querySelector("#stat-updated").textContent = relativeTime(stats.generated_at);
}

function populateQuickInstall(stats) {
    elements.latestVersion.textContent = `v${stats.latest_release}`;
    const latest = state.wheels.find((wheel) => (
        wheel.channel === "release"
        && wheel.release === stats.latest_release
        && wheel.source === "wheels.vllm.ai"
        && wheel.effective_variant === "default"
        && wheel.architecture === "x86_64"
    ));
    if (latest) elements.latestCommand.textContent = latest.install_command;
}

function populateFilters() {
    fillSelect(elements.source, unique(state.wheels.map((wheel) => wheel.source)), sourceLabel);
    fillSelect(elements.variant, unique(state.wheels.map((wheel) => wheel.effective_variant)));
    fillSelect(elements.architecture, unique(state.wheels.map((wheel) => wheel.architecture)));
    fillSelect(elements.python, unique(state.wheels.map((wheel) => wheel.python_tag)));
}

function fillSelect(select, values, labeler = (value) => value) {
    values.forEach((value) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = labeler(value);
        select.append(option);
    });
}

function populateChannelCounts() {
    const counts = { all: state.wheels.length, release: 0, nightly: 0, commit: 0 };
    state.wheels.forEach((wheel) => {
        counts[wheel.channel] = (counts[wheel.channel] || 0) + 1;
    });
    document.querySelectorAll("[data-count]").forEach((element) => {
        element.textContent = number.format(counts[element.dataset.count] || 0);
    });
}

function applyFilters({ updateUrl = true } = {}) {
    const terms = state.query.toLowerCase().split(/\s+/).filter(Boolean);
    state.filtered = state.wheels.filter((wheel) => {
        if (state.channel && wheel.channel !== state.channel) return false;
        if (state.source && wheel.source !== state.source) return false;
        if (state.variant && wheel.effective_variant !== state.variant) return false;
        if (state.architecture && wheel.architecture !== state.architecture) return false;
        if (state.python && wheel.python_tag !== state.python) return false;
        return terms.every((term) => wheel._searchText.includes(term));
    });

    if (state.sort === "oldest") {
        state.filtered.reverse();
    } else if (state.sort === "filename") {
        state.filtered.sort((a, b) => a.filename.localeCompare(b.filename));
    }

    const pages = Math.max(1, Math.ceil(state.filtered.length / PAGE_SIZE));
    state.page = Math.min(state.page, pages);
    render();
    if (updateUrl) writeUrlState();
}

function render() {
    const total = state.filtered.length;
    const start = (state.page - 1) * PAGE_SIZE;
    const visible = state.filtered.slice(start, start + PAGE_SIZE);
    elements.rows.replaceChildren(...visible.map(renderRow));

    elements.table.hidden = total === 0;
    elements.empty.hidden = total !== 0;
    elements.pagination.hidden = total <= PAGE_SIZE;

    if (total) {
        const end = Math.min(start + PAGE_SIZE, total);
        elements.summary.textContent = `${number.format(start + 1)}–${number.format(end)} of ${number.format(total)} matching entries`;
    } else {
        elements.summary.textContent = "0 matching entries";
    }

    const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    elements.pageStatus.textContent = `Page ${state.page} of ${pages}`;
    elements.previous.disabled = state.page <= 1;
    elements.next.disabled = state.page >= pages;
}

function renderRow(wheel) {
    const row = document.createElement("tr");

    const build = cell("Build", "build-cell");
    const version = document.createElement("strong");
    version.textContent = wheel.release || wheel.version;
    const buildType = document.createElement("span");
    buildType.textContent = wheel.channel === "commit" && wheel.commit
        ? `commit ${wheel.commit.slice(0, 10)}`
        : wheel.channel;
    build.append(version, buildType);

    const source = cell("Source");
    const sourceLink = document.createElement("a");
    sourceLink.className = "source-link";
    sourceLink.href = wheel.source_url;
    sourceLink.textContent = sourceLabel(wheel.source);
    sourceLink.target = "_blank";
    sourceLink.rel = "noreferrer";
    const family = document.createElement("span");
    family.textContent = wheel.index_family || "release asset";
    source.append(sourceLink, family);

    const variant = cell("Variant");
    const variantTag = document.createElement("span");
    variantTag.className = `tag ${wheel.effective_variant === "default" ? "" : "tag-accent"}`;
    variantTag.textContent = wheel.effective_variant;
    variant.append(variantTag);

    const python = cell("Python", "python-cell");
    const pythonTag = document.createElement("code");
    pythonTag.textContent = wheel.python_tag;
    const abi = document.createElement("span");
    abi.textContent = wheel.abi_tag;
    python.append(pythonTag, abi);

    const platform = cell("Platform", "platform-cell");
    const filename = document.createElement("code");
    filename.textContent = wheel.filename;
    const platformMeta = document.createElement("span");
    platformMeta.textContent = `${wheel.operating_system} · ${wheel.architecture} · ${wheel.platform_tag}`;
    platform.append(filename, platformMeta);

    const install = cell("Install", "install-cell");
    const command = document.createElement("div");
    command.className = "install-command";
    const code = document.createElement("code");
    code.textContent = wheel.install_command;
    const copy = document.createElement("button");
    copy.type = "button";
    copy.className = "copy-button";
    copy.dataset.copyCommand = wheel.id;
    copy.textContent = "Copy";
    copy.setAttribute("aria-label", `Copy install command for ${wheel.filename}`);
    command.append(code, copy);
    const links = document.createElement("div");
    links.className = "install-links";
    links.append(
        externalLink("Download wheel", wheel.download_url),
        externalLink("Open index", wheel.index_url || wheel.source_url),
    );
    install.append(command, links);

    row.append(build, source, variant, python, platform, install);
    return row;
}

function cell(label, className = "") {
    const element = document.createElement("td");
    element.dataset.label = label;
    if (className) element.className = className;
    return element;
}

function externalLink(label, href) {
    const link = document.createElement("a");
    link.href = href;
    link.textContent = label;
    link.target = "_blank";
    link.rel = "noreferrer";
    return link;
}

function changePage(delta) {
    state.page += delta;
    render();
    writeUrlState();
    document.querySelector("#explorer-title").scrollIntoView({ block: "start" });
}

function resetFilters() {
    Object.assign(state, {
        query: "",
        channel: "",
        source: "",
        variant: "",
        architecture: "",
        python: "",
        sort: "newest",
        page: 1,
    });
    syncControls();
    applyFilters();
}

function writeUrlState() {
    const params = new URLSearchParams();
    const entries = [
        ["q", state.query],
        ["channel", state.channel],
        ["source", state.source],
        ["variant", state.variant],
        ["arch", state.architecture],
        ["python", state.python],
        ["sort", state.sort === "newest" ? "" : state.sort],
        ["page", state.page > 1 ? String(state.page) : ""],
    ];
    entries.forEach(([key, value]) => {
        if (value) params.set(key, value);
    });
    const query = params.toString();
    history.replaceState(null, "", `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash}`);
}

async function shareView() {
    writeUrlState();
    await copyText(window.location.href, "Shareable view link copied");
}

async function copyText(text, message) {
    try {
        await navigator.clipboard.writeText(text);
    } catch {
        const textarea = document.createElement("textarea");
        textarea.value = text;
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.append(textarea);
        textarea.select();
        document.execCommand("copy");
        textarea.remove();
    }
    showToast(message);
}

function showToast(message) {
    window.clearTimeout(toastTimer);
    elements.toast.textContent = message;
    elements.toast.classList.add("is-visible");
    toastTimer = window.setTimeout(() => {
        elements.toast.classList.remove("is-visible");
    }, 1800);
}

function sourceLabel(source) {
    return source === "github" ? "GitHub assets" : "wheels.vllm.ai";
}

function unique(values) {
    return [...new Set(values.filter(Boolean))].sort((a, b) => (
        a.localeCompare(b, undefined, { numeric: true })
    ));
}

function relativeTime(value) {
    const date = new Date(value);
    const seconds = Math.round((date.getTime() - Date.now()) / 1000);
    const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
    if (Math.abs(seconds) < 3600) return formatter.format(Math.round(seconds / 60), "minute");
    if (Math.abs(seconds) < 86400) return formatter.format(Math.round(seconds / 3600), "hour");
    return formatter.format(Math.round(seconds / 86400), "day");
}

init();

