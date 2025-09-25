import numpy as np
import pandas as pd
import random, string
from datetime import timedelta

SEED = 22
np.random.seed(SEED); random.seed(SEED)

DATE_START = pd.Timestamp("2024-01-01")
DATE_END   = pd.Timestamp("2024-12-31")
DATES = pd.date_range(DATE_START, DATE_END, freq="D")

# Number of products per category
N_PER_CAT = 14

CATS = {
    "Tops":        dict(base_price=(20, 45),   margin=(0.45, 0.60)),
    "Bottoms":     dict(base_price=(30, 70),   margin=(0.45, 0.60)),
    "Dresses":     dict(base_price=(35, 120),  margin=(0.45, 0.60)),
    "Outerwear":   dict(base_price=(60, 220),  margin=(0.45, 0.60)),
    "Shoes":       dict(base_price=(40, 180),  margin=(0.45, 0.60)),
    "Accessories": dict(base_price=(8,  60),   margin=(0.45, 0.60)),
}

CHANNELS = [
    ("google_ads",   ["always_on_search","summer_sale","black_friday","mid_year_sale","holiday_push"]),
    ("facebook_ads", ["always_on_social","summer_sale","black_friday","mid_year_sale","holiday_push"]),
    ("email",        ["newsletter","summer_sale","black_friday","mid_year_sale","holiday_push"]),
    ("seo",          ["organic_brand","evergreen_content"]),
    ("influencer",   ["seasonal_collab","evergreen_affiliate"]),
]
UTM_MAP = {"google_ads":"google","facebook_ads":"facebook","email":"email","seo":"seo","influencer":"influencer","direct":"direct"}

# Approximate daily spend ranges (USD)
BASE_SPEND = {
    "google_ads":   (700, 1600),
    "facebook_ads": (400, 1200),
    "email":        (0, 0),      
    "seo":          (0, 0),      
    "influencer":   (180, 600),
}

BASE_CTR = {
    "google_ads":   (0.02, 0.05),
    "facebook_ads": (0.006, 0.02),
    "email":        (0.03, 0.09),
    "seo":          (0.12, 0.22),
    "influencer":   (0.01, 0.03),
}

IMP_PER_DOLLAR = {
    "google_ads":   (70, 120),
    "facebook_ads": (100, 180),
    "email":        (3000, 7000),
    "seo":          (1800, 4000),
    "influencer":   (450, 1000),
}

BASE_CVR = {
    "google_ads":   0.012,
    "facebook_ads": 0.007,
    "email":        0.020,
    "seo":          0.018,
    "influencer":   0.006,
    "direct":       0.018,
}

PAYMENT_METHODS = ["credit_card","paypal","apple_pay","klarna"]
US_STATES = [
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA",
    "ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK",
    "OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC"
]

# -------------------------------------------------
def black_friday(d: pd.Timestamp) -> bool:
    if d.month != 11: return False
    first = pd.Timestamp(d.year, 11, 1)
    offset = (3 - first.weekday()) % 7  # Thu=3
    fourth_thu = first + pd.Timedelta(days=offset + 21)
    return d == fourth_thu + pd.Timedelta(days=1)

def season(d: pd.Timestamp):
    """Return (demand_factor, promo_discount) for the day."""
    demand = 1.0
    disc = 0.0

    # seasonal demand lift
    if d.month in (3,4):    demand *= 1.10        # spring refresh
    if d.month in (6,7):    demand *= 1.15        # summer
    if d.month == 8:        demand *= 1.12        # back-to-school
    if d.month in (11,12):  demand *= 1.25        # holiday

    # mid-year sale
    if pd.Timestamp(d.year,6,10) <= d <= pd.Timestamp(d.year,6,30):
        disc += 0.20; demand *= 1.35
    # Labor Day
    if d.month == 9:
        first = pd.Timestamp(d.year,9,1)
        first_mon = first + pd.Timedelta(days=(7 - first.weekday()) % 7)
        if first_mon - pd.Timedelta(days=3) <= d <= first_mon:
            disc += 0.15; demand *= 1.25
    # BF/CM
    if black_friday(d) or (d.month == 12 and d.weekday() == 0 and d.day <= 7):
        disc += 0.35; demand *= 1.8
    # Holiday gifting
    if pd.Timestamp(d.year,12,10) <= d <= pd.Timestamp(d.year,12,24):
        disc += 0.10; demand *= 1.35
    # Post-Xmas clearance
    if pd.Timestamp(d.year,12,26) <= d <= pd.Timestamp(d.year,12,31):
        disc += 0.25; demand *= 1.30
    # newsletter pulses
    if d.day in (1, 15): demand *= 1.05

    return demand, float(np.clip(disc, 0.0, 0.60))

def pick_campaign(channel, d, disc):
    cands = dict(CHANNELS)[channel]
    if disc >= 0.25:
        if "black_friday" in cands and (d.month in (11,12) or black_friday(d)): return "black_friday"
        if d.month == 12 and "holiday_push" in cands:                            return "holiday_push"
        if d.month == 6 and "mid_year_sale" in cands:                            return "mid_year_sale"
        if d.month in (6,7,8) and "summer_sale" in cands:                        return "summer_sale"
    return cands[0]

def cvr_adj(d, disc):
    adj = 1.0
    if disc >= 0.15: adj *= 1.15
    if disc >= 0.30: adj *= 1.10
    if d.weekday() >= 5: adj *= 1.03
    return adj

def basket_units(d, disc):
    base = np.random.uniform(1.1, 1.8)
    if disc >= 0.15: base += np.random.uniform(0.2, 0.5)
    if d.month in (11,12): base += np.random.uniform(0.1, 0.3)
    return max(1, min(5, int(round(base + np.random.uniform(-0.3, 1.3)))))

def unit_price_discount(disc):
    return float(np.clip(disc + np.random.uniform(-0.03, 0.03), 0.0, 0.25))

def direct_clicks(demand):
    return int(np.random.uniform(600, 1500) * (0.5 + 0.3 * demand))


# PRODUCTS
def gen_products():
    rows, pid = [], 10001
    for cat, meta in CATS.items():
        for _ in range(N_PER_CAT):
            model = ''.join(random.choices(string.ascii_uppercase, k=2)) + "-" + ''.join(random.choices(string.digits, k=3))
            name = f"{cat[:-1] if cat.endswith('s') else cat} {model}"
            base = np.random.uniform(*meta["base_price"])
            current = round(base * np.random.uniform(0.95, 1.15), 2)
            margin = np.random.uniform(*meta["margin"])
            cost = round(current * (1 - margin), 2)
            rows.append([pid, name, cat, current, cost]); pid += 1
    return pd.DataFrame(rows, columns=["product_id","product_name","category","current_price","cost_price"])

products = gen_products()
products_by_cat = {c: df for c, df in products.groupby("category")}

# MARKETING_SPEND (daily)
mk_rows = []
for d in DATES:
    demand, disc = season(d)
    for channel, _ in CHANNELS:
        lo, hi = BASE_SPEND[channel]
        spend = 0.0 if hi == 0 else float(np.random.uniform(lo, hi) * (0.8 + 0.4 * demand))
        imp_lo, imp_hi = IMP_PER_DOLLAR[channel]
        if channel in ("seo","email") and spend == 0:
            impressions = int(np.random.uniform(imp_lo, imp_hi) * (0.6 + 0.8 * demand))
        else:
            impressions = int(spend * np.random.uniform(imp_lo, imp_hi))
        ctr_lo, ctr_hi = BASE_CTR[channel]
        boost = 1.0 + (0.15 if disc >= 0.15 and channel in ("google_ads","facebook_ads","email") else 0.0)
        ctr = float(np.clip(np.random.uniform(ctr_lo, ctr_hi) * boost, 0.001, 0.60))
        clicks = int(impressions * ctr)
        campaign = pick_campaign(channel, d, disc)
        mk_rows.append([d.date(), channel, campaign, round(spend,2), impressions, clicks, round(ctr,4)])

marketing_spend = pd.DataFrame(mk_rows, columns=[
    "date","channel","campaign_name","spend_amount","impressions","clicks","ctr"
])


# ORDERS & ORDER_ITEMS
order_rows, item_rows = [], []
order_id, order_item_id = 500000, 800000

for d in DATES:
    demand, disc = season(d)
    day_mkt = marketing_spend[marketing_spend["date"] == d.date()]
    cvr_multiplier = cvr_adj(d, disc)

    ch_to_orders = {}
    for _, r in day_mkt.iterrows():
        ch, clicks = r["channel"], int(r["clicks"])
        cvr = BASE_CVR[ch] * cvr_multiplier * np.random.uniform(0.85, 1.15)
        cvr = float(np.clip(cvr, 0.0005, 0.20))
        conv = np.random.binomial(clicks, cvr)
        if conv: ch_to_orders[(ch, r["campaign_name"])] = ch_to_orders.get((ch, r["campaign_name"]), 0) + int(conv)

    dc = direct_clicks(demand)
    cvr = BASE_CVR["direct"] * cvr_multiplier * np.random.uniform(0.9, 1.1)
    conv = np.random.binomial(dc, float(np.clip(cvr, 0.0003, 0.20)))
    if conv: ch_to_orders[("direct","type_in_return")] = int(conv)

    cancel_rate = 0.03 if disc < 0.15 else 0.04
    ship_delay_rate = 0.08

    for (ch, camp), n in ch_to_orders.items():
        for _ in range(n):
            order_id += 1
            customer_id = np.random.randint(10000, 99999)
            x = np.random.random()
            if   x < cancel_rate:              status = "cancelled"
            elif x < cancel_rate+ship_delay_rate: status = ("pending" if np.random.random()<0.5 else "shipped")
            else:                               status = "delivered"
            pay = random.choice(PAYMENT_METHODS)
            shipping_state = random.choice(US_STATES)

            n_items = basket_units(d, disc)
            price_disc = unit_price_discount(disc)

            order_total = 0.0
            for _i in range(n_items):
                order_item_id += 1
                if d.month in (11,12):
                    weights = {"Outerwear":1.6,"Dresses":1.1,"Tops":1.2,"Bottoms":1.1,"Shoes":1.3,"Accessories":0.9}
                elif d.month in (6,7):
                    weights = {"Outerwear":0.6,"Dresses":1.4,"Tops":1.3,"Bottoms":1.2,"Shoes":1.1,"Accessories":1.0}
                else:
                    weights = {"Outerwear":1.0,"Dresses":1.1,"Tops":1.2,"Bottoms":1.1,"Shoes":1.0,"Accessories":1.0}
                cats, w = list(weights.keys()), np.array(list(weights.values()))
                cat_choice = np.random.choice(cats, p=w/w.sum())
                prod = products_by_cat[cat_choice].sample(1).iloc[0]
                qty = int(max(1, round(np.random.lognormal(mean=0.0, sigma=0.6))))
                unit_price = round(float(prod["current_price"])*(1-price_disc)*np.random.uniform(0.98,1.02), 2)
                line_total = round(unit_price*qty, 2); order_total += line_total

                item_rows.append([
                    order_item_id, order_id, prod["product_name"], prod["category"],
                    qty, unit_price, line_total
                ])

            if order_total > 0:
                order_rows.append([
                    order_id, customer_id, d.date(), status, round(order_total,2),
                    pay, shipping_state, UTM_MAP[ch], camp
                ])

orders = pd.DataFrame(order_rows, columns=[
    "order_id","customer_id","order_date","order_status","total_amount",
    "payment_method","shipping_state","utm_source","utm_campaign"
]).reset_index(drop=True)

order_items = pd.DataFrame(item_rows, columns=[
    "order_item_id","order_id","product_name","product_category","quantity","unit_price","total_price"
])

products.to_csv("products3.csv", index=False)
marketing_spend.to_csv("marketing_spend3.csv", index=False)
orders.to_csv("orders3.csv", index=False)
order_items.to_csv("order_items3.csv", index=False)

print("Done!")
