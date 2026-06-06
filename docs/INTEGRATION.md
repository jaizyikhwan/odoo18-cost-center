# Panduan Integrasi

> **Audiens**: System administrator, Odoo integrator, dan developer
> yang perlu deploy modul ini bareng modul budget/accounting lain.
>
> **Terakhir diperbarui**: 2026-06-04

Dokumen ini menjelaskan bagaimana modul ini coexist dengan modul
budget lain di ekosistem Odoo, dan menyediakan migration path dari
vanilla Odoo atau OCA `account_budget_oca`.

---

## 1. Matriks Referensi Cepat

| Skenario | Status | Rekomendasi |
|---|---|---|
| **Vanilla Odoo 18 CE** (tanpa modul budget) | Cocok | Install modul ini — semua yang vanilla kurang tersedia di sini |
| **OCA `account_budget_oca` (v18.0)** | Cocok | Install dua-duanya. Pakai `account_budget_oca` untuk **multi-company crossovered budgets**, pakai modul ini untuk **per-cost-center enforcement** |
| **OCA `account_budget_oca` + modul ini** | Paling ideal | Rekomendasi untuk organisasi dengan kebutuhan multi-company budget yang kompleks |
| **Native Odoo Enterprise `account.budget`** | Tidak bisa dipakai bersamaan | Modul Enterprise auto-disable kalau tidak berlisensi; modul ini adalah alternatif untuk CE |
| **Dua-duanya: Enterprise `account.budget` DAN modul ini** | Konflik | Catatan OCA: "incompatible". Disable salah satu |

---

## 2. Coexistence dengan OCA `account_budget_oca`

OCA `account_budget_oca` adalah modul yang cukup baik dan di-maintain
oleh Odoo S.A. Fitur yang disediakan:

- `crossovered.budget` (definisi analytic budget)
- `crossovered.budget.lines` (planned/actual/practical amount)
- 3 QWeb report bawaan
- Multi-company support

Modul ini menyediakan fitur **komplementer**:

- Per-cost-center enforcement (bukan per-analytic)
- Hard-block di posting
- PO committed tracking
- Allocation engine
- Revision chain

### 2.1 Urutan Instalasi

**Tidak ada urutan khusus.** Dua modul bisa di-install independen:

```bash
# Dua-dua urutan jalan
odoo-bin -d mydb -i account_budget_oca,cost_center_budget_control
# atau
odoo-bin -d mydb -i cost_center_budget_control,account_budget_oca
```

Setelah instalasi, dua set modul aktif bersamaan tanpa konflik.

### 2.2 Coexistence Data Model

| Konsep | `account_budget_oca` | Modul Ini |
|---|---|---|
| Definisi budget | `crossovered.budget` | `budget.plan` |
| Baris budget | `crossovered.budget.lines` | `budget.plan.line` |
| Unit org | `account.analytic.account` | `cost.center` (linked ke analytic account) |
| Actual amount | `practical_amount` (compute via `_compute_practical_amount`) | `actual_amount` (compute via SQL JSONB) |
| Committed amount | (tidak ada di versi CE) | `po_committed_amount`, `committed_amount` |

**Catatan**: dua `actual` amount dihitung dengan cara berbeda tapi
seharusnya match (dalam toleransi) untuk analytic account + periode yang
sama. `account_budget_oca` pakai ORM search; modul ini pakai SQL JSONB
dengan GIN index. Untuk dataset besar, compute di modul ini lebih
cepat.

### 2.3 Opsional: Sync Budget Plan ↔ Crossovered Budget

Kalau mau data mengalir dari `budget.plan` (modul ini) ke
`crossovered.budget` (OCA), bisa tambah sync hook di modul custom.
Contoh:

```python
# Di modul custom kamu: models/budget_plan_sync.py
from odoo import models, api


class BudgetPlanSync(models.Model):
    _inherit = "budget.plan"

    crossovered_budget_id = fields.Many2one(
        "crossovered.budget",
        help="Opsional link ke OCA crossovered.budget untuk cross-reporting",
    )

    @api.model_create_multi
    def create(self, vals_list):
        plans = super().create(vals_list)
        for plan, vals in zip(plans, vals_list):
            if self.env.context.get("sync_to_oca_budget"):
                # Bikin crossovered.budget yang corresponding
                cb = self.env["crossovered.budget"].create({
                    "name": plan.name,
                    "date_from": plan.date_from,
                    "date_to": plan.date_to,
                    # ... field lain
                })
                plan.crossovered_budget_id = cb
        return plans
```

**Opsional** dan **tidak enable by default**. Kebanyakan user merasa
reporting dari dua modul sudah cukup sendiri-sendiri.

---

## 3. Coexistence dengan Odoo Enterprise `account.budget`

**Catatan dokumentasi OCA**: *"Modul ini incompatible dengan modul
Enterprise `account_budget` Odoo"*.

Karena dua modul sama-sama:

- Pakai XML ID `account.budget`
- Override `account.move._post` untuk tambah budget check
- Definisikan model `crossovered.budget` (atau mirip)

**Implikasi praktis**: tidak bisa punya Enterprise `account.budget` DAN
modul ini aktif bersamaan.

### 3.1 Pilih yang Mana?

| Pilih Enterprise `account.budget` kalau: | Pilih Modul Ini kalau: |
|---|---|
| Sudah punya lisensi Odoo Enterprise | Pakai Odoo Community |
| Butuh kontrak support resmi Odoo | Nyaman dengan support community/OCA |
| Butuh fitur Enterprise lain (helpdesk, mobile, dll.) | Cuma butuh budget enforcement |
| Butuh automated budget vs actual report di pivot | Butuh **enforcement + allocation + revision** |
| Partner Odoo kamu insist Enterprise | Mau LGPL-3 source-available |

**Pertimbangan biaya**: Enterprise sekitar $20-25/user/bulan. Untuk
organisasi 50 user, itu $12.000-15.000/tahun untuk satu modul budget.

Modul ini: **gratis**, LGPL-3, source-available, OCA-style.

### 3.2 Kalau Sekarang Sedang di Enterprise

Untuk migrasi dari Enterprise `account.budget` ke modul ini:

1. **Disable** modul Enterprise `account.budget`
2. **Install** modul ini + OCA `account_budget_oca` (opsional)
3. **Migrasi data** (lihat Section 5 di bawah)
4. **Validasi** bahwa report sesuai ekspektasi

---

## 4. Coexistence dengan OCA `account_budget_oca_usability`

OCA punya modul lain `account_budget_oca_usability` (oleh AvanzOSC)
yang nambah pivot view untuk budget line. Statusnya:

- **Cocok** dengan `account_budget_oca`
- **Cocok** dengan modul ini (model berbeda, tidak overlap)
- Nambah: pivot view, sub-menu "Budget Lines"

Ketiganya bisa di-install bersamaan tanpa masalah.

---

## 5. Migration Path dari Vanilla Odoo 18

Kalau saat ini pakai `account.budget` vanilla Odoo 18 dan mau migrasi
ke modul ini:

### 5.1 Audit Pra-Migrasi

```sql
-- Run di psql untuk audit data budget yang ada
SELECT
    b.name,
    b.date_from,
    b.date_to,
    COUNT(bl.id) AS line_count,
    SUM(bl.planned_amount) AS total_planned
FROM account_budget b
LEFT JOIN account_budget_line bl ON bl.budget_id = b.id
WHERE b.state != 'cancelled'
GROUP BY b.id
ORDER BY b.date_from DESC;
```

Query ini kasih baseline apa yang perlu dimigrasi.

### 5.2 Script Migrasi (Proses Manual)

Untuk tiap `account.budget` yang ada di vanilla:

1. Identifikasi analytic account di `account.budget.line`
2. Cari atau bikin `cost.center` dengan `analytic_account_id` yang match
3. Bikin `budget.plan` baru untuk periodenya
4. Bikin `budget.plan.line` untuk tiap `account.budget.line`:
   - `account_id` ← `account.budget.line.account_id`
   - `planned_amount` ← `account.budget.line.planned_amount`
   - `name` ← deskripsi
5. (Opsional) Link lewat field custom untuk referensi historis

### 5.3 Contoh Kode Migrasi (Odoo Shell)

```python
# Di Odoo shell (odoo-bin shell -d mydb)
env = Environment(cr, SUPERUSER_ID, {})

# Ambil semua budget vanilla
vanilla_budgets = env['account.budget'].search([('state', '!=', 'cancelled')])

for vb in vanilla_budgets:
    # Cari atau bikin cost center
    analytic = vb.analytic_account_id
    cost_center = env['cost.center'].search([
        ('analytic_account_id', '=', analytic.id)
    ], limit=1)

    if not cost_center:
        cost_center = env['cost.center'].create({
            'name': analytic.name,
            'code': analytic.code or analytic.name[:8],
            'analytic_account_id': analytic.id,
            'company_id': vb.company_id.id,
        })

    # Bikin budget plan
    plan = env['budget.plan'].create({
        'name': f"[Migrated] {vb.name}",
        'cost_center_id': cost_center.id,
        'date_from': vb.date_from,
        'date_to': vb.date_to,
        'state': 'approved',  # atau 'submitted' kalau mau re-approval
    })

    # Migrasi lines
    for vbl in vb.budget_line_ids:
        env['budget.plan.line'].create({
            'plan_id': plan.id,
            'account_id': vbl.account_id.id,
            'planned_amount': vbl.planned_amount,
            'name': vbl.name or '',
        })

    env.cr.commit()
    print(f"Migrated: {vb.name} → {plan.name}")
```

### 5.4 Validasi Pasca-Migrasi

1. Bandingkan `actual_amount` antara vanilla dan modul ini untuk periode
   yang sama — harusnya match dalam toleransi rounding
2. Bandingkan total `planned_amount` — harusnya match persis
3. Verifikasi semua record `cost.center` ter-link ke
   `account.analytic` yang valid
4. Test threshold validation dengan posting JE kecil

---

## 6. Resolusi Konflik Cross-Module

Kalau ketemu error saat install/upgrade:

### 6.1 Error "Model already exists"

Berarti ada modul lain yang definisikan model yang sama. Kandidat yang
paling mungkin:

- `account.budget` (Enterprise)
- `account_budget_oca` (OCA)

**Fix**: Uninstall modul yang konflik dulu.

### 6.2 Error "Field X already exists with different type"

Berarti ada modul lain yang definisikan field yang sama dengan tipe
berbeda. Contoh: dua modul definisikan `state` di related model
dengan selection yang berbeda.

**Fix**: Cek `__manifest__.py` semua modul yang ter-install; modul
yang konflik harus dimodifikasi (di luar scope panduan ini).

### 6.3 Konflik Demo Data

Demo data modul ini pakai ID seperti `cost_center_*`, `budget_plan_*`.
Kalau modul lain pakai external ID yang sama, demo data gagal load.

**Fix**: Pakai `noupdate="1"` di demo data, atau rename XML ID di salah
satu modul.

---

## 7. Production Deployment Checklist

Sebelum deploy modul ini ke production:

- [ ] **Backup database** sebelum install/upgrade modul apapun
- [ ] **Test di staging** dengan copy data production
- [ ] **Verifikasi multi-company** isolation jalan untuk setup kamu
- [ ] **Konfigurasi settings** (threshold, override group) sebelum
       enable di production
- [ ] **Audit user yang ada** untuk group assignment yang sesuai
- [ ] **Set `block_on_purchase = False`** dulu (opt-in saja)
- [ ] **Train tim finance** untuk workflow override
- [ ] **Set up monitoring** untuk `ir.config_parameter` terkait perubahan
       setting
- [ ] **Dokumentasikan period budget** (misal fiscal year start,
       alignment period)
- [ ] **Plan revision cycle** (kapan Revise diharapkan, oleh siapa)

---

## 8. API & Webhook Integration (Mendatang)

Modul ini saat ini pakai standar Odoo XML-RPC / JSON-RPC. Belum ada
custom REST API. Untuk integrasi dengan sistem eksternal:

| Kebutuhan | Solusi |
|---|---|
| Baca status budget dari BI tool | Pakai endpoint `/xmlrpc/2/object` Odoo dengan `execute_kw` |
| Trigger allocation dari scheduler eksternal | Bikin allocation via XML-RPC, panggil `action_allocate()` |
| Webhook saat threshold breach | Subscribe ke chatter `account.move` via bus Odoo (long-polling) |
| Bulk import budget historis | Pakai wizard `import` standar Odoo di `budget.plan` |

Untuk kebutuhan yang lebih advance, modul ini extensible lewat
`_inherit` di model manapun. Lihat
[`ARCHITECTURE.md` Section 4](ARCHITECTURE.md#4-extension-point).

---

## 9. Pertanyaan yang Sering Ditanya

### Q: Bisa pakai modul ini tanpa OCA `account_budget_oca`?

A: Bisa. Modul ini **standalone**. Tidak mensyaratkan
`account_budget_oca`. Keduanya komplementer tapi independen.

### Q: Apakah modul ini auto-bikin `crossovered.budget` waktu saya bikin
`budget.plan`?

A: Tidak. Keduanya model independen. Kalau mau sync, lihat
Section 2.3 di atas.

### Q: Saya di Odoo 17. Bisa pakai modul ini?

A: Tidak. Modul ini targetnya 18.0 secara spesifik karena:

- `analytic_distribution` JSONB (v16+, tapi ada behavior spesifik v18)
- API `_parent_store` stabil di v18
- Perubahan signature `account.move._post()`

Untuk Odoo 17, perlu branch terpisah. (Belum di-maintain saat ini.)

### Q: Apakah ini jalan dengan OCA `mis_builder`?

A: Bisa, keduanya modul independen. `mis_builder` bisa dipakai untuk
dashboard KPI advanced di atas data `budget.plan.line` lewat extension
`_compute_*`. Tidak ada konflik.

### Q: Bagaimana dengan multi-currency?

A: Didukung di modul ini. Tiap `budget.plan` bisa punya `currency_id`
sendiri (default ke company currency tapi bisa di-override). Agregasi
SQL pakai `currency_id` untuk grouping; konversi ke company currency
terjadi saat display.

### Q: Bagaimana cara disable enforcement sementara?

A: Set `cost_center_budget_control.enabled = False` lewat Settings
(checkbox) atau lewat shell:

```python
env['ir.config_parameter'].set_param(
    'cost_center_budget_control.enabled', False
)
```

Hard-block ke-bypass; warning juga ke-disable.

---

## 10. Butuh Bantuan

Kalau ketemu issue yang tidak dibahas di sini:

1. Cek [bagian troubleshooting README utama](../README.md#troubleshooting)
2. Cari di [GitHub Issues](https://github.com/jaizyikhwan/odoo18-cost-center/issues)
3. Buka issue baru dengan info:
   - Versi Odoo + commit hash
   - Steps to reproduce
   - Ekspektasi vs actual
   - Kombinasi modul yang ter-install (modul ini + yang lain)
