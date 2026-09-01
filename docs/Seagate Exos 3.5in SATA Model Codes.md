# Seagate Exos 3.5-inch SATA Model-Code Reference

**Updated:** 7 August 2026 — factory-recertified table expanded  
**Purpose:** Search exact Seagate Exos model codes when shopping for used, refurbished or recertified SATA drives.

> `ST16000NM001G` is a **model number/model code**, not a serial number. A serial number is unique to one physical drive and cannot be used as a general shopping reference.

## Scope

This reference contains **3.5-inch Seagate Exos SATA base/standard models**, arranged by capacity and approximately oldest to newest. It includes older 512n models, normal 512e/FastFormat models and a few explicitly labelled hyperscale SATA models.

It deliberately excludes:

- SAS models
- 4Kn-only models
- SED/FIPS encrypted variants
- most PowerBalance and OEM-only sub-variants
- 2.5-inch Exos drives
- SMR drives from the main buying table

Families overlapped, so the order within a capacity is an **approximate generation order**, not a precise manufacturing-date sequence.

## Quick capacity lookup

| Capacity | SATA model codes — approximately oldest → newest |
|---:|---|
| **1TB** | `ST1000NM0008` → `ST1000NM0055` → `ST1000NM000A` |
| **2TB** | `ST2000NM0008` → `ST2000NM0055` → `ST2000NM0125` → `ST2000NM000A` → `ST2000NM001A` → `ST2000NM000B` → `ST2000NM017B` |
| **3TB** | `ST3000NM0005` → `ST3000NM000A` |
| **4TB** | `ST4000NM0035` → `ST4000NM0115` → `ST4000NM000A` → `ST4000NM002A` → `ST4000NM000B` → `ST4000NM024B` |
| **6TB** | `ST6000NM0235` → `ST6000NM0115` → `ST6000NM002A` → `ST6000NM021A` → `ST6000NM000B` → `ST6000NM019B` |
| **8TB** | `ST8000NM0055` → `ST8000NM0016` → `ST8000NM0206` → `ST8000NM000A` → `ST8000NM017B` |
| **10TB** | `ST10000NM0016` → `ST10000NM0086` → `ST10000NM0478` → `ST10000NM001G` → `ST10000NM018G` → `ST10000NM017B` |
| **12TB** | `ST12000NM0007` → `ST12000NM0008` → `ST12000NM001G` → `ST12000NM000J` → `ST12000NM002H` |
| **14TB** | `ST14000NM0018` → `ST14000NM001G` → `ST14000NM000J` |
| **16TB** | `ST16000NM001G` → `ST16000NM000J` → `ST16000NM002H` |
| **18TB** | `ST18000NM000J` → `ST18000NM003D` |
| **20TB** | `ST20000NM007D` → `ST20000NM004E` → `ST20000NM002H` |
| **22TB** | `ST22000NM001E` |
| **24TB** | `ST24000NM002H` → `ST24000NM001K` |
| **28TB** | `ST28000NM003K` |
| **30TB** | `ST30000NM004K` |
| **32TB** | `ST32000NM004K` |

## Detailed SATA table

| Capacity | Exos family | Documentation era | Exact model code | Sector format | Variant | Notes |
|---:|---|---:|---|---|---|---|
| **1TB** | Exos 7E2 | 2017 | `ST1000NM0008` | 512n | Standard |  |
| **1TB** | Legacy Exos 7E8 | 2016–2017 | `ST1000NM0055` | 512n | Standard |  |
| **1TB** | Exos 7E8 (A generation) | 2019 | `ST1000NM000A` | 512n | Standard |  |
| **2TB** | Exos 7E2 | 2017 | `ST2000NM0008` | 512n | Standard |  |
| **2TB** | Legacy Exos 7E8 | 2016–2017 | `ST2000NM0055` | 512n | Standard |  |
| **2TB** | Legacy Exos 7E8 | 2016–2017 | `ST2000NM0125` | 512e | Standard |  |
| **2TB** | Exos 7E8 (A generation) | 2019 | `ST2000NM000A` | 512n | Standard |  |
| **2TB** | Exos 7E8 (A generation) | 2019 | `ST2000NM001A` | 512e | Standard |  |
| **2TB** | Exos 7E10 | 2021+ | `ST2000NM000B` | 512n | Standard |  |
| **2TB** | Exos 7E10 | 2021+ | `ST2000NM017B` | 512e / FastFormat | Standard | Preferred 7E10 format for a typical SATA NAS |
| **3TB** | Legacy Exos 7E8 | 2016–2017 | `ST3000NM0005` | 512n | Standard |  |
| **3TB** | Exos 7E8 (A generation) | 2019 | `ST3000NM000A` | 512n | Standard |  |
| **4TB** | Legacy Exos 7E8 | 2016–2017 | `ST4000NM0035` | 512n | Standard |  |
| **4TB** | Legacy Exos 7E8 | 2016–2017 | `ST4000NM0115` | 512e | Standard |  |
| **4TB** | Exos 7E8 (A generation) | 2019 | `ST4000NM000A` | 512n | Standard |  |
| **4TB** | Exos 7E8 (A generation) | 2019 | `ST4000NM002A` | 512e | Standard |  |
| **4TB** | Exos 7E10 | 2021+ | `ST4000NM000B` | 512n | Standard |  |
| **4TB** | Exos 7E10 | 2021+ | `ST4000NM024B` | 512e / FastFormat | Standard | Preferred 7E10 format for a typical SATA NAS |
| **6TB** | Legacy Exos 7E8 | 2016–2017 | `ST6000NM0235` | 512n | Standard |  |
| **6TB** | Legacy Exos 7E8 | 2016–2017 | `ST6000NM0115` | 512e | Standard |  |
| **6TB** | Exos 7E8 (A generation) | 2019 | `ST6000NM002A` | 512n | Standard |  |
| **6TB** | Exos 7E8 (A generation) | 2019 | `ST6000NM021A` | 512e | Standard |  |
| **6TB** | Exos 7E10 | 2021+ | `ST6000NM000B` | 512n | Standard |  |
| **6TB** | Exos 7E10 | 2021+ | `ST6000NM019B` | 512e / FastFormat | Standard | Preferred 7E10 format for a typical SATA NAS |
| **8TB** | Legacy Exos 7E8 | 2016–2017 | `ST8000NM0055` | 512e | Standard |  |
| **8TB** | Exos X10 | 2017 | `ST8000NM0016` | 512e | Hyperscale SATA | Valid SATA model; verify seller firmware and warranty |
| **8TB** | Exos X10 | 2017 | `ST8000NM0206` | 512e | Standard |  |
| **8TB** | Exos 7E8 (A generation) | 2019 | `ST8000NM000A` | 512e | Standard |  |
| **8TB** | Exos 7E10 | 2021+ | `ST8000NM017B` | 512e / FastFormat | Standard |  |
| **10TB** | Exos X10 | 2017 | `ST10000NM0016` | 512e | Hyperscale SATA | Valid SATA model; verify seller firmware and warranty |
| **10TB** | Exos X10 | 2017 | `ST10000NM0086` | 512e | Standard |  |
| **10TB** | Exos X14 | 2018 | `ST10000NM0478` | 512e / FastFormat | Standard |  |
| **10TB** | Exos X16 | 2019 | `ST10000NM001G` | 512e / FastFormat | Standard |  |
| **10TB** | Exos X18 | 2020–2021 | `ST10000NM018G` | 512e / FastFormat | Standard |  |
| **10TB** | Exos 7E10 | 2021+ | `ST10000NM017B` | 512e / FastFormat | Standard |  |
| **12TB** | Exos X12 | 2017 | `ST12000NM0007` | 512e | Standard |  |
| **12TB** | Exos X14 | 2018 | `ST12000NM0008` | 512e / FastFormat | Standard |  |
| **12TB** | Exos X16 | 2019 | `ST12000NM001G` | 512e / FastFormat | Standard |  |
| **12TB** | Exos X18 | 2020–2021 | `ST12000NM000J` | 512e / FastFormat | Standard |  |
| **12TB** | Exos X24 | 2023–2024 | `ST12000NM002H` | 512e / FastFormat | Standard / ISE |  |
| **14TB** | Exos X14 | 2018 | `ST14000NM0018` | 512e / FastFormat | Standard |  |
| **14TB** | Exos X16 | 2019 | `ST14000NM001G` | 512e / FastFormat | Standard |  |
| **14TB** | Exos X18 | 2020–2021 | `ST14000NM000J` | 512e / FastFormat | Standard |  |
| **16TB** | Exos X16 | 2019 | `ST16000NM001G` | 512e / FastFormat | Standard | Your current NAS drive model **← your model** |
| **16TB** | Exos X18 | 2020–2021 | `ST16000NM000J` | 512e / FastFormat | Standard |  |
| **16TB** | Exos X24 | 2023–2024 | `ST16000NM002H` | 512e / FastFormat | Standard / ISE |  |
| **18TB** | Exos X18 | 2020–2021 | `ST18000NM000J` | 512e / FastFormat | Standard |  |
| **18TB** | Exos X20 | 2021–2022 | `ST18000NM003D` | 512e / FastFormat | Standard |  |
| **20TB** | Exos X20 | 2021–2022 | `ST20000NM007D` | 512e / FastFormat | Standard |  |
| **20TB** | Exos X22 | 2023 | `ST20000NM004E` | 512e / FastFormat | Standard |  |
| **20TB** | Exos X24 | 2023–2024 | `ST20000NM002H` | 512e / FastFormat | Standard / ISE |  |
| **22TB** | Exos X22 | 2023 | `ST22000NM001E` | 512e / FastFormat | Standard |  |
| **24TB** | Exos X24 | 2023–2024 | `ST24000NM002H` | 512e / FastFormat | Standard / ISE |  |
| **24TB** | Exos HAMR CMR | 2025–2026 | `ST24000NM001K` | 512e | Standard / ISE | Newer K-generation channel model |
| **28TB** | Exos HAMR CMR | 2025–2026 | `ST28000NM003K` | 512e | Standard / ISE |  |
| **30TB** | Exos HAMR CMR | 2025–2026 | `ST30000NM004K` | 512e | Standard / ISE |  |
| **32TB** | Exos HAMR CMR | 2025–2026 | `ST32000NM004K` | 512e | Standard / ISE | Current CMR channel model |

## Official Seagate factory-recertified `C` models

This is the complete capacity range listed in Seagate's official factory-recertified Exos data sheet. These are separate `C`-suffix product SKUs rather than ordinary X16, X18, X22 or X24 retail-generation model numbers.

### Complete `C`-model quick lookup

| Capacity | Official Seagate factory-recertified SATA model |
|---:|---|
| **16TB** | `ST16000NM002C` |
| **20TB** | `ST20000NM002C` |
| **22TB** | `ST22000NM000C` |
| **24TB** | `ST24000NM000C` |
| **26TB** | `ST26000NM000C` |
| **28TB** | `ST28000NM000C` |

### Detailed factory-recertified table

| Capacity | Product family | Exact model code | Interface | Recording technology | Sector format as shipped | FastFormat | Spindle speed | Cache | MTBF rating | Factory warranty | Notes |
|---:|---|---|---|---|---|---|---:|---:|---:|---:|---|
| **16TB** | Exos Factory Recertified | `ST16000NM002C` | SATA 6Gb/s | CMR | 512e | 512e → 4Kn supported | 7200 RPM | 512MB | 2.5 million hours | 6 months | Closest official `C`-model alternative to your 16TB X16 |
| **20TB** | Exos Factory Recertified | `ST20000NM002C` | SATA 6Gb/s | CMR | 512e | 512e → 4Kn supported | 7200 RPM | 512MB | 2.5 million hours | 6 months |  |
| **22TB** | Exos Factory Recertified | `ST22000NM000C` | SATA 6Gb/s | CMR | 512e | 512e → 4Kn supported | 7200 RPM | 512MB | 2.5 million hours | 6 months |  |
| **24TB** | Exos Factory Recertified | `ST24000NM000C` | SATA 6Gb/s | CMR | 512e | 512e → 4Kn supported | 7200 RPM | 512MB | 2.5 million hours | 6 months |  |
| **26TB** | Exos Factory Recertified | `ST26000NM000C` | SATA 6Gb/s | CMR | 512e | 512e → 4Kn supported | 7200 RPM | 512MB | 2.5 million hours | 6 months | Official `C` model even though 26TB is absent from the normal channel-model table |
| **28TB** | Exos Factory Recertified | `ST28000NM000C` | SATA 6Gb/s | CMR | 512e | 512e → 4Kn supported | 7200 RPM | 512MB | 2.5 million hours | 6 months | Listed separately on the following page of Seagate's data sheet |

**No other capacities are listed in Seagate's official `C`-model data sheet.** In particular, it does not list official `C` models for 1TB–14TB, 18TB, 30TB or 32TB.

All six models are specified by Seagate as:

- 3.5-inch SATA 6Gb/s
- CMR
- helium sealed
- 512e when shipped
- FastFormat-capable for conversion to 4Kn
- 7200 RPM
- 512MB cache
- 2.5-million-hour MTBF
- six-month Seagate limited warranty
- approximately 190MB/s maximum sustained outer-diameter transfer rate

A retailer may advertise a longer seller warranty, but that is separate from Seagate's six-month factory-recertified warranty.

## SATA Exos model to avoid for this NAS use

| Capacity | Model | Why it is excluded |
|---:|---|---|
| **8TB** | `ST8000AS0003` | Exos 5E8 **drive-managed SMR** archive drive. Seagate states that it is not intended for NAS applications. |

Some newer very-high-capacity Exos products also use SMR. Do not assume that every Exos drive is CMR merely because the label says Exos. The `ST32000NM004K` listed above is the current **32TB CMR** channel model.

## Best searches for your existing 16TB array

Search these exact phrases:

```text
"ST16000NM001G" SATA 16TB refurbished
"ST16000NM001G" SATA 16TB recertified
"ST16000NM000J" SATA 16TB
"ST16000NM002H" SATA 16TB
"ST16000NM002C" SATA 16TB recertified
```

Priority order for the closest match:

1. `ST16000NM001G` — exact Exos X16 match
2. `ST16000NM000J` — newer Exos X18 standard SATA
3. `ST16000NM002H` — newer Exos X24 standard/ISE SATA
4. `ST16000NM002C` — official Seagate recertified model

## Refurbished-drive checks

Before buying, verify all of the following in the listing or with the seller:

- **SATA 6Gb/s**, not SAS
- **CMR**, not SMR
- Prefer **512e** or a FastFormat drive currently formatted as 512e
- The exact `ST...` model on the photographed label matches the listing
- SMART report, power-on hours, reallocated/pending sectors and passed long test
- Seller warranty length, return shipping terms and who pays for a failed-drive return
- Whether it is Seagate factory recertified, seller refurbished, or an OEM pull

> A FastFormat drive may have been changed to 4Kn by a previous owner. Ask the seller to confirm its current logical sector format, especially when buying refurbished stock.

## Official Seagate sources

- [Exos 7E2 support](https://www.seagate.com/au/en/support/internal-hard-drives/enterprise-hard-drives/exos-7E2/)
- [Legacy 7E8 data sheet](https://www.seagate.com/www-content/datasheets/pdfs/ent-cap-3-5-hdd-data-sheetDS1882-3-1610US-en_US.pdf)
- [Exos 7E8 A-generation data sheet](https://www.seagate.com/www-content/datasheets/pdfs/exos-7-e8-data-sheet-DS1957-2-1904US-en_US.pdf)
- [Exos 7E10 data sheet](https://www.seagate.com/www-content/datasheets/pdfs/exos-7e10-DS1957-6M-2104US-en_US.pdf)
- [Exos X10 data sheet](https://www.seagate.com/www-content/datasheets/pdfs/exos-x-10DS1948-1-1709US-en_US.pdf)
- [Exos X18 SATA product manual](https://www.seagate.com/content/dam/seagate/migrated-assets/www-content/product-content/enterprise-hdd-fam/exos-x18-channel/_shared/en-us/docs/100865854d.pdf)
- [Current Exos HAMR/CMR data sheet](https://www.seagate.com/content/dam/seagate/en/content-fragments/products/datasheets/exos-m-v1-2/exos-v1-2-DS2045-4-2511-en_US.pdf)
- [Seagate factory-recertified Exos data sheet](https://www.seagate.com/content/dam/seagate/en/content-fragments/products/datasheets/exos-recertified-drive/exos-recertified-drive-DS2045-2-2010US-October-2020-en_US.pdf)
- [Exos 5E8 support](https://www.seagate.com/au/en/support/internal-hard-drives/enterprise-hard-drives/exos-5E/)

---

### Important limitation

Seagate has produced many encrypted, FIPS, SAS, PowerBalance and OEM-specific sub-SKUs. This document is intentionally a **shopping list of standard/base 3.5-inch SATA models suitable for comparison**, rather than every suffix Seagate has ever manufactured.
