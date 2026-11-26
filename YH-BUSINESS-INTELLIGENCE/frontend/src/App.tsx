import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import {
  Activity, ArrowDownLeft, ArrowUpRight, Boxes, Building2, ChartNoAxesCombined, Check,
  ChevronDown, CircleDollarSign, FileText, Globe2, LayoutDashboard, LogOut, Menu, Package,
  Plus, RefreshCw, Search, Settings2, ShieldCheck, ShoppingCart, Sparkles, Users, Wallet,
  X,
} from "lucide-react";
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "./services/api";

type Company = { id: number; name: string; functional_currency_code: string; country_code?: string | null };
type Row = Record<string, any>;
type Tab = "overview" | "sales" | "purchases" | "inventory" | "finance" | "masterdata" | "analytics";

const copy = {
  en: {
    overview: "Overview", sales: "Sales", purchases: "Purchases", inventory: "Inventory",
    finance: "Finance", masterdata: "Master data", analytics: "Analytics", workspace: "WORKSPACE",
    business: "BUSINESS INTELLIGENCE", period: "This month", revenue: "Revenue",
    expenses: "Expenses", cogs: "Cost of goods", profit: "Net profit estimate", invoices: "Invoices",
    inventoryUnits: "Units on hand", activity: "Revenue trend", insights: "Local insights",
    latest: "Recent activity", company: "Company", refresh: "Refresh data", language: "العربية",
    signOut: "Sign out", signIn: "Sign in to your workspace", email: "Work email", password: "Password",
    signInButton: "Continue", loading: "Loading…", noData: "No records yet.", newInvoice: "New invoice",
    newBill: "New bill", newExpense: "Record expense", newMovement: "Record stock movement",
    addCustomer: "Add customer", addProduct: "Add product", addWarehouse: "Add warehouse",
    post: "Post", draft: "Draft", status: "Status", number: "Number", date: "Date",
    customer: "Customer", supplier: "Supplier", product: "Product", warehouse: "Warehouse",
    quantity: "Quantity", price: "Unit price", cost: "Unit cost", currency: "Currency",
    tax: "Tax", category: "Category", description: "Description", amount: "Amount", save: "Save draft",
    create: "Create", close: "Close", accounts: "Trial balance", debit: "Debit", credit: "Credit",
    localEngine: "Local rules engine", localLabel: "Runs locally • no external AI service",
    powered: "Powered by your posted records", apiOffline: "Can’t reach the API. Check the backend and API address.",
    emptyInsights: "Insights appear after posting records.", dashboard: "Business overview", operating: "OPERATIONS",
    name: "Name", code: "Code", sku: "SKU", type: "Type", inventoryValue: "Inventory position",
  },
  ar: {
    overview: "نظرة عامة", sales: "المبيعات", purchases: "المشتريات", inventory: "المخزون",
    finance: "المالية", masterdata: "البيانات الأساسية", analytics: "التحليلات", workspace: "مساحة العمل",
    business: "ذكاء الأعمال", period: "هذا الشهر", revenue: "الإيرادات", expenses: "المصروفات",
    cogs: "تكلفة البضاعة", profit: "تقدير صافي الربح", invoices: "الفواتير", inventoryUnits: "الوحدات المتاحة",
    activity: "اتجاه الإيرادات", insights: "تحليلات محلية", latest: "أحدث النشاطات", company: "الشركة",
    refresh: "تحديث البيانات", language: "English", signOut: "تسجيل الخروج", signIn: "تسجيل الدخول",
    email: "البريد الإلكتروني", password: "كلمة المرور", signInButton: "متابعة", loading: "جار التحميل…",
    noData: "لا توجد سجلات بعد.", newInvoice: "فاتورة جديدة", newBill: "فاتورة شراء جديدة",
    newExpense: "تسجيل مصروف", newMovement: "تسجيل حركة مخزون", addCustomer: "إضافة عميل",
    addProduct: "إضافة منتج", addWarehouse: "إضافة مخزن", post: "ترحيل", draft: "مسودة",
    status: "الحالة", number: "الرقم", date: "التاريخ", customer: "العميل", supplier: "المورد",
    product: "المنتج", warehouse: "المخزن", quantity: "الكمية", price: "سعر الوحدة",
    cost: "تكلفة الوحدة", currency: "العملة", tax: "الضريبة", category: "الفئة",
    description: "الوصف", amount: "المبلغ", save: "حفظ كمسودة", create: "إنشاء", close: "إغلاق",
    accounts: "ميزان المراجعة", debit: "مدين", credit: "دائن", localEngine: "محرك قواعد محلي",
    localLabel: "يعمل محليًا • دون خدمة ذكاء اصطناعي خارجية", powered: "مبني على سجلاتك المُرحّلة",
    apiOffline: "تعذر الاتصال بالخادم. تحقق من تشغيله وعنوان API.", emptyInsights: "ستظهر التحليلات بعد ترحيل السجلات.",
    dashboard: "ملخص الأعمال", operating: "التشغيل", name: "الاسم", code: "الرمز", sku: "رمز المنتج",
    type: "النوع", inventoryValue: "حالة المخزون",
  },
} as const;

const nav: { id: Tab; icon: typeof LayoutDashboard }[] = [
  { id: "overview", icon: LayoutDashboard }, { id: "sales", icon: ShoppingCart },
  { id: "purchases", icon: ArrowDownLeft }, { id: "inventory", icon: Boxes },
  { id: "finance", icon: Wallet }, { id: "masterdata", icon: Users },
  { id: "analytics", icon: ChartNoAxesCombined },
];

function formatMoney(value: number | string | undefined, currency: string) {
  const amount = Number(value || 0);
  return new Intl.NumberFormat(undefined, { style: "currency", currency, maximumFractionDigits: 2 }).format(amount);
}

function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem("yhbi_access_token") || "");
  const [companies, setCompanies] = useState<Company[]>([]);
  const [companyId, setCompanyId] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [language, setLanguage] = useState<"en" | "ar">("en");
  const [data, setData] = useState<Row>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const t = copy[language];
  const company = companies.find((item) => item.id === companyId);

  const signOut = useCallback(() => {
    sessionStorage.removeItem("yhbi_access_token");
    setToken(""); setCompanies([]); setCompanyId(null); setData({});
  }, []);

  useEffect(() => {
    if (!token) return;
    let live = true;
    api<Company[]>("/companies", { token }).then((items) => {
      if (!live) return;
      setCompanies(items);
      setCompanyId((previous) => items.some((item) => item.id === previous) ? previous : (items[0]?.id ?? null));
      if (items.length === 0) setError("Your account has no active company membership yet.");
    }).catch((reason: Error) => { if (live) { setError(reason.message); signOut(); } });
    return () => { live = false; };
  }, [token, signOut]);

  const reload = useCallback(async () => {
    if (!token || !companyId) return;
    setLoading(true); setError("");
    try {
      const opts = { token, companyId };
      let next: Row = {};
      if (activeTab === "overview" || activeTab === "analytics") {
        const [overview, trend, insights] = await Promise.all([
          api<Row>("/analytics/overview", opts), api<Row>("/analytics/revenue-trend?months=6", opts),
          api<Row>("/analytics/insights", opts),
        ]);
        next = { overview, trend, insights };
      } else if (activeTab === "sales") {
        const [invoices, customers, products, warehouses, currencies] = await Promise.all([
          api<Row[]>("/sales/invoices", opts), api<Row[]>("/customers", opts), api<Row[]>("/products", opts),
          api<Row[]>("/warehouses", opts), api<Row[]>("/currencies"),
        ]);
        next = { invoices, customers, products, warehouses, currencies };
      } else if (activeTab === "purchases") {
        const [bills, suppliers, products, warehouses, currencies] = await Promise.all([
          api<Row[]>("/purchases/bills", opts), api<Row[]>("/suppliers", opts), api<Row[]>("/products", opts),
          api<Row[]>("/warehouses", opts), api<Row[]>("/currencies"),
        ]);
        next = { bills, suppliers, products, warehouses, currencies };
      } else if (activeTab === "inventory") {
        const [balances, products, warehouses] = await Promise.all([
          api<Row[]>("/inventory/balances", opts), api<Row[]>("/products", opts), api<Row[]>("/warehouses", opts),
        ]);
        next = { balances, products, warehouses };
      } else if (activeTab === "finance") {
        const [trial, expenses, currencies] = await Promise.all([
          api<Row>("/finance/trial-balance", opts), api<Row[]>("/expenses", opts), api<Row[]>("/currencies"),
        ]);
        next = { trial, expenses, currencies };
      } else {
        const [customers, suppliers, products, warehouses] = await Promise.all([
          api<Row[]>("/customers", opts), api<Row[]>("/suppliers", opts), api<Row[]>("/products", opts),
          api<Row[]>("/warehouses", opts),
        ]);
        next = { customers, suppliers, products, warehouses };
      }
      setData(next);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t.apiOffline);
    } finally { setLoading(false); }
  }, [activeTab, companyId, t.apiOffline, token]);

  useEffect(() => { void reload(); }, [reload]);

  async function mutate(path: string, body: unknown, method = "POST") {
    if (!token || !companyId) return;
    setError("");
    try {
      await api(path, { token, companyId, method, body });
      await reload();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "The change could not be saved."); }
  }

  if (!token) return <Login t={t} onLogin={(newToken) => {
    sessionStorage.setItem("yhbi_access_token", newToken); setError(""); setToken(newToken);
  }} error={error} />;

  if (!company && companies.length === 0) return <div className="loading-screen"><div className="spinner" />{t.loading}</div>;

  const title = activeTab === "overview" ? t.dashboard : t[activeTab];
  const content: Record<Tab, ReactNode> = {
    overview: <Overview data={data} company={company} t={t} />,
    analytics: <Analytics data={data} company={company} t={t} />,
    sales: <Sales data={data} company={company} t={t} mutate={mutate} />,
    purchases: <Purchases data={data} company={company} t={t} mutate={mutate} />,
    inventory: <Inventory data={data} company={company} t={t} mutate={mutate} />,
    finance: <Finance data={data} company={company} t={t} mutate={mutate} />,
    masterdata: <MasterData data={data} t={t} mutate={mutate} />,
  };

  return <div className={`app-shell ${language === "ar" ? "rtl" : ""}`} dir={language === "ar" ? "rtl" : "ltr"}>
    {drawerOpen && <button className="mobile-scrim" aria-label="Close menu" onClick={() => setDrawerOpen(false)} />}
    <aside className={`sidebar ${drawerOpen ? "open" : ""}`}>
      <div className="brand"><div className="brand-mark">YH</div><div><strong>YH</strong><span>{t.business}</span></div>
        <button className="icon-button mobile-close" onClick={() => setDrawerOpen(false)} aria-label="Close menu"><X size={17} /></button></div>
      <div className="side-label">{t.workspace}</div>
      <nav className="nav-list" aria-label={t.workspace}>{nav.map(({ id, icon: Icon }) => <button key={id}
        className={`nav-item ${activeTab === id ? "active" : ""}`} onClick={() => { setActiveTab(id); setDrawerOpen(false); }}>
        <Icon size={18} strokeWidth={1.8} /><span>{t[id]}</span>{id === "overview" && activeTab === id && <span className="nav-dot" />}
      </button>)}</nav>
      <div className="sidebar-spacer" />
      <div className="local-badge"><span className="pulse" /><div><b>{t.localEngine}</b><small>{language === "en" ? "Private and explainable" : "خاص وقابل للتفسير"}</small></div><ShieldCheck size={16} /></div>
      <div className="profile"><div className="avatar">{companies[0]?.name?.slice(0, 1) || "Y"}</div><div className="profile-copy"><b>{companies[0]?.name || "YH Workspace"}</b><small>{language === "en" ? "Secure workspace" : "مساحة عمل آمنة"}</small></div>
        <button className="icon-button" title={t.signOut} onClick={signOut}><LogOut size={16} /></button></div>
    </aside>
    <main className="main-area">
      <header className="topbar">
        <button className="icon-button menu-trigger" onClick={() => setDrawerOpen(true)} aria-label="Open menu"><Menu size={19} /></button>
        <div className="crumb"><span>{t.business}</span><b>/</b><strong>{title}</strong></div>
        <div className="top-actions">
          <label className="company-select"><Building2 size={16} /><select value={companyId || ""}
            onChange={(event) => setCompanyId(Number(event.target.value))} aria-label={t.company}>
            {companies.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select><ChevronDown size={14} /></label>
          <button className="icon-button language-button" onClick={() => setLanguage(language === "en" ? "ar" : "en")} title={t.language}><Globe2 size={17} /><span>{t.language}</span></button>
          <button className="icon-button" onClick={() => void reload()} title={t.refresh} aria-label={t.refresh}><RefreshCw size={17} className={loading ? "spin" : ""} /></button>
          <div className="top-avatar">{company?.name.slice(0, 1) || "Y"}</div>
        </div>
      </header>
      <section className="page-content">
        <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line" />{t.operating}</div><h1>{title}</h1>
          <p>{company?.name} <span className="muted-dot">·</span> {company?.functional_currency_code} <span className="muted-dot">·</span> {t.period}</p></div>
          {activeTab === "overview" && <div className="period-pill"><Activity size={15} />{t.period}</div>}
        </div>
        {error && <div className="error-banner"><span>{error}</span><button className="icon-button" onClick={() => setError("")}><X size={15} /></button></div>}
        {loading && !Object.keys(data).length ? <div className="loading-screen"><div className="spinner" />{t.loading}</div> : content[activeTab]}
        <footer className="page-footer"><span>YH BUSINESS INTELLIGENCE <i>·</i> {t.localLabel}</span><span>v0.1.0 <i>·</i> {company?.functional_currency_code} functional reporting</span></footer>
      </section>
    </main>
  </div>;
}

function Login({ t, onLogin, error }: { t: typeof copy.en | typeof copy.ar; onLogin: (token: string) => void; error: string }) {
  const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [busy, setBusy] = useState(false); const [localError, setLocalError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setLocalError("");
    try { const result = await api<{ access_token: string }>("/auth/token", { method: "POST", body: { email, password } }); onLogin(result.access_token); }
    catch (reason) { setLocalError(reason instanceof Error ? reason.message : "Sign in failed"); }
    finally { setBusy(false); }
  }
  return <div className="login-screen"><div className="login-art"><div className="orb orb-one" /><div className="orb orb-two" />
    <div className="login-brand"><div className="brand-mark large">YH</div><span>YH BUSINESS INTELLIGENCE</span></div>
    <div className="login-pitch"><span className="gold-kicker"><Sparkles size={14} /> PRIVATE BUSINESS INTELLIGENCE</span>
      <h1>Make every<br /><em>number</em> count.</h1><p>One clear view of your finance, operations, and company performance.</p>
      <div className="login-footnote"><ShieldCheck size={15} /> Local analytics. Company-scoped access. Functional currency reporting.</div>
    </div><div className="login-grid" /></div>
    <div className="login-panel"><form className="login-card" onSubmit={submit}><div className="login-mini-logo">YH <span>· BUSINESS INTELLIGENCE</span></div>
      <div className="login-heading"><div className="login-symbol"><CircleDollarSign size={21} /></div><h2>{t.signIn}</h2><p>Enter the administrator account created during setup.</p></div>
      <label className="field-label">{t.email}<span><Users size={13} /></span><input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="username" required /></label>
      <label className="field-label">{t.password}<span><ShieldCheck size={13} /></span><input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required /></label>
      {(localError || error) && <div className="form-error">{localError || error}</div>}
      <button className="primary-button login-submit" disabled={busy}>{busy ? t.loading : t.signInButton}<ArrowUpRight size={16} /></button>
      <div className="login-secure"><ShieldCheck size={14} /> Your password is never stored in this browser.</div>
    </form><div className="login-copyright">© 2026 YH Business Intelligence <span>·</span> Secure workspace</div></div>
  </div>;
}

function Overview({ data, company, t }: { data: Row; company?: Company; t: typeof copy.en | typeof copy.ar }) {
  const overview = data.overview || {}; const trend = data.trend?.months || []; const insights = data.insights?.insights || [];
  const kpis = [
    { label: t.revenue, value: formatMoney(overview.revenue, overview.functional_currency_code || company?.functional_currency_code || "USD"), icon: ArrowDownLeft, tone: "gold", note: `${overview.invoice_count || 0} ${t.invoices.toLowerCase()}` },
    { label: t.expenses, value: formatMoney(overview.expenses, overview.functional_currency_code || company?.functional_currency_code || "USD"), icon: ArrowUpRight, tone: "rose", note: `${overview.expense_count || 0} ${t.status.toLowerCase()}` },
    { label: t.cogs, value: formatMoney(overview.cost_of_goods_sold, overview.functional_currency_code || company?.functional_currency_code || "USD"), icon: Package, tone: "blue", note: "Posted cost" },
    { label: t.profit, value: formatMoney(overview.net_profit_estimate, overview.functional_currency_code || company?.functional_currency_code || "USD"), icon: CircleDollarSign, tone: Number(overview.net_profit_estimate || 0) >= 0 ? "green" : "rose", note: "Revenue − costs" },
  ];
  return <>
    <div className="kpi-grid">{kpis.map((kpi) => <div className="kpi-card" key={kpi.label}><div className="kpi-top"><span>{kpi.label}</span><span className={`kpi-icon ${kpi.tone}`}><kpi.icon size={17} /></span></div>
      <strong>{kpi.value}</strong><div className="kpi-foot"><span className="kpi-period"><span className="tiny-dot" />{t.period}</span><span>{kpi.note}</span></div></div>)}</div>
    <div className="overview-grid">
      <section className="panel chart-panel"><div className="panel-heading"><div><h2>{t.activity}</h2><p>{t.powered}</p></div><span className="chart-period">Last 6 months</span></div>
        <div className="chart-legend"><span><i className="legend-dot" />{t.revenue}</span><small>{company?.functional_currency_code}</small></div>
        <div className="chart-wrap">{trend.length ? <ResponsiveContainer width="100%" height="100%"><LineChart data={trend} margin={{ top: 12, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="#292b2e" strokeDasharray="3 5" vertical={false} /><XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fill: "#777b80", fontSize: 11 }} tickMargin={12} />
          <YAxis tickLine={false} axisLine={false} tick={{ fill: "#777b80", fontSize: 11 }} width={42} tickFormatter={(v) => Number(v) >= 1000 ? `${Number(v) / 1000}k` : String(v)} />
          <Tooltip contentStyle={{ background: "#1b1d20", border: "1px solid #34373b", borderRadius: 10, color: "#f4f1e9" }} formatter={(value) => [formatMoney(Number(value), company?.functional_currency_code || "USD"), t.revenue]} />
          <Line type="monotone" dataKey="revenue" stroke="#d9b66d" strokeWidth={2.6} dot={{ fill: "#d9b66d", stroke: "#15171a", strokeWidth: 3, r: 4 }} activeDot={{ r: 5, strokeWidth: 0 }} /></LineChart></ResponsiveContainer>
          : <div className="empty-chart"><div className="empty-chart-mark"><ChartNoAxesCombined size={19} /></div><span>{t.noData}</span></div>}</div>
      </section>
      <section className="panel insights-panel"><div className="panel-heading"><div><div className="insight-title"><span className="sparkle-icon"><Sparkles size={15} /></span><h2>{t.insights}</h2></div><p>{t.localLabel}</p></div><span className="engine-tag">RULES</span></div>
        <div className="insights-list">{insights.length ? insights.map((item: Row) => <div className={`insight-item ${item.severity}`} key={item.code}><span className="insight-status">{item.severity === "positive" ? <Check size={14} /> : <Activity size={14} />}</span><div><b>{item.code.replaceAll("_", " ")}</b><p>{item.message}</p></div></div>) : <div className="insight-empty"><Sparkles size={20} /><span>{t.emptyInsights}</span></div>}</div>
        <div className="insight-disclaimer"><ShieldCheck size={13} /> Deterministic rules, based on posted records only.</div>
      </section>
    </div>
    <section className="panel summary-panel"><div className="panel-heading"><div><h2>{t.latest}</h2><p>Current reporting window</p></div><span className="live-tag"><i />LIVE</span></div>
      <div className="summary-strip"><SummaryMetric icon={<FileText size={17} />} label={t.invoices} value={overview.invoice_count || 0} />
        <SummaryMetric icon={<Package size={17} />} label={t.inventoryUnits} value={Number(overview.inventory_units || 0).toLocaleString()} />
        <SummaryMetric icon={<CircleDollarSign size={17} />} label="Functional currency" value={overview.functional_currency_code || company?.functional_currency_code || "—"} />
        <SummaryMetric icon={<ShieldCheck size={17} />} label="Data isolation" value="Company scoped" />
      </div>
    </section>
  </>;
}

function SummaryMetric({ icon, label, value }: { icon: ReactNode; label: string; value: string | number }) {
  return <div className="summary-metric"><span className="summary-icon">{icon}</span><div><small>{label}</small><b>{value}</b></div></div>;
}

function Analytics({ data, company, t }: { data: Row; company?: Company; t: typeof copy.en | typeof copy.ar }) {
  return <div className="analytics-layout"><Overview data={data} company={company} t={t} />
    <section className="panel method-panel"><div className="method-icon"><Settings2 size={19} /></div><div><h3>How these insights are produced</h3>
      <p>The local rules engine evaluates posted invoices, posted expenses, and posted journal entries for the selected company and period. It does not send business data to an external AI service.</p></div><span className="engine-tag">LOCAL</span></section></div>;
}

function Sales({ data, company, t, mutate }: { data: Row; company?: Company; t: typeof copy.en | typeof copy.ar; mutate: (path: string, body: unknown) => Promise<void> }) {
  const [show, setShow] = useState(false); const invoices = data.invoices || [];
  return <div className="module-stack"><div className="module-toolbar"><div><h2>{t.sales}</h2><p>Customer invoices and posting status</p></div><button className="primary-button" onClick={() => setShow(!show)}><Plus size={16} />{t.newInvoice}</button></div>
    {show && <InvoiceForm data={data} company={company} t={t} onCancel={() => setShow(false)} onSave={async (body) => { await mutate("/sales/invoices", body); setShow(false); }} />}
    <section className="panel table-panel"><TableHead columns={[t.number, t.customer, t.date, t.amount, t.status]} />
      {invoices.length ? invoices.map((row: Row) => <div className="table-row" key={row.id}><b>{row.invoice_number}</b><span>{data.customers?.find((c: Row) => c.id === row.customer_id)?.name || `#${row.customer_id}`}</span><span>{row.invoice_date}</span><span>{formatMoney(row.total_amount, row.currency_code)}</span><span className={`status-pill ${row.status.toLowerCase()}`}>{row.status}</span>{row.status === "DRAFT" && <button className="row-action" onClick={() => void mutate(`/sales/invoices/${row.id}/post`, {})}>{t.post}</button>}</div>) : <EmptyRow text={t.noData} />}</section></div>;
}

function Purchases({ data, company, t, mutate }: { data: Row; company?: Company; t: typeof copy.en | typeof copy.ar; mutate: (path: string, body: unknown) => Promise<void> }) {
  const [show, setShow] = useState(false); const bills = data.bills || [];
  return <div className="module-stack"><div className="module-toolbar"><div><h2>{t.purchases}</h2><p>Supplier bills and inventory receipts</p></div><button className="primary-button" onClick={() => setShow(!show)}><Plus size={16} />{t.newBill}</button></div>
    {show && <PurchaseForm data={data} company={company} t={t} onCancel={() => setShow(false)} onSave={async (body) => { await mutate("/purchases/bills", body); setShow(false); }} />}
    <section className="panel table-panel"><TableHead columns={[t.number, t.supplier, t.date, t.amount, t.status]} />
      {bills.length ? bills.map((row: Row) => <div className="table-row" key={row.id}><b>{row.bill_number}</b><span>{data.suppliers?.find((c: Row) => c.id === row.supplier_id)?.name || `#${row.supplier_id}`}</span><span>{row.bill_date}</span><span>{formatMoney(row.total_amount, row.currency_code)}</span><span className={`status-pill ${row.status.toLowerCase()}`}>{row.status}</span>{row.status === "DRAFT" && <button className="row-action" onClick={() => void mutate(`/purchases/bills/${row.id}/post`, {})}>{t.post}</button>}</div>) : <EmptyRow text={t.noData} />}</section></div>;
}

function InvoiceForm({ data, company, t, onCancel, onSave }: { data: Row; company?: Company; t: typeof copy.en | typeof copy.ar; onCancel: () => void; onSave: (body: Row) => Promise<void> }) {
  const [form, setForm] = useState({ customer_id: "", product_id: "", warehouse_id: "", invoice_number: `INV-${Date.now().toString().slice(-6)}`,
    invoice_date: new Date().toISOString().slice(0, 10), currency_code: company?.functional_currency_code || "USD", quantity: "1", unit_price: "0", tax_amount: "0" });
  const [busy, setBusy] = useState(false);
  const change = (key: string, value: string) => setForm((current) => ({ ...current, [key]: value }));
  async function submit(event: FormEvent) { event.preventDefault(); setBusy(true); try { await onSave({ customer_id: Number(form.customer_id), invoice_number: form.invoice_number, invoice_date: form.invoice_date, currency_code: form.currency_code, tax_amount: form.tax_amount, lines: [{ product_id: Number(form.product_id), warehouse_id: Number(form.warehouse_id), quantity: form.quantity, unit_price: form.unit_price }] }); } finally { setBusy(false); } }
  return <FormPanel title={t.newInvoice} onClose={onCancel} onSubmit={submit} busy={busy} t={t}>
    <SelectField label={t.customer} value={form.customer_id} onChange={(v) => change("customer_id", v)} options={data.customers || []} />
    <TextField label={t.number} value={form.invoice_number} onChange={(v) => change("invoice_number", v)} />
    <TextField label={t.date} type="date" value={form.invoice_date} onChange={(v) => change("invoice_date", v)} />
    <SelectField label={t.currency} value={form.currency_code} onChange={(v) => change("currency_code", v)} options={(data.currencies || []).map((c: Row) => ({ id: c.code, name: `${c.code} · ${c.name}` }))} />
    <SelectField label={t.product} value={form.product_id} onChange={(v) => change("product_id", v)} options={(data.products || []).filter((p: Row) => p.is_active)} />
    <SelectField label={t.warehouse} value={form.warehouse_id} onChange={(v) => change("warehouse_id", v)} options={data.warehouses || []} />
    <TextField label={t.quantity} type="number" step="0.0001" min="0.0001" value={form.quantity} onChange={(v) => change("quantity", v)} />
    <TextField label={t.price} type="number" step="0.0001" min="0" value={form.unit_price} onChange={(v) => change("unit_price", v)} />
    <TextField label={t.tax} type="number" step="0.0001" min="0" value={form.tax_amount} onChange={(v) => change("tax_amount", v)} />
  </FormPanel>;
}

function PurchaseForm({ data, company, t, onCancel, onSave }: { data: Row; company?: Company; t: typeof copy.en | typeof copy.ar; onCancel: () => void; onSave: (body: Row) => Promise<void> }) {
  const [form, setForm] = useState({ supplier_id: "", product_id: "", warehouse_id: "", bill_number: `BILL-${Date.now().toString().slice(-6)}`,
    bill_date: new Date().toISOString().slice(0, 10), currency_code: company?.functional_currency_code || "USD", quantity: "1", unit_cost: "0" });
  const [busy, setBusy] = useState(false); const change = (key: string, value: string) => setForm((current) => ({ ...current, [key]: value }));
  async function submit(event: FormEvent) { event.preventDefault(); setBusy(true); try { await onSave({ supplier_id: Number(form.supplier_id), bill_number: form.bill_number, bill_date: form.bill_date, currency_code: form.currency_code, lines: [{ product_id: Number(form.product_id), warehouse_id: Number(form.warehouse_id), quantity: form.quantity, unit_cost: form.unit_cost }] }); } finally { setBusy(false); } }
  return <FormPanel title={t.newBill} onClose={onCancel} onSubmit={submit} busy={busy} t={t}>
    <SelectField label={t.supplier} value={form.supplier_id} onChange={(v) => change("supplier_id", v)} options={data.suppliers || []} />
    <TextField label={t.number} value={form.bill_number} onChange={(v) => change("bill_number", v)} />
    <TextField label={t.date} type="date" value={form.bill_date} onChange={(v) => change("bill_date", v)} />
    <SelectField label={t.currency} value={form.currency_code} onChange={(v) => change("currency_code", v)} options={(data.currencies || []).map((c: Row) => ({ id: c.code, name: `${c.code} · ${c.name}` }))} />
    <SelectField label={t.product} value={form.product_id} onChange={(v) => change("product_id", v)} options={(data.products || []).filter((p: Row) => p.is_active)} />
    <SelectField label={t.warehouse} value={form.warehouse_id} onChange={(v) => change("warehouse_id", v)} options={data.warehouses || []} />
    <TextField label={t.quantity} type="number" step="0.0001" min="0.0001" value={form.quantity} onChange={(v) => change("quantity", v)} />
    <TextField label={t.cost} type="number" step="0.0001" min="0" value={form.unit_cost} onChange={(v) => change("unit_cost", v)} />
  </FormPanel>;
}

function Inventory({ data, company, t, mutate }: { data: Row; company?: Company; t: typeof copy.en | typeof copy.ar; mutate: (path: string, body: unknown) => Promise<void> }) {
  const [show, setShow] = useState(false); const [form, setForm] = useState({ product_id: "", warehouse_id: "", movement_date: new Date().toISOString().slice(0, 10), movement_type: "RECEIPT", quantity: "1", unit_cost: "0", reference: "" });
  const balances = data.balances || []; const change = (key: string, value: string) => setForm((old) => ({ ...old, [key]: value }));
  async function submit(event: FormEvent) { event.preventDefault(); await mutate("/inventory/movements", { ...form, product_id: Number(form.product_id), warehouse_id: Number(form.warehouse_id) }); setShow(false); }
  return <div className="module-stack"><div className="module-toolbar"><div><h2>{t.inventory}</h2><p>On-hand quantities by product and warehouse</p></div><button className="primary-button" onClick={() => setShow(!show)}><Plus size={16} />{t.newMovement}</button></div>
    {show && <FormPanel title={t.newMovement} onClose={() => setShow(false)} onSubmit={submit} t={t}>
      <SelectField label={t.product} value={form.product_id} onChange={(v) => change("product_id", v)} options={data.products || []} />
      <SelectField label={t.warehouse} value={form.warehouse_id} onChange={(v) => change("warehouse_id", v)} options={data.warehouses || []} />
      <SelectField label={t.type} value={form.movement_type} onChange={(v) => change("movement_type", v)} options={[{ id: "RECEIPT", name: "Receipt" }, { id: "ISSUE", name: "Issue" }, { id: "ADJUSTMENT_IN", name: "Adjustment in" }, { id: "ADJUSTMENT_OUT", name: "Adjustment out" }]} />
      <TextField label={t.date} type="date" value={form.movement_date} onChange={(v) => change("movement_date", v)} />
      <TextField label={t.quantity} type="number" step="0.0001" min="0.0001" value={form.quantity} onChange={(v) => change("quantity", v)} />
      <TextField label={t.cost} type="number" step="0.0001" min="0" value={form.unit_cost} onChange={(v) => change("unit_cost", v)} />
      <TextField label={t.description} value={form.reference} onChange={(v) => change("reference", v)} />
    </FormPanel>}
    <section className="panel table-panel"><TableHead columns={[t.sku, t.product, t.warehouse, t.quantity, t.inventoryValue]} />
      {balances.length ? balances.map((row: Row) => <div className="table-row" key={`${row.product_id}-${row.warehouse_id}`}><b>{row.sku}</b><span>{data.products?.find((p: Row) => p.id === row.product_id)?.name || row.product_id}</span><span>{row.warehouse}</span><strong>{Number(row.quantity).toLocaleString()}</strong><span>{formatMoney(row.inventory_value_functional, company?.functional_currency_code || "USD")}</span></div>) : <EmptyRow text={t.noData} />}</section></div>;
}

function Finance({ data, company, t, mutate }: { data: Row; company?: Company; t: typeof copy.en | typeof copy.ar; mutate: (path: string, body: unknown) => Promise<void> }) {
  const [show, setShow] = useState(false); const [form, setForm] = useState({ expense_date: new Date().toISOString().slice(0, 10), category: "", description: "", currency_code: company?.functional_currency_code || "USD", amount: "", expense_account_code: "6000", payment_account_code: "1000" });
  const expenses = data.expenses || []; const trial = data.trial || { accounts: [] }; const change = (key: string, value: string) => setForm((old) => ({ ...old, [key]: value }));
  async function submit(event: FormEvent) { event.preventDefault(); await mutate("/expenses", form); setShow(false); }
  return <div className="module-stack"><div className="module-toolbar"><div><h2>{t.finance}</h2><p>Posted ledger and recorded expenses · {company?.functional_currency_code}</p></div><button className="primary-button" onClick={() => setShow(!show)}><Plus size={16} />{t.newExpense}</button></div>
    {show && <FormPanel title={t.newExpense} onClose={() => setShow(false)} onSubmit={submit} t={t}>
      <TextField label={t.date} type="date" value={form.expense_date} onChange={(v) => change("expense_date", v)} />
      <TextField label={t.category} value={form.category} onChange={(v) => change("category", v)} required />
      <TextField label={t.description} value={form.description} onChange={(v) => change("description", v)} required />
      <SelectField label={t.currency} value={form.currency_code} onChange={(v) => change("currency_code", v)} options={(data.currencies || []).map((c: Row) => ({ id: c.code, name: `${c.code} · ${c.name}` }))} />
      <TextField label={t.amount} type="number" step="0.0001" min="0.0001" value={form.amount} onChange={(v) => change("amount", v)} required />
    </FormPanel>}
    <section className="panel table-panel"><div className="panel-heading compact"><div><h2>{t.accounts}</h2><p>Posted journals in functional currency</p></div></div>
      <TableHead columns={[t.code, t.name, t.type, t.debit, t.credit]} />
      {trial.accounts?.length ? trial.accounts.map((row: Row) => <div className="table-row five" key={row.account_code}><b>{row.account_code}</b><span>{row.account_name}</span><span>{row.account_type}</span><span>{formatMoney(row.debit_functional, company?.functional_currency_code || "USD")}</span><span>{formatMoney(row.credit_functional, company?.functional_currency_code || "USD")}</span></div>) : <EmptyRow text={t.noData} />}
    </section>
    <section className="panel table-panel"><div className="panel-heading compact"><div><h2>{t.expenses}</h2><p>Record first, then post to the ledger</p></div></div><TableHead columns={[t.date, t.category, t.description, t.amount, t.status]} />
      {expenses.length ? expenses.map((row: Row) => <div className="table-row" key={row.id}><span>{row.expense_date}</span><b>{row.category}</b><span>{row.description}</span><span>{formatMoney(row.amount, row.currency_code)}</span><span className={`status-pill ${row.status.toLowerCase()}`}>{row.status}</span>{row.status === "RECORDED" && <button className="row-action" onClick={() => void mutate(`/expenses/${row.id}/post`, {})}>{t.post}</button>}</div>) : <EmptyRow text={t.noData} />}</section>
  </div>;
}

function MasterData({ data, t, mutate }: { data: Row; t: typeof copy.en | typeof copy.ar; mutate: (path: string, body: unknown) => Promise<void> }) {
  const [mode, setMode] = useState<"customer" | "supplier" | "product" | "warehouse">("customer");
  const [form, setForm] = useState({ code: "", name: "", email: "", phone: "", sku: "", category: "", unit_cost: "0", selling_price: "0" });
  const change = (key: string, value: string) => setForm((old) => ({ ...old, [key]: value }));
  const path = mode === "customer" ? "/customers" : mode === "supplier" ? "/suppliers" : mode === "product" ? "/products" : "/warehouses";
  async function submit(event: FormEvent) { event.preventDefault(); const body = mode === "product" ? { sku: form.sku, name: form.name, category: form.category || null, unit_cost: form.unit_cost, selling_price: form.selling_price } : mode === "warehouse" ? { code: form.code, name: form.name } : { code: form.code, name: form.name, email: form.email || null, phone: form.phone || null }; await mutate(path, body); setForm({ code: "", name: "", email: "", phone: "", sku: "", category: "", unit_cost: "0", selling_price: "0" }); }
  const values = mode === "customer" ? data.customers : mode === "supplier" ? data.suppliers : mode === "product" ? data.products : data.warehouses;
  return <div className="module-stack"><div className="module-toolbar"><div><h2>{t.masterdata}</h2><p>Shared company records used by sales, purchasing, and inventory</p></div></div>
    <section className="panel form-panel"><div className="panel-heading compact"><div><h2>{t.create} {mode}</h2><p>New records are isolated to the selected company</p></div></div>
      <div className="segmented">{(["customer", "supplier", "product", "warehouse"] as const).map((item) => <button key={item} className={mode === item ? "selected" : ""} onClick={() => setMode(item)}>{item}</button>)}</div>
      <form onSubmit={submit} className="form-grid">
        {mode === "product" ? <><TextField label={t.sku} value={form.sku} onChange={(v) => change("sku", v)} required /><TextField label={t.name} value={form.name} onChange={(v) => change("name", v)} required /><TextField label={t.category} value={form.category} onChange={(v) => change("category", v)} /><TextField label={t.cost} type="number" value={form.unit_cost} onChange={(v) => change("unit_cost", v)} /><TextField label={t.price} type="number" value={form.selling_price} onChange={(v) => change("selling_price", v)} /></>
          : <><TextField label={t.code} value={form.code} onChange={(v) => change("code", v)} required /><TextField label={t.name} value={form.name} onChange={(v) => change("name", v)} required />{(mode === "customer" || mode === "supplier") && <><TextField label={t.email} type="email" value={form.email} onChange={(v) => change("email", v)} /><TextField label="Phone" value={form.phone} onChange={(v) => change("phone", v)} /></>}</>}
        <div className="form-actions"><button className="primary-button"><Plus size={15} />{t.create}</button></div>
      </form>
    </section>
    <section className="panel table-panel"><TableHead columns={mode === "product" ? [t.sku, t.name, t.category, t.cost, t.price] : [t.code, t.name, ...(mode === "warehouse" ? [] : [t.email])]} />
      {values?.length ? values.map((row: Row) => <div className="table-row" key={row.id}><b>{row.code || row.sku}</b><span>{row.name}</span>{mode === "product" ? <><span>{row.category || "—"}</span><span>{row.unit_cost}</span><span>{row.selling_price}</span></> : mode !== "warehouse" && <span>{row.email || "—"}</span>}</div>) : <EmptyRow text={t.noData} />}</section>
  </div>;
}

function FormPanel({ title, onClose, onSubmit, busy, t, children }: { title: string; onClose: () => void; onSubmit: (event: FormEvent) => void; busy?: boolean; t: typeof copy.en | typeof copy.ar; children: ReactNode }) {
  return <form className="panel form-panel" onSubmit={onSubmit}><div className="panel-heading compact"><div><h2>{title}</h2><p>Save a draft to review before posting</p></div><button className="icon-button" type="button" onClick={onClose} aria-label={t.close}><X size={16} /></button></div>
    <div className="form-grid">{children}<div className="form-actions"><button type="button" className="secondary-button" onClick={onClose}>{t.close}</button><button className="primary-button" disabled={busy}><Check size={15} />{busy ? t.loading : t.save}</button></div></div></form>;
}

function TextField({ label, value, onChange, type = "text", step, min, required }: { label: string; value: string; onChange: (value: string) => void; type?: string; step?: string; min?: string; required?: boolean }) {
  return <label className="form-field"><span>{label}</span><input type={type} value={value} onChange={(event) => onChange(event.target.value)} step={step} min={min} required={required} /></label>;
}

function SelectField({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: Row[] }) {
  return <label className="form-field"><span>{label}</span><select value={value} onChange={(event) => onChange(event.target.value)} required>
    <option value="">Select…</option>{options.map((option) => <option key={option.id ?? option.code} value={option.id ?? option.code}>{option.name}</option>)}
  </select></label>;
}

function TableHead({ columns }: { columns: string[] }) {
  return <div className={`table-head ${columns.length === 5 ? "five" : ""}`}><span>{columns[0]}</span>{columns.slice(1).map((item) => <span key={item}>{item}</span>)}</div>;
}

function EmptyRow({ text }: { text: string }) {
  return <div className="empty-row"><Search size={17} /><span>{text}</span></div>;
}

export default App;
