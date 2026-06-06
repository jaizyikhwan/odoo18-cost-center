# Panduan Penggunaan

Dokumen ini memandu workflow end-to-end modul Cost Center & Budget
Control.

## 1. Setup Awal

Setelah install modul, buka **Settings → Cost Center & Budget Control**
untuk konfigurasi threshold:

| Setting | Default | Fungsi |
|---|---|---|
| Enable Budget Control | `True` | Master switch |
| Control Mode | `warning_only` | `blocking` atau `warning_only` |
| Warning Threshold | `70%` | Warning di-post ke chatter |
| Critical Threshold | `90%` | Mail template di-queue ke manager |
| Blocking Threshold | `100%` | Posting dihentikan |
| Block Purchase Orders | `False` | Kalau `True` + `mode=blocking`, konfirmasi RFQ juga di-block |
| Chatter Notifications | `True` | Log warning ke chatter dokumen |
| Activity Notifications | `False` | Schedule activity alert |

## 2. Lifecycle Cost Center

1. Buka **Cost Center & Budget Control → Cost Centers → Create**
2. Isi:
   - **Name** (wajib)
   - **Code** (wajib, unik per company)
   - **Parent Cost Center** (opsional, untuk hierarki)
   - **Company** (wajib, default current)
   - **Manager** (user penanggung jawab)

   - **Analytic Account** (auto-created kalau tidak diisi)
3. Save dan archive kalau sudah tidak dipakai (active flag, bukan
   delete)

### Hierarki

Relasi parent-child disimpan pakai mekanisme `_parent_store` Odoo
untuk tree traversal yang efisien. Field `parent_path` menyediakan
materialized path query untuk lookup ancestor yang cepat.

## 3. Workflow Budget Plan

State machine: `Draft → Submitted → Approved → Revised / Closed / Cancelled`

| From | To | Action | Oleh |
|---|---|---|---|
| Draft | Submitted | **Submit** | Budget User |
| Submitted | Draft | **Reject** | Budget Manager |
| Submitted | Approved | **Approve** | Budget Manager |
| Approved | Revised | **(auto via Revise)** | System (clone ke approved baru) |
| Revised | (terminal) | (tidak ada) | — |
| Approved | Closed | **Close** | Budget Manager |
| * | Cancelled | **Cancel** | Budget Manager |

### Langkah

1. **Create** budget plan di state `Draft`
2. Tambah **budget lines**: tiap line pasangkan `account.account` dengan
   `planned_amount` dan (opsional) date range
3. **Submit** kalau sudah siap untuk review
4. **Approve** untuk lock plan dari modifikasi
5. Begitu accounting moves ter-post dengan analytic account yang match,
   field `actual_amount`, `po_committed_amount`, `committed_amount`,
   `available_amount`, `variance_amount`, `usage_percent`, dan
   `alert_level` otomatis terhitung
6. **Revise** kalau budget perlu diubah di tengah periode (lihat §3a)
7. **Close** plan di akhir periode

### 3a. Workflow Budget Revision

Kalau approved budget perlu adjustment di tengah periode (perubahan
scope, reforecast, grant baru, dll.):

1. Buka approved budget plan
2. Klik **Revise** di header form
3. Sistem akan:
   - Tandai original sebagai `Revised` (immutable — tidak bisa diedit)
   - Clone seluruh plan (header + lines) sebagai record baru
   - Set nama plan baru jadi `<nama original> (Rev N)` (N auto-increment)
   - Link plan baru ke original lewat `parent_revision_id`
   - Set state plan baru ke `Approved` (revision sendiri langsung aktif;
     revision adalah budget baru, bukan re-approval)
   - Post pesan chatter di plan original yang mengumumkan revision
4. Edit lines plan baru sesuai kebutuhan
5. Posted move selanjutnya agregasi ke plan **baru** (karena yang lama
   `revised` dan di-exclude dari `_recompute_actual_amount_batch`)

**Penting**: revision tidak destruktif. Plan `revised` original tetap
ada sebagai audit history dengan snapshot `actual_amount` yang frozen.
Kamu bisa lihat seluruh chain di list view dengan group by "Parent
Revision".

**Catatan reversal**: revision tidak bisa di-revert lewat UI action.
Kalau salah bikin revision, pattern yang direkomendasikan adalah revise
lagi (chain) atau close manual lewat ORM langsung (dengan permission
yang sesuai dan audit logging).

## 4. Budget Threshold Control

Waktu journal entry di-post dan punya analytic account yang ter-link
ke cost center dengan budget plan aktif:

- **< 70%**: posting jalan tanpa notifikasi
- **70% – 90%**: posting jalan, warning di-log ke chatter (kalau enable)
- **90% – 100%**: posting jalan, mail template di-queue ke manager
- **> 100%** di mode `blocking`: posting gagal dengan `UserError` yang
  listing impacted budget plan. Override Manager bisa authorize
  override lewat group membership (bukan lewat context flag)

`committed_amount` juga dicek:

- `committed_amount = actual_amount + po_committed_amount`
- `available_amount = planned_amount - committed_amount`
- Kalau `available_amount < 0`, budget **over-committed** (baris jadi
  merah di list view, PDF report tampilkan nilai negatif merah)

## 5. Integrasi Purchase Order

Waktu Purchase Order di-confirm (status pindah dari `draft` ke
`purchase`), lines-nya diagregasi ke budget line yang match sebagai
`po_committed_amount`. Waktu vendor bill di-post, `actual_amount`
naik dan `po_committed_amount` turun (karena sudah tidak unbilled).

### Opt-in Hard Block

Default-nya, konfirmasi PO yang akan exceed blocking threshold budget
**sukses tanpa notifikasi** (overage terlihat di report tapi tidak
block procurement). Untuk enable hard blocking:

1. Buka **Settings → Cost Center & Budget Control**
2. Set **Block Purchase Orders** ke `True`
3. Set **Control Mode** ke `blocking` (hard block butuh blocking mode)
4. Sekarang `button_confirm()` di PO yang akan dorong budget lewat
   threshold akan raise `UserError` yang listing affected budget plan
5. Block ke-bypass untuk user di security group
   `group_budget_override_manager` (dengan chatter audit log)

### Event yang Di-Hook

Integrasi PO auto-recompute impacted budget line pada:

| Event | Scope Recompute |
|---|---|
| `button_confirm` | Semua PO lines (baru confirmed) |
| `button_cancel` | Semua PO lines (jadi un-confirmed) |
| `action_rfq_send` (dikirim untuk approval) | Tidak ada recompute (RFQ masih draft) |
| `write` (tracked field apapun) | Hanya line yang berubah (delta) |
| `unlink` | Semua PO lines (cascading recompute) |

## 6. Overhead Allocation

Alokasi shared overhead cost dari satu source cost center ke beberapa
target cost center berdasarkan persentase:

1. Buka **Budget Allocations → Create**
2. Set **Source Cost Center** (overhead pool)
3. Tambah **Allocation Lines**: tiap line pasangkan target cost center
   dengan persentase. Total HARUS 100%.
4. Set **Period** (date range)
5. Klik **Allocate** — sistem akan:
   - Validasi persentase total 100%
   - Hitung debit proporsional
   - Serap rounding residual di line terakhir
   - Generate `account.move` yang balanced dengan analytic distribution
   - Assign idempotency reference yang deterministik
6. Pakai **Reverse** kalau allocation perlu di-undo (generate reversal
   entry)

## 7. Reporting

- **Budget Analysis** (pivot) — `actual` vs `planned` vs `committed` vs
  `available` per cost center × account
- **Budget Graphs** (bar/line) — trend penggunaan
- **Allocation Analysis** (pivot) — histori distribusi overhead
- **Budget Variance Report** (QWeb PDF) — laporan variance lengkap
  dengan kolom planned/actual/PO-committed/committed/available, status
  indicator, dan revision chain indicator
- **List view filter** — "Over-Budget", "Warning", "Critical",
  "Exceeded", "Over-Committed", "Has Committed POs", "Revised",
  "Latest Revision Only", "Has Revisions"

## 8. Demo Data

Modul ini bundled dengan demo data yang mengaktifkan budget control,
bikin sample cost center, budget plan, dan skenario over-budget.
Install dengan demo data enable untuk langsung lihat modul in
action.

## 9. Skenario Multi-Company

Modul ini support multi-company dengan isolasi ketat di level ORM dan
record rule. Contoh skenario: holding company dengan HQ + 2 anak
perusahaan.

### 9.1 Setup Awal Multi-Company

1. **Aktifkan multi-company** di Settings → Users → Administration:
   - Set "Multi-Company" allowed companies untuk user yang relevan
2. **Buat companies** di Settings → Companies:
   - `Demo Holding (HQ)` — currency IDR
   - `Demo Subsidiary A` — currency IDR
   - `Demo Subsidiary B` — currency USD
3. **Setup Cost Centers per company**:
   - Login sebagai user dengan akses ke Demo Holding
   - Buat cost center: `HQ-Finance`, `HQ-HR` (`parent_id` kosong,
     company = Demo Holding)
   - Switch company ke Demo Subsidiary A
   - Buat cost center: `SUB-A-Operations`, `SUB-A-Sales` (company =
     Demo Subsidiary A)
4. **Verifikasi isolasi**:
   - Buka Cost Centers sebagai user di Demo Holding
   - Filter by Company: hanya cost center Demo Holding yang visible
   - Cost center Demo Subsidiary A TIDAK terlihat

### 9.2 Cross-Company Block (Negative Test)

Coba test isolasi dengan attempt berbahaya:

1. Login sebagai user di Demo Holding
2. Buka form cost center Demo Holding
3. Coba ubah field Company ke Demo Subsidiary A
4. **Expected error**: ORM `check_company=True` reject — `Company
   incompatible with cost center's analytic account`
5. Hal yang sama berlaku untuk budget plan, allocation, dan journal
   entry

### 9.3 Consolidated Reporting Across Companies

Untuk CFO yang butuh view cross-company:

1. Login sebagai user dengan akses ke SEMUA companies
2. Buka **Reporting → Budget Analysis**
3. Search bar → Group By: **Company**
4. **Observasi**: Pivot menampilkan cost center + budget data per
   company
5. **Catatan**: Multi-currency conversion terjadi otomatis di background
   (planned/actual disimpan dalam currency plan, bukan company
   currency)

### 9.4 Record Rules (Referensi Teknis)

Modul ini enforce 4 record rule (`security/ir_rule.xml`):

| Rule | Model | Domain |
|---|---|---|
| `budget_plan_comp_rule` | `budget.plan` | `[('company_id', 'in', company_ids)]` |
| `budget_plan_line_comp_rule` | `budget.plan.line` | sama |
| `cost_center_comp_rule` | `cost.center` | sama |
| `budget_allocation_comp_rule` | `budget.allocation` | sama |

User hanya bisa lihat record di company yang ada di
`user.company_ids`. Tidak ada escape — `sudo()` dibutuhkan untuk
bypass (dan di-audit di chatter).
