/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart } from "@odoo/owl";

const CATEGORY_CONFIG = {
    credit_import: { label: "Vencimientos Crédito — Importación", icon: "📦", color: "#2196F3" },
    credit_freight_sea: { label: "Fletes Marítimos", icon: "🚢", color: "#00BCD4" },
    credit_freight_land: { label: "Fletes Terrestres", icon: "🚛", color: "#FF9800" },
    advance: { label: "Anticipos", icon: "💰", color: "#9C27B0" },
    balance: { label: "Balances / Liquidaciones", icon: "📑", color: "#F44336" },
    import_tax: { label: "Impuestos de Importación", icon: "🏛️", color: "#607D8B" },
};

const STATE_BADGES = {
    paid: { label: "Pagado", class: "bg-success" },
    partial: { label: "Parcial", class: "bg-info" },
    pending: { label: "Pendiente", class: "bg-warning text-dark" },
    overdue: { label: "Vencido", class: "bg-danger" },
    draft: { label: "Borrador", class: "bg-secondary" },
};

class ImportPaymentDashboard extends Component {
    static template = "somgroup_payment_terms.ImportPaymentDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            months: {},
            reports: [],
            selectedReportId: false,
            selectedMonth: null,
            activeTab: "all",
            loading: true,
            error: false,
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        this.state.loading = true;
        this.state.error = false;
        try {
            const data = await this.orm.call(
                "import.payment.report",
                "get_dashboard_data",
                [this.state.selectedReportId || false],
            );
            this.state.months = data.months || {};
            this.state.reports = data.reports || [];

            // Seleccionar primer mes si no hay selección
            const monthKeys = Object.keys(this.state.months).sort();
            if (monthKeys.length && !this.state.selectedMonth) {
                this.state.selectedMonth = monthKeys[0];
            }
        } catch (e) {
            this.state.error = e.message || "Error al cargar datos";
            console.error("Dashboard error:", e);
        }
        this.state.loading = false;
    }

    // ─── Getters ────────────────────────────────────────────────────────

    get monthKeys() {
        return Object.keys(this.state.months).sort();
    }

    get currentMonthData() {
        if (!this.state.selectedMonth || !this.state.months[this.state.selectedMonth]) {
            return null;
        }
        return this.state.months[this.state.selectedMonth];
    }

    get currentSummary() {
        return this.currentMonthData?.summary || {};
    }

    get filteredLines() {
        if (!this.currentMonthData) return [];
        const lines = this.currentMonthData.lines || [];
        if (this.state.activeTab === "all") return lines;
        return lines.filter((l) => l.commitment_category === this.state.activeTab);
    }

    get summaryCards() {
        const s = this.currentSummary;
        return [
            { label: "Vencim. Crédito", usd: s.credit_import_usd, mxn: s.credit_import_mxn, color: "#2196F3" },
            { label: "Fletes Marítimos", usd: s.freight_sea_usd, mxn: s.freight_sea_mxn, color: "#00BCD4" },
            { label: "Fletes Terrestres", usd: 0, mxn: s.freight_land_mxn, color: "#FF9800" },
            { label: "Anticipos", usd: s.advance_usd, mxn: s.advance_mxn, color: "#9C27B0" },
            { label: "Balances", usd: s.balance_usd, mxn: s.balance_mxn, color: "#F44336" },
            { label: "Impuestos", usd: 0, mxn: s.tax_mxn, color: "#607D8B" },
        ];
    }

    get tabs() {
        const tabs = [{ key: "all", label: "Todo", icon: "📋" }];
        for (const [key, cfg] of Object.entries(CATEGORY_CONFIG)) {
            const count = (this.currentMonthData?.lines || []).filter(
                (l) => l.commitment_category === key
            ).length;
            if (count > 0) {
                tabs.push({ key, label: cfg.label, icon: cfg.icon, count });
            }
        }
        return tabs;
    }

    // ─── Helpers ────────────────────────────────────────────────────────

    formatCurrency(amount, currency) {
        if (!amount && amount !== 0) return "—";
        const val = parseFloat(amount) || 0;
        if (currency === "MXN") {
            return "$" + val.toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        }
        return "$" + val.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " USD";
    }

    formatMXN(amount) {
        return this.formatCurrency(amount, "MXN");
    }

    formatUSD(amount) {
        return this.formatCurrency(amount, "USD");
    }

    formatDate(dateStr) {
        if (!dateStr) return "—";
        const d = new Date(dateStr + "T00:00:00");
        return d.toLocaleDateString("es-MX", { day: "2-digit", month: "short", year: "numeric" });
    }

    getCategoryConfig(cat) {
        return CATEGORY_CONFIG[cat] || { label: cat, icon: "📄", color: "#999" };
    }

    getStateBadge(state) {
        return STATE_BADGES[state] || STATE_BADGES.draft;
    }

    getRowClass(line) {
        if (line.state === "overdue") return "table-danger";
        if (line.state === "paid") return "table-success";
        if (line.alert_level === "warning") return "table-warning";
        return "";
    }

    // ─── Acciones ───────────────────────────────────────────────────────

    onSelectMonth(ev) {
        this.state.selectedMonth = ev.target.value;
        this.state.activeTab = "all";
    }

    onSelectReport(ev) {
        const val = ev.target.value;
        this.state.selectedReportId = val ? parseInt(val) : false;
        this.state.selectedMonth = null;
        this.loadData();
    }

    onClickTab(tabKey) {
        this.state.activeTab = tabKey;
    }

    async onRefresh() {
        await this.loadData();
    }

    onOpenReport() {
        if (!this.state.selectedReportId) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "import.payment.report",
            res_id: this.state.selectedReportId,
            views: [[false, "form"]],
        });
    }

    onOpenLine(lineId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "import.payment.line",
            res_id: lineId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async onMarkPaid(lineId) {
        await this.orm.call("import.payment.line", "action_mark_paid", [[lineId]]);
        await this.loadData();
    }

    onCreateReport() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "import.payment.report",
            views: [[false, "form"]],
            target: "current",
        });
    }

    onOpenAllLines() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "import.payment.line",
            views: [[false, "list"], [false, "form"]],
            target: "current",
            domain: [],
            context: { search_default_group_category: 1 },
        });
    }

    onOpenProjection() {
        const today = new Date().toISOString().split("T")[0];
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "import.payment.line",
            name: "Proyección Meses Futuros",
            views: [[false, "list"], [false, "pivot"], [false, "graph"], [false, "form"]],
            target: "current",
            domain: [
                ["due_date", ">=", today],
                ["state", "in", ["pending", "partial"]],
            ],
            context: { search_default_group_month: 1 },
        });
    }
}

registry.category("actions").add("import_payment_dashboard", ImportPaymentDashboard);
