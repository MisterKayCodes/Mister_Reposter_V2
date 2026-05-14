# Mister Reposter V2: Business Strategy & Policy

## 1. The "Strict Discount" Policy
* **Pattern**: Prevent users from repeatedly using introductory or discounted prices.
* **Mechanism**: Use the `is_premium` logic to track if a user has *ever* used a discount. If `has_had_discount` is True, they can only renew at the "Normal" market rate.
* **Logic**: This maintains the perceived value of the software and prevents "subscription hopping."

## 2. Pricing Tiers (Draft)
* **Tier 1: Starter (Self-Service)**
  - 1 Pair, No Schedule.
  - Price: $10 - $15 / month.
* **Tier 2: Pro (Self-Service)**
  - 4 Pairs, Custom Schedules, Replacement links.
  - Price: $25 - $40 / month.
* **Tier 3: VIP Managed**
  - Admin handles everything. User just watches stats.
  - Price: $99 / month or ₦50,000 / month.

## 3. Market Targeting
* **Primary Target**: Foreign USD earners (SaaS model).
* **Secondary Target**: Local Nigerian businesses (Managed service model).

## 4. Anti-Impersonator Policy
* Keep the code private. 
* Vet clients manually for the "Managed" service to ensure ethical use.
