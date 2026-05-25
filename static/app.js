(function () {
  const h = React.createElement;
  const { useEffect, useMemo, useState } = React;

  const SOURCE_META = {
    sap: { label: "SAP", icon: "database", tone: "violet" },
    utility: { label: "Utility", icon: "zap", tone: "info" },
    travel: { label: "Travel", icon: "plane", tone: "good" },
  };

  const STATUS_LABELS = {
    needs_review: "Needs review",
    failed: "Failed",
    approved: "Approved",
    rejected: "Rejected",
    locked: "Locked",
  };

  const SOURCE_TYPES = ["sap", "utility", "travel"];
  const ACTORS = ["Jaswanth Analyst", "Omar Review Lead", "Nina Auditor", "Demo Analyst"];
  const SAMPLE_DOWNLOADS = {
    sap: "/api/samples/sap/download/",
    utility: "/api/samples/utility/download/",
    travel: "/api/samples/travel/download/",
  };
  const FLAG_OPTIONS = [
    ["", "All flags"],
    ["unknown_plant_code", "Unknown plant"],
    ["unknown_facility", "Unknown facility"],
    ["duplicate_meter_period", "Duplicate meter period"],
    ["non_usd_spend_no_fx", "Non-USD spend"],
    ["distance_estimated_from_airports", "Estimated distance"],
    ["high_utility_usage", "High utility usage"],
    ["missing_tariff", "Missing tariff"],
  ];

  function Icon(props) {
    return h("i", {
      "data-lucide": props.name,
      style: { width: props.size || 16, height: props.size || 16 },
      "aria-hidden": "true",
    });
  }

  function useLucide() {
    useEffect(() => {
      if (window.lucide) window.lucide.createIcons();
    });
  }

  function formatNumber(value, digits) {
    const number = Number(value || 0);
    return new Intl.NumberFormat("en-US", {
      maximumFractionDigits: digits == null ? 1 : digits,
    }).format(number);
  }

  function formatDate(value) {
    if (!value) return "No date";
    return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(
      new Date(value + "T00:00:00")
    );
  }

  function formatDateTime(value) {
    if (!value) return "No date";
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }).format(new Date(value));
  }

  function flagTone(flag) {
    if (!flag) return "";
    if (flag.includes("failed") || flag.includes("unsupported") || flag.includes("unknown") || flag.includes("missing")) {
      return "bad";
    }
    if (flag.includes("high") || flag.includes("future") || flag.includes("duplicate") || flag.includes("negative")) {
      return "warn";
    }
    if (flag.includes("converted") || flag.includes("estimated") || flag.includes("derived")) {
      return "info";
    }
    return "";
  }

  function niceFlag(flag) {
    return String(flag || "").replaceAll("_", " ");
  }

  function StatusChip({ status }) {
    return h("span", { className: `status ${status}` }, STATUS_LABELS[status] || status);
  }

  function FlagChip({ flag }) {
    return h("span", { className: `chip ${flagTone(flag)}` }, niceFlag(flag));
  }

  function Metric({ label, value, sub, icon }) {
    return h(
      "div",
      { className: "metric" },
      h("div", { className: "source-title" }, h("span", { className: "label" }, label), icon ? h(Icon, { name: icon }) : null),
      h("div", { className: "value" }, value),
      h("div", { className: "sub" }, sub)
    );
  }

  function App() {
    useLucide();
    const [activeTab, setActiveTab] = useState("overview");
    const [actor, setActor] = useState(ACTORS[0]);
    const [tenants, setTenants] = useState([]);
    const [tenant, setTenant] = useState("");
    const [overview, setOverview] = useState(null);
    const [records, setRecords] = useState([]);
    const [batches, setBatches] = useState([]);
    const [audit, setAudit] = useState([]);
    const [filters, setFilters] = useState({ q: "", source: "", status: "", scope: "", flag: "" });
    const [selectedId, setSelectedId] = useState(null);
    const [selectedIds, setSelectedIds] = useState([]);
    const [loading, setLoading] = useState(true);
    const [toast, setToast] = useState("");
    const [liveRefresh, setLiveRefresh] = useState(false);
    const [lastUpdated, setLastUpdated] = useState(null);
    const [mobileOpen, setMobileOpen] = useState(false);
    const [searchDraft, setSearchDraft] = useState("");

    async function request(path, options) {
      const init = options || {};
      const headers = Object.assign({ "X-Analyst": actor }, init.headers || {});
      if (init.body && !(init.body instanceof FormData)) {
        headers["Content-Type"] = "application/json";
        init.body = JSON.stringify(init.body);
      }
      const response = await fetch(path, Object.assign({}, init, { headers }));
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || "Request failed");
      }
      return data;
    }

    function queryString(extra) {
      const params = new URLSearchParams();
      if (tenant) params.set("tenant", tenant);
      Object.entries(Object.assign({}, filters, extra || {})).forEach(([key, value]) => {
        if (value) params.set(key, value);
      });
      return params.toString();
    }

    async function loadTenants() {
      const data = await request("/api/tenants/");
      setTenants(data);
      if (!tenant && data.length) setTenant(String(data[0].id));
    }

    async function loadData() {
      setLoading(true);
      try {
        const base = tenant ? `?tenant=${tenant}` : "";
        const [overviewData, recordData, batchData, auditData] = await Promise.all([
          request(`/api/overview/${base}`),
          request(`/api/records/?${queryString()}`),
          request(`/api/batches/${base}`),
          request(`/api/audit/${base}`),
        ]);
        setOverview(overviewData);
        setRecords(recordData);
        setBatches(batchData);
        setAudit(auditData);
        setLastUpdated(new Date().toISOString());
        if (!selectedId && recordData[0]) setSelectedId(recordData[0].id);
      } catch (error) {
        setToast(error.message);
      } finally {
        setLoading(false);
      }
    }

    useEffect(() => {
      loadTenants().catch((error) => setToast(error.message));
    }, []);

    useEffect(() => {
      setSearchDraft(filters.q);
    }, [filters.q]);

    useEffect(() => {
      const timer = setTimeout(() => {
        if (searchDraft !== filters.q) changeFilter("q", searchDraft);
      }, 320);
      return () => clearTimeout(timer);
    }, [searchDraft]);

    useEffect(() => {
      loadData();
    }, [tenant, filters.q, filters.source, filters.status, filters.scope, filters.flag]);

    useEffect(() => {
      if (!liveRefresh) return undefined;
      const interval = setInterval(() => {
        loadData().catch((error) => setToast(error.message));
      }, 15000);
      return () => clearInterval(interval);
    }, [liveRefresh, tenant, filters.q, filters.source, filters.status, filters.scope, filters.flag, actor]);

    useEffect(() => {
      if (!toast) return undefined;
      const timer = setTimeout(() => setToast(""), 5200);
      return () => clearTimeout(timer);
    }, [toast]);

    useEffect(() => {
      function onKey(event) {
        if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
          event.preventDefault();
          setActiveTab("review");
        }
        if (event.key.toLowerCase() === "r" && !event.metaKey && !event.ctrlKey && document.activeElement.tagName !== "INPUT" && document.activeElement.tagName !== "TEXTAREA") {
          loadData().catch((error) => setToast(error.message));
        }
      }
      window.addEventListener("keydown", onKey);
      return () => window.removeEventListener("keydown", onKey);
    }, [tenant, filters, actor]);

    function downloadAuditCsv() {
      if (!audit.length) {
        setToast("No audit events to export.");
        return;
      }
      const csvHeaders = ["Timestamp", "Action", "Actor", "Subject", "Reason"];
      const rows = audit.map((event) => [
        new Date(event.created_at).toISOString(),
        event.action.replaceAll("_", " "),
        event.actor,
        event.activity_source_key || event.batch_filename || "batch",
        event.reason || "",
      ]);
      const csvContent = [csvHeaders, ...rows].map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(",")).join("\n");
      const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `audit-export-${new Date().toISOString().slice(0, 10)}.csv`;
      link.click();
      URL.revokeObjectURL(link.href);
      setToast("Audit export started.");
    }

    const selectedRecord = useMemo(
      () => records.find((record) => record.id === selectedId) || records[0],
      [records, selectedId]
    );

    async function uploadSource(sourceType, file) {
      if (!file) return;
      const form = new FormData();
      form.append("tenant", tenant);
      form.append("actor", actor);
      form.append("file", file);
      try {
        const batch = await request(`/api/ingest/${sourceType}/`, { method: "POST", body: form });
        setToast(`${SOURCE_META[sourceType].label} upload complete: ${batch.normalized_rows} normalized, ${batch.failed_rows} failed.`);
        await loadData();
      } catch (error) {
        setToast(error.message);
      }
    }

    async function actOnRecord(recordId, action, reason) {
      try {
        await request(`/api/records/${recordId}/${action}/`, {
          method: "POST",
          body: { tenant, actor, reason: reason || "" },
        });
        setToast(`Record ${action} complete.`);
        await loadData();
      } catch (error) {
        setToast(error.message);
      }
    }

    async function bulkAction(action) {
      if (!selectedIds.length) {
        setToast("Select rows first.");
        return;
      }
      try {
        const result = await request("/api/records/bulk-action/", {
          method: "POST",
          body: { tenant, actor, ids: selectedIds, action, reason: "Bulk analyst action" },
        });
        setToast(`${result.updated.length} updated, ${result.errors.length} skipped.`);
        setSelectedIds([]);
        await loadData();
      } catch (error) {
        setToast(error.message);
      }
    }

    async function saveRecord(recordId, draft) {
      try {
        await request(`/api/records/${recordId}/`, {
          method: "PATCH",
          body: Object.assign({ tenant, actor, reason: "Manual review adjustment" }, draft),
        });
        setToast("Record saved and audit event written.");
        await loadData();
      } catch (error) {
        setToast(error.message);
      }
    }

    function changeFilter(key, value) {
      setFilters((current) => Object.assign({}, current, { [key]: value }));
    }

    const tenantName = overview && overview.tenant ? overview.tenant.name : "Breathe ESG";

    function selectTab(tab) {
      setActiveTab(tab);
      setMobileOpen(false);
    }

    return h(
      "div",
      { className: "app" },
      h("div", {
        className: `sidebar-backdrop${mobileOpen ? " open" : ""}`,
        onClick: () => setMobileOpen(false),
        "aria-hidden": mobileOpen ? "false" : "true",
      }),
      h(
        "aside",
        { className: `sidebar${mobileOpen ? " open" : ""}` },
        h(
          "div",
          { className: "brand" },
          h("div", { className: "brand-mark" }, "B"),
          h("div", null, h("strong", null, "Breathe ESG"), h("span", null, "Intake review"))
        ),
        h(
          "div",
          { className: "nav" },
          navButton("Overview", "overview", "layout-dashboard", activeTab, selectTab),
          navButton("Intake", "intake", "upload-cloud", activeTab, selectTab),
          navButton("Review", "review", "list-checks", activeTab, selectTab),
          navButton("Audit", "audit", "shield-check", activeTab, selectTab)
        ),
        h(
          "div",
          { className: "sidebar-foot" },
          h("div", { className: "label" }, "Tenant"),
          h(
            "select",
            { className: "select", value: tenant, onChange: (event) => setTenant(event.target.value) },
            tenants.map((item) => h("option", { key: item.id, value: item.id }, item.name))
          ),
          h("div", { className: "label" }, "Reviewer"),
          h(
            "select",
            { className: "select", value: actor, onChange: (event) => setActor(event.target.value) },
            ACTORS.map((item) => h("option", { key: item, value: item }, item))
          )
        )
      ),
      h(
        "main",
        { className: "main" },
        h(
          "div",
          { className: "mobile-bar" },
          h(
            "button",
            { className: "menu-button", onClick: () => setMobileOpen(true), "aria-label": "Open menu" },
            h(Icon, { name: "menu" })
          ),
          h("strong", null, pageTitle(activeTab))
        ),
        h(
          "div",
          { className: "topbar" },
          h(
            "div",
            null,
            h("div", { className: "eyebrow" }, tenantName),
            h("h1", null, pageTitle(activeTab)),
            lastUpdated && h("div", { className: "top-meta" }, `Last refreshed ${formatDateTime(lastUpdated)}`)
          ),
          h(
            "div",
            { className: "toolbar" },
            h(
              "button",
              { className: `ghost-button${liveRefresh ? " active" : ""}`, onClick: () => setLiveRefresh((current) => !current) },
              h(Icon, { name: "clock" }),
              liveRefresh ? "Live on" : "Live refresh"
            ),
            h(
              "button",
              { className: "ghost-button", onClick: downloadAuditCsv },
              h(Icon, { name: "download" }),
              "Export audit"
            ),
            h(
              "button",
              { className: "ghost-button", onClick: () => loadData() },
              h(Icon, { name: "refresh-cw" }),
              "Refresh"
            ),
            h(
              "button",
              { className: "primary-button", onClick: () => selectTab("intake") },
              h(Icon, { name: "upload" }),
              "New upload"
            )
          )
        ),
        activeTab === "overview"
          ? h(Overview, { overview, loading, setFilter: changeFilter, setActiveTab: selectTab })
          : null,
        activeTab === "intake" ? h(Intake, { overview, batches, uploadSource }) : null,
        activeTab === "review"
          ? h(Review, {
              records,
              filters,
              changeFilter,
              searchDraft,
              setSearchDraft,
              selectedId,
              setSelectedId,
              selectedRecord,
              selectedIds,
              setSelectedIds,
              actOnRecord,
              bulkAction,
              saveRecord,
              loading,
            })
          : null,
        activeTab === "audit" ? h(Audit, { audit, batches }) : null,
        toast ? h("div", { className: "toast", onClick: () => setToast("") }, toast) : null
      )
    );
  }

  function navButton(label, tab, icon, activeTab, setActiveTab) {
    return h(
      "button",
      { className: activeTab === tab ? "active" : "", onClick: () => setActiveTab(tab) },
      h(Icon, { name: icon }),
      label
    );
  }

  function pageTitle(tab) {
    return {
      overview: "Analyst dashboard",
      intake: "Source intake",
      review: "Review queue",
      audit: "Audit trail",
    }[tab];
  }

  function Overview({ overview, loading, setFilter, setActiveTab }) {
    if (loading && !overview) {
      return h("div", { className: "workspace" }, h("div", { className: "skeleton" }), h("div", { className: "skeleton" }));
    }
    if (!overview) return h("div", { className: "empty" }, h("strong", null, "No overview available"), h("span", null, "Upload a source file to begin."));
    const totals = overview.totals || {};
    const maxScope = Math.max(...Object.values(overview.emissions_by_scope || {}).map(Number), 1);
    const suspiciousTotal = (overview.source_health || []).reduce((sum, item) => sum + (item.suspicious_rows || 0), 0);
    return h(
      "div",
      { className: `workspace loading-overlay${loading ? " is-loading" : ""}` },
      h(
        "div",
        { className: "grid metrics" },
        h(Metric, { label: "Rows", value: formatNumber(totals.records, 0), sub: `${formatNumber(totals.batches, 0)} batches`, icon: "rows-3" }),
        h(Metric, { label: "CO2e kg", value: formatNumber(totals.co2e_kg, 1), sub: "Open and approved rows", icon: "cloud" }),
        h(Metric, { label: "Needs review", value: formatNumber(totals.needs_review, 0), sub: `${formatNumber(totals.failed, 0)} failed`, icon: "alert-triangle" }),
        h(Metric, { label: "Audit locked", value: formatNumber(totals.locked, 0), sub: `${formatNumber(totals.approved, 0)} approved`, icon: "lock" })
      ),
      h(WorkflowStrip, { totals, statusCounts: overview.status_counts || {} }),
      h(
        "section",
        { className: "panel" },
        h("div", { className: "panel-head" }, h("h2", null, "Quality insights"), h("span", { className: "muted" }, "Signals across all sources")),
        h(
          "div",
          { className: "panel-body", style: { display: "grid", gap: "14px", gridTemplateColumns: "repeat(3, minmax(0, 1fr))" } },
          h(Metric, {
            label: "Data confidence",
            value: `${Math.max(0, Math.min(100, Math.round(100 - ((totals.failed + totals.needs_review) / Math.max(totals.records, 1)) * 100)))}%`,
            sub: "Lower backlog means stronger data",
            icon: "shield-check",
          }),
          h(Metric, {
            label: "Suspicious rate",
            value: `${Math.round((suspiciousTotal / Math.max(totals.records, 1)) * 100)}%`,
            sub: `${suspiciousTotal} rows flagged suspicious`,
            icon: "alert-circle",
          }),
          h(Metric, {
            label: "Top flag",
            value: overview.top_flags && overview.top_flags[0] ? niceFlag(overview.top_flags[0].flag) : "None",
            sub: overview.top_flags && overview.top_flags[0] ? `${overview.top_flags[0].count} occurrences` : "No flags yet",
            icon: "star",
          })
        )
      ),
      h(
        "div",
        { className: "grid two-col" },
        h(
          "section",
          { className: "panel" },
          h("div", { className: "panel-head" }, h("h2", null, "Source health"), h("span", { className: "muted" }, "Rows by pipeline")),
          h(
            "div",
            { className: "panel-body source-grid" },
            overview.source_health.map((source) => h(SourceHealthCard, { key: source.source_type, source, setFilter, setActiveTab }))
          )
        ),
        h(
          "section",
          { className: "panel" },
          h("div", { className: "panel-head" }, h("h2", null, "Scope mix"), h("span", { className: "muted" }, "kg CO2e")),
          h(
            "div",
            { className: "panel-body bar-stack" },
            ["scope_1", "scope_2", "scope_3"].map((scope) => {
              const value = Number(overview.emissions_by_scope[scope] || 0);
              return h(
                "div",
                { className: "bar-row", key: scope },
                h("strong", null, scope.replace("_", " ")),
                h("div", { className: "bar-track" }, h("div", { className: "bar-fill", style: { width: `${Math.max((value / maxScope) * 100, 2)}%` } })),
                h("span", null, formatNumber(value, 1))
              );
            })
          )
        )
      ),
      h(
        "div",
        { className: "grid two-col" },
        h(
          "section",
          { className: "panel" },
          h("div", { className: "panel-head" }, h("h2", null, "Top flags"), h("span", { className: "muted" }, "Quality signals")),
          h(
            "div",
            { className: "panel-body flag-list" },
            overview.top_flags.length
              ? overview.top_flags.map((item) =>
                  h(
                    "button",
                    {
                      className: `chip ${flagTone(item.flag)}`,
                      key: item.flag,
                      onClick: () => {
                        setFilter("flag", item.flag);
                        setActiveTab("review");
                      },
                    },
                    `${niceFlag(item.flag)} (${item.count})`
                  )
                )
              : h("span", { className: "muted" }, "No flags yet.")
          )
        ),
        h(
          "section",
          { className: "panel" },
          h("div", { className: "panel-head" }, h("h2", null, "Monthly CO2e"), h("span", { className: "muted" }, "kg by activity month")),
          h("div", { className: "panel-body" }, h(MonthlyChart, { monthly: overview.monthly || [] }))
        ),
        h(
          "section",
          { className: "panel" },
          h("div", { className: "panel-head" }, h("h2", null, "Recent batches"), h("span", { className: "muted" }, "Latest first")),
          h("div", { className: "panel-body" }, h(BatchList, { batches: overview.recent_batches || [] }))
        )
      )
    );
  }

  function WorkflowStrip({ totals, statusCounts }) {
    const steps = [
      { key: "needs_review", label: "Needs review", count: totals.needs_review || statusCounts.needs_review || 0 },
      { key: "failed", label: "Failed", count: totals.failed || statusCounts.failed || 0 },
      { key: "approved", label: "Approved", count: totals.approved || statusCounts.approved || 0 },
      { key: "locked", label: "Locked", count: totals.locked || statusCounts.locked || 0 },
      { key: "rejected", label: "Rejected", count: totals.rejected || statusCounts.rejected || 0 },
    ];
    return h(
      "section",
      { className: "panel" },
      h("div", { className: "panel-head" }, h("h2", null, "Review pipeline"), h("span", { className: "muted" }, "Analyst workflow")),
      h(
        "div",
        { className: "panel-body workflow" },
        steps.map((step) =>
          h("div", { className: "workflow-step", key: step.key }, h("strong", null, formatNumber(step.count, 0)), h("span", null, step.label))
        )
      )
    );
  }

  function MonthlyChart({ monthly }) {
    if (!monthly.length) {
      return h("div", { className: "empty" }, h("span", null, "No dated emissions yet."));
    }
    const max = Math.max(...monthly.map((item) => Number(item.co2e_kg || 0)), 1);
    return h(
      "div",
      { className: "monthly-chart" },
      monthly.map((item) => {
        const value = Number(item.co2e_kg || 0);
        const height = Math.max((value / max) * 100, 6);
        return h(
          "div",
          { className: "month-bar", key: item.month },
          h("div", { className: "track" }, h("div", { className: "fill", style: { height: `${height}%` } })),
          h("div", { className: "value" }, formatNumber(value, 0)),
          h("div", { className: "label" }, item.month)
        );
      })
    );
  }

  function SourceHealthCard({ source, setFilter, setActiveTab }) {
    const meta = SOURCE_META[source.source_type] || SOURCE_META.sap;
    return h(
      "button",
      {
        className: "source-card",
        onClick: () => {
          setFilter("source", source.source_type);
          setActiveTab("review");
        },
      },
        h("div", { className: "source-title" }, h("h3", null, meta.label), h("span", { className: `chip ${meta.tone}` }, h(Icon, { name: meta.icon }), source.rows)),
      h(
        "div",
        { className: "source-stats" },
        h("div", { className: "mini-stat" }, h("strong", null, source.needs_review), h("span", null, "Review")),
        h("div", { className: "mini-stat" }, h("strong", null, source.failed), h("span", null, "Failed")),
        h("div", { className: "mini-stat" }, h("strong", null, source.suspicious_rows || 0), h("span", null, "Suspicious")),
        h("div", { className: "mini-stat" }, h("strong", null, source.locked), h("span", null, "Locked"))
      ),
      h("span", { className: "muted" }, source.latest_batch ? source.latest_batch.filename : "No batches")
    );
  }

  function Intake({ overview, batches, uploadSource }) {
    return h(
      "div",
      { className: "workspace" },
      h(
        "section",
        { className: "panel" },
        h("div", { className: "panel-head" }, h("h2", null, "Upload source files"), h("span", { className: "muted" }, "CSV or JSON")),
        h(
          "div",
          { className: "panel-body source-grid" },
          SOURCE_TYPES.map((sourceType) => {
            const meta = SOURCE_META[sourceType];
            const inputId = `upload-${sourceType}`;
            const source = overview && overview.source_health ? overview.source_health.find((item) => item.source_type === sourceType) : null;
            return h(
              "div",
              { className: "source-card", key: sourceType },
              h("div", { className: "source-title" }, h("h3", null, meta.label), h("span", { className: `chip ${meta.tone}` }, h(Icon, { name: meta.icon }), source ? source.rows : 0)),
              h("p", { className: "muted" }, intakeCopy(sourceType)),
              h(
                "div",
                { className: "upload-zone" },
                h("span", { className: "muted" }, "CSV or JSON export"),
                h("a", { className: "link-button", href: SAMPLE_DOWNLOADS[sourceType], download: true }, h(Icon, { name: "download" }), "Sample")
              ),
              h("input", {
                id: inputId,
                className: "upload-input",
                type: "file",
                accept: sourceType === "travel" ? ".json,.csv" : ".csv",
                onChange: (event) => uploadSource(sourceType, event.target.files[0]),
              }),
              h("label", { className: "upload-button", htmlFor: inputId }, h(Icon, { name: "upload-cloud" }), "Upload file")
            );
          })
        )
      ),
      h(
        "section",
        { className: "panel" },
        h("div", { className: "panel-head" }, h("h2", null, "Batches"), h("span", { className: "muted" }, "Normalization outcomes")),
        h("div", { className: "panel-body" }, h(BatchList, { batches }))
      )
    );
  }

  function intakeCopy(sourceType) {
    return {
      sap: "S/4HANA material document and purchase order exports with plant, unit, quantity, supplier, and value columns.",
      utility: "Utility portal exports with meter ids, billing periods, usage units, demand, tariff, and bill amount.",
      travel: "Concur-like travel exports with flight, hotel, and ground segments. JSON and CSV are accepted.",
    }[sourceType];
  }

  function BatchList({ batches }) {
    if (!batches.length) return h("div", { className: "empty" }, "No batches yet.");
    return h(
      "div",
      { className: "table-wrap" },
      h(
        "table",
        null,
        h("thead", null, h("tr", null, ["Source", "File", "Rows", "Failed", "Suspicious", "Uploaded"].map((heading) => h("th", { key: heading }, heading)))),
        h(
          "tbody",
          null,
          batches.map((batch) =>
            h(
              "tr",
              { key: batch.id },
              h("td", null, SOURCE_META[batch.source_type] ? SOURCE_META[batch.source_type].label : batch.source_type),
              h("td", null, h("strong", null, batch.filename), h("div", { className: "muted" }, batch.uploaded_by)),
              h("td", null, `${batch.normalized_rows}/${batch.total_rows}`),
              h("td", null, batch.failed_rows),
              h("td", null, batch.suspicious_rows),
              h("td", null, new Date(batch.created_at).toLocaleString())
            )
          )
        )
      )
    );
  }

  function Review(props) {
    const {
      records,
      filters,
      changeFilter,
      searchDraft,
      setSearchDraft,
      selectedId,
      setSelectedId,
      selectedRecord,
      selectedIds,
      setSelectedIds,
      actOnRecord,
      bulkAction,
      saveRecord,
      loading,
    } = props;
    function toggle(id) {
      setSelectedIds((current) => (current.includes(id) ? current.filter((item) => item !== id) : current.concat(id)));
    }
    return h(
      "div",
      { className: "workspace" },
      h(
        "section",
        { className: "panel" },
        h(
          "div",
          { className: "panel-head" },
          h("h2", null, "Queue"),
          h(
            "div",
            { className: "toolbar" },
            h("button", { className: "ghost-button", onClick: () => bulkAction("approve") }, h(Icon, { name: "check" }), "Approve"),
            h("button", { className: "ghost-button", onClick: () => bulkAction("lock") }, h(Icon, { name: "lock" }), "Lock"),
            h("button", { className: "danger-button", onClick: () => bulkAction("reject") }, h(Icon, { name: "x" }), "Reject")
          )
        ),
        h(
          "div",
          { className: "panel-body" },
          h(
            "div",
            { className: "filters" },
            h("input", {
              className: "input",
              placeholder: "Search key, vendor, description",
              value: searchDraft,
              onChange: (event) => setSearchDraft(event.target.value),
            }),
            hSelect(filters.source, (value) => changeFilter("source", value), [["", "All sources"], ["sap", "SAP"], ["utility", "Utility"], ["travel", "Travel"]]),
            hSelect(filters.status, (value) => changeFilter("status", value), [["", "All status"], ["needs_review", "Needs review"], ["failed", "Failed"], ["approved", "Approved"], ["locked", "Locked"], ["rejected", "Rejected"]]),
            hSelect(filters.scope, (value) => changeFilter("scope", value), [["", "All scopes"], ["scope_1", "Scope 1"], ["scope_2", "Scope 2"], ["scope_3", "Scope 3"]]),
            hSelect(filters.flag, (value) => changeFilter("flag", value), FLAG_OPTIONS)
          ),
          h(ReviewSummary, { records }),
          filters.flag
            ? h("div", { className: "toolbar", style: { marginTop: 10 } }, h(FlagChip, { flag: filters.flag }), h("button", { className: "ghost-button", onClick: () => changeFilter("flag", "") }, h(Icon, { name: "x" }), "Clear flag"))
            : null
        )
      ),
      h(
        "div",
        { className: "grid two-col" },
        h(
          "section",
          { className: "panel" },
          h("div", { className: "panel-head" }, h("h2", null, `${records.length} rows`), loading ? h("span", { className: "muted" }, "Loading") : null),
          h("div", { className: "table-wrap" }, h(RecordTable, { records, selectedId, setSelectedId, selectedIds, toggle, actOnRecord }))
        ),
        h(
          "section",
          { className: "panel" },
          h("div", { className: "panel-head" }, h("h2", null, "Record detail"), selectedRecord ? h(StatusChip, { status: selectedRecord.status }) : null),
          h("div", { className: "panel-body" }, selectedRecord ? h(RecordDetail, { record: selectedRecord, actOnRecord, saveRecord }) : h("div", { className: "empty" }, "Select a row."))
        )
      )
    );
  }

  function hSelect(value, onChange, options) {
    return h(
      "select",
      { className: "select", value, onChange: (event) => onChange(event.target.value) },
      options.map(([optionValue, label]) => h("option", { key: optionValue, value: optionValue }, label))
    );
  }

  function ReviewSummary({ records }) {
    const total = records.length;
    const flagged = records.filter((record) => (record.quality_flags || []).length > 0).length;
    const failed = records.filter((record) => record.status === "failed").length;
    const totalCO2 = records.reduce((sum, record) => sum + Number(record.co2e_kg || 0), 0);
    return h(
      "div",
      { className: "grid", style: { gap: "12px", marginTop: "16px", gridTemplateColumns: "repeat(3, minmax(0, 1fr))" } },
      h(Metric, { label: "Queue snapshot", value: total, sub: `${failed} failed / ${flagged} flagged`, icon: "eye" }),
      h(Metric, { label: "CO2 in queue", value: `${formatNumber(totalCO2, 1)} kg`, sub: "Potential review impact", icon: "cloud" }),
      h(Metric, { label: "Flag density", value: `${total ? Math.round((flagged / total) * 100) : 0}%`, sub: "Rows with quality flags", icon: "alert-circle" })
    );
  }

  function RecordTable({ records, selectedId, setSelectedId, selectedIds, toggle, actOnRecord }) {
    if (!records.length) return h("div", { className: "empty" }, "No rows match the current filters.");
    return h(
      "table",
      null,
      h(
        "thead",
        null,
        h(
          "tr",
          null,
          h("th", null, ""),
          ["Source", "Activity", "Status", "Quantity", "CO2e", "Flags", "Actions"].map((heading) => h("th", { key: heading }, heading))
        )
      ),
      h(
        "tbody",
        null,
        records.map((record) =>
          h(
            "tr",
            {
              key: record.id,
              className: selectedId === record.id ? "selected" : "",
              onClick: () => setSelectedId(record.id),
            },
            h("td", null, h("input", { type: "checkbox", checked: selectedIds.includes(record.id), onChange: (event) => { event.stopPropagation(); toggle(record.id); }, onClick: (event) => event.stopPropagation() })),
            h("td", null, h("span", { className: `chip ${(SOURCE_META[record.source_type] || {}).tone || ""}` }, (SOURCE_META[record.source_type] || {}).label || record.source_type)),
            h(
              "td",
              { className: "row-title" },
              h("strong", null, record.description || record.source_record_key),
              h("span", { className: "muted" }, `${record.category} | ${formatDate(record.activity_date)}`),
              h("span", { className: "muted" }, record.facility_code || record.vendor || record.supplier || "No facility")
            ),
            h("td", null, h(StatusChip, { status: record.status })),
            h("td", null, `${formatNumber(record.canonical_quantity, 2)} ${record.canonical_unit || ""}`),
            h("td", null, record.co2e_kg == null ? "Not calculated" : formatNumber(record.co2e_kg, 1)),
            h("td", null, h("div", { className: "row-flags" }, (record.quality_flags || []).slice(0, 3).map((flag) => h(FlagChip, { key: flag, flag })), (record.quality_flags || []).length > 3 ? h("span", { className: "chip" }, `+${record.quality_flags.length - 3}`) : null)),
            h(
              "td",
              null,
              h(
                "div",
                { className: "toolbar" },
                h("button", { className: "icon-button", title: "Approve", onClick: (event) => { event.stopPropagation(); actOnRecord(record.id, "approve"); } }, h(Icon, { name: "check" })),
                h("button", { className: "icon-button", title: "Lock", onClick: (event) => { event.stopPropagation(); actOnRecord(record.id, "lock"); } }, h(Icon, { name: "lock" })),
                h("button", { className: "icon-button", title: "Reject", onClick: (event) => { event.stopPropagation(); actOnRecord(record.id, "reject", "Rejected from queue"); } }, h(Icon, { name: "x" }))
              )
            )
          )
        )
      )
    );
  }

  function RecordDetail({ record, actOnRecord, saveRecord }) {
    const [draft, setDraft] = useState({});
    const [detailTab, setDetailTab] = useState("summary");
    useEffect(() => {
      setDetailTab("summary");
    }, [record.id]);
    useEffect(() => {
      setDraft({
        description: record.description || "",
        canonical_quantity: record.canonical_quantity || "",
        canonical_unit: record.canonical_unit || "",
        spend_amount: record.spend_amount || "",
        currency: record.currency || "",
        analyst_notes: record.analyst_notes || "",
      });
    }, [record.id]);

    function update(key, value) {
      setDraft((current) => Object.assign({}, current, { [key]: value }));
    }

    return h(
      "div",
      { className: "detail" },
      h(
        "div",
        { className: "flag-list" },
        (record.quality_flags || []).length ? record.quality_flags.map((flag) => h(FlagChip, { key: flag, flag })) : h("span", { className: "chip good" }, "No flags")
      ),
      h(
        "div",
        { className: "tabs" },
        ["summary", "normalized", "raw"].map((tab) =>
          h(
            "button",
            { key: tab, className: `tab${detailTab === tab ? " active" : ""}`, onClick: () => setDetailTab(tab) },
            tab === "summary" ? "Summary" : tab === "normalized" ? "Normalized" : "Raw source"
          )
        )
      ),
      detailTab === "summary"
        ? h(
            "div",
            null,
            h(
              "div",
              { className: "detail-grid" },
              fieldView("Source key", record.source_record_key),
              fieldView("Scope", record.scope_label),
              fieldView("Factor", record.emission_factor_label || "No factor"),
              fieldView("Calculated", record.co2e_kg == null ? "Not calculated" : `${formatNumber(record.co2e_kg, 2)} kg CO2e`),
              fieldView("Facility", record.facility_code || "Unmapped"),
              fieldView("Edited", record.edited_from_source ? "Yes" : "No")
            ),
            h(
              "div",
              { className: "field" },
              h("label", { className: "label" }, "Description"),
              h("input", {
                className: "input",
                value: draft.description || "",
                onChange: (event) => update("description", event.target.value),
                disabled: record.status === "locked",
              })
            ),
            h(
              "div",
              { className: "detail-grid" },
              h("div", { className: "field" }, h("label", { className: "label" }, "Canonical quantity"), h("input", { className: "input", value: draft.canonical_quantity || "", onChange: (event) => update("canonical_quantity", event.target.value), disabled: record.status === "locked" })),
              h("div", { className: "field" }, h("label", { className: "label" }, "Canonical unit"), h("input", { className: "input", value: draft.canonical_unit || "", onChange: (event) => update("canonical_unit", event.target.value), disabled: record.status === "locked" })),
              h("div", { className: "field" }, h("label", { className: "label" }, "Spend"), h("input", { className: "input", value: draft.spend_amount || "", onChange: (event) => update("spend_amount", event.target.value), disabled: record.status === "locked" })),
              h("div", { className: "field" }, h("label", { className: "label" }, "Currency"), h("input", { className: "input", value: draft.currency || "", onChange: (event) => update("currency", event.target.value), disabled: record.status === "locked" }))
            ),
            h("div", { className: "field" }, h("label", { className: "label" }, "Analyst notes"), h("textarea", { className: "textarea", value: draft.analyst_notes || "", onChange: (event) => update("analyst_notes", event.target.value), disabled: record.status === "locked" })),
            h(
              "div",
              { className: "toolbar" },
              h("button", { className: "primary-button", onClick: () => saveRecord(record.id, draft), disabled: record.status === "locked" }, h(Icon, { name: "save" }), "Save"),
              h("button", { className: "ghost-button", onClick: () => actOnRecord(record.id, "approve"), disabled: record.status === "locked" || record.status === "failed" }, h(Icon, { name: "check" }), "Approve"),
              h("button", { className: "ghost-button", onClick: () => actOnRecord(record.id, "lock"), disabled: record.status !== "approved" }, h(Icon, { name: "lock" }), "Lock"),
              h("button", { className: "danger-button", onClick: () => actOnRecord(record.id, "reject", "Rejected in detail panel"), disabled: record.status === "locked" }, h(Icon, { name: "x" }), "Reject")
            )
          )
        : null,
      detailTab === "normalized" ? h("pre", { className: "payload" }, JSON.stringify(record.normalized_payload || {}, null, 2)) : null,
      detailTab === "raw" ? h("pre", { className: "payload" }, JSON.stringify(record.raw_record ? record.raw_record.raw_data : {}, null, 2)) : null
    );
  }

  function fieldView(label, value) {
    return h("div", { className: "mini-stat" }, h("span", null, label), h("strong", null, value || "None"));
  }

  function Audit({ audit, batches }) {
    return h(
      "div",
      { className: "grid two-col" },
      h(
        "section",
        { className: "panel" },
        h("div", { className: "panel-head" }, h("h2", null, "Events"), h("span", { className: "muted" }, `${audit.length} latest`)),
        h("div", { className: "panel-body" }, h(AuditSummary, { audit })),
        h(
          "div",
          { className: "panel-body timeline" },
          audit.length
            ? audit.map((event) =>
                h(
                  "div",
                  { className: "event", key: event.id },
                  h("span", { className: "muted" }, new Date(event.created_at).toLocaleString()),
                  h(
                    "div",
                    null,
                    h("strong", null, event.action.replaceAll("_", " ")),
                    h("div", { className: "muted" }, `${event.actor} | ${event.activity_source_key || event.batch_filename || "batch"}`),
                    event.reason ? h("div", null, event.reason) : null
                  )
                )
              )
            : h("div", { className: "empty" }, "No audit events yet.")
        )
      ),
      h(
        "section",
        { className: "panel" },
        h("div", { className: "panel-head" }, h("h2", null, "Batches"), h("span", { className: "muted" }, "Source of truth")),
        h("div", { className: "panel-body" }, h(BatchList, { batches }))
      )
    );
  }

  function AuditSummary({ audit }) {
    const actionCounts = audit.reduce((counts, event) => {
      counts[event.action] = (counts[event.action] || 0) + 1;
      return counts;
    }, {});
    const actorCounts = audit.reduce((counts, event) => {
      counts[event.actor] = (counts[event.actor] || 0) + 1;
      return counts;
    }, {});

    return h(
      "div",
      { className: "grid", style: { gap: "12px", marginBottom: "14px", gridTemplateColumns: "repeat(2, minmax(0, 1fr))" } },
      h(
        "div",
        { className: "panel" },
        h("div", { className: "panel-head" }, h("h3", null, "Actions")),
        h(
          "div",
          { className: "panel-body" },
          Object.entries(actionCounts).map(([action, count]) =>
            h(
              "div",
              { className: "mini-stat", key: action },
              h("strong", null, count),
              h("span", null, action.replaceAll("_", " "))
            )
          )
        )
      ),
      h(
        "div",
        { className: "panel" },
        h("div", { className: "panel-head" }, h("h3", null, "Reviewers")),
        h(
          "div",
          { className: "panel-body" },
          Object.entries(actorCounts).map(([actorName, count]) =>
            h(
              "div",
              { className: "mini-stat", key: actorName },
              h("strong", null, count),
              h("span", null, actorName)
            )
          )
        )
      )
    );
  }

  ReactDOM.createRoot(document.getElementById("root")).render(h(App));
})();
