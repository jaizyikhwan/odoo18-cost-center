# Cost Center & Budget Control

[![Tests](https://github.com/jaizyikhwan/odoo18-cost-center/actions/workflows/test.yml/badge.svg)](https://github.com/jaizyikhwan/odoo18-cost-center/actions/workflows/test.yml)
[![Odoo 18 CE](https://img.shields.io/badge/Odoo-18.0-714B67.svg)](https://www.odoo.com/documentation/18.0/)
[![License: LGPL-3](https://img.shields.io/badge/License-LGPL--3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Version](https://img.shields.io/badge/version-18.0.2.2.0-green.svg)](CHANGELOG.md)

Modul untuk **Odoo 18 Community Edition** yang membantu Anda mengontrol anggaran per cost center. Transaksi yang melebihi limit langsung ditolak saat posting, bukan cuma peringatan. Komitmen dari PO yang masih terbuka ikut terhitung, jadi saldo anggaran selalu realistis dan tidak over-commit.

---

## Quick Start

```bash
git clone https://github.com/jaizyikhwan/odoo18-cost-center.git
cd odoo-cost-center
docker compose up -d
```

Buka `http://localhost:8018`, install **Cost Center & Budget Control** dari Apps menu. Demo data sudah include di module, jadi bisa langsung coba.

---

## Fitur

- **Hard-block di posting**. Transaksi yang akan lewat budget ditolak saat konfirmasi, bukan sekadar muncul di laporan. Manager bisa override lewat group dengan audit trail di chatter.
- **PO Committed tracking**. PO yang sudah confirmed tapi belum ditagih tetap dihitung sebagai komitmen, jadi angka budget yang tersedia selalu real-time.
- **Hierarki cost center**. Cost center bisa disusun parent-child (misal divisi → departemen → tim), dengan analytic account otomatis ter-link.
- **Distribusi overhead**. Alokasi biaya antar cost center lewat journal entry yang balance (debit = kredit), dengan SHA1 ref supaya tidak dobel kalau diulang.
- **Budget revision**. Revisi budget membuat clone baru yang editable, versi lama otomatis di-lock jadi history yang tidak bisa diedit.

---

## Alur Penggunaan

Dua diagram ini merangkum workflow end-to-end: dari setup awal sampai
penutupan periode, dan state machine budget plan-nya.

### End-to-End Flow

```mermaid
graph LR
    A[Install Module] --> B[Setup Cost Centers<br/>parent-child + analytic]
    B --> C[Buat Budget Plan<br/>Draft + budget lines]
    C --> D[Submit]
    D --> E{Manager Review}
    E -->|Reject| C
    E -->|Approve| F[Plan Active]
    F --> G[Post Journal Entry<br/>dengan analytic account]
    G --> H{Budget Check}
    H -->|OK / Warning| I[Posted]
    H -->|> 100% blocking| J{Override?}
    J -->|Group Override Manager| I
    J -->|Tidak| K[Posting ditolak]
    I --> L{Akhir periode}
    L -->|Perlu revisi| M[Revise<br/>clone + lock original]
    L -->|Tutup periode| N[Close]
    M --> G
    N --> O([Selesai])
```

### Budget Plan State Machine

```mermaid
stateDiagram-v2
    [*] --> Draft
    Draft --> Submitted: Submit (User)
    Submitted --> Draft: Reject (Manager)
    Submitted --> Approved: Approve (Manager)
    Submitted --> Cancelled: Cancel (Manager)
    Draft --> Cancelled: Cancel (Manager)
    Approved --> Revised: Revise (auto: clone)
    Approved --> Closed: Close (Manager)
    Approved --> Cancelled: Cancel (Manager)
    Revised --> [*]
    Closed --> [*]
    Cancelled --> [*]
```

---

## Instalasi

### Prasyarat

- Docker + Docker Compose
- Git

### Langkah

```bash
git clone https://github.com/jaizyikhwan/odoo18-cost-center.git
cd odoo-cost-center
docker compose up -d
docker compose logs -f odoo
```

Tunggu sampai Odoo siap di `http://localhost:8018`. Login sebagai admin, lalu ke **Apps**, cari **Cost Center & Budget Control**, klik **Install**.

Volume `addons/` ter-mount, jadi perubahan lokal langsung ter-reflect.

### Dependencies

`base`, `account`, `analytic`, `mail`, `purchase` (semua bawaan Odoo 18 CE).

---

## Struktur Repository

```
odoo-cost-center/
├── addons/
│   └── cost_center_budget_control/
│       ├── __manifest__.py
│       ├── models/                # cost_center, budget_plan, allocation, account_move, ...
│       ├── security/              # groups, ACL, multi-company rules
│       ├── views/                 # form, tree, pivot, graph, search
│       ├── wizard/                # approval wizard, variance export
│       ├── report/                # QWeb PDF variance report
│       ├── data/                  # mail template, ir.cron
│       ├── demo/                  # sample data
│       ├── static/img/            # screenshots
│       └── tests/                 # 51 tests (test_performance, test_multi_company, ...)
├── docker-compose.yml
└── .env
```

---

## Screenshots

**Daftar cost center** (hierarkis, dikelompokkan berdasarkan parent).

![Cost Centers](addons/cost_center_budget_control/static/img/01_cost_center_form.png)

**Form cost center** dengan link ke analytic account dan responsible user.

![Cost Center Form](addons/cost_center_budget_control/static/img/02_cost_center_form.png)

**Form budget plan** Approved, dengan progress bar penggunaan dan highlight baris over-budget.

![Budget Plan Form](addons/cost_center_budget_control/static/img/03_budget_plan_form.png)

**Form allocation** dengan source cost center, persentase target, dan SHA1 idempotency ref.

![Allocation Form](addons/cost_center_budget_control/static/img/04_allocation_form.png)

**Variance report** (QWeb PDF, planned vs actual per cost center).

![Variance Report](addons/cost_center_budget_control/static/img/05_variance_report.png)

---

## Lisensi

LGPL-3.0.

Pengembang: [Muhammad Ikhwan Jaizy](https://github.com/jaizyikhwan)
