"""Synthetic claims with complete, consistent recording, modeled on how a modern claims system is meant to be used.

Run (from the repo root):  python generator/synthetic_claims.py --n 20000 --seed 7 [--out data/interim/synthetic]

Output CSVs: header, exposures, money, activities and notes, plus coverages, contact_roles, matters,
negotiations, vehicles, incidents and users. Everything is generated: no real claim, person, vehicle or note
text is used. Claim numbers start with 9 so they are easy to recognize as synthetic.
Column definitions: docs/data-dictionary.md

How the data is structured
  Money      net_amount and original_amount equal amount; payments are always positive; a void is a voided
             row plus a replacement; a closed exposure's reserves net to exactly what was paid.
  Limits     every exposure has a coverage row with a limit; limit_reached is computed
             (paid_to_date >= coverage_limit) and paid never exceeds the limit.
  Users      every user has a title, a department and a team group.
  Activities a completed activity has close_date set and >= create_time; an open one has close_date NULL;
             each activity is created once.
  Claims     lob and loss_type are always set; every claim has >= 1 exposure; segment is always a real one;
             a claim is closed iff all its exposures are closed, and close_date = last exposure close.
  Dates      loss <= reported <= opened <= assigned; matter filing >= loss; service >= filing;
             demands and offers are dated when they happened; note authoring_date == create_time.
  Vehicles   every vehicle has a vehicles row (VIN with a valid check digit, year/make/model/style) and an
             incidents row with first_point_of_impact (only values from the standard collision-point list),
             vehicle_direction, damage_description, severity and est_repair_cost; impact points match the
             cause (rear-ended => insured front / other rear); every claim header has loss_description;
             vehicle exposures carry incident_id.
  Work steps each step is an activity with the date it was done and a note authored by whoever closed it.
             The liability decision (header.insured_fault_pct) precedes the first liability payment; police
             report, statements, witness and scene inspection precede the decision; quote and review_quote
             precede the first payment; subro_check follows the decision and drives the subrogation referral
             (recovery only when the insured is not 100% at fault); total losses get a salvage notice and a
             salvage status activity that closes when the salvage sells; PIP and BI get medical-report and
             treatment follow-up activities.
  Notes      every note has a topic, an author with title/department, and (when it documents one) the
             activity it belongs to.
  History    every table has bean_version (1 + the number of changes since the row was created) and update_time
             (when it last changed). change_log.csv lists each change: table, row, column, old and new value,
             who and when. A row is created at version 1 and each later edit is a logged change: claim and
             exposure assignment, the liability decision, each payment (paid_to_date), closing, approval of a
             payment or reserve, check issue and clearing, voids, activity completion, the repair estimate
             and service of a suit. Notes, coverages, vehicles, negotiations, attorney roles and users are
             never edited, so they stay at version 1. The self-check replays the log and must reproduce
             every current value, and each change's old value must equal the previous new value.
Assumptions made for this data: PIP income-loss/loss-of-services/funeral/survivor limits,
recovery_category values, check_status values, fictional firms/vendors/providers.
Deliberately left out: reopens, reassignments, fault ratings, litigation beyond one suit per exposure.
"""
import argparse
import datetime as dt
import random
from pathlib import Path

import pandas as pd

ASOF = dt.datetime(2026, 10, 7, 12, 0)
M, H, D = dt.timedelta(minutes=1), dt.timedelta(hours=1), dt.timedelta(days=1)
INS, TPL = "Insured's loss", "Third-party liability"
FAST, NOINJ, PIPSEG = "Auto Fast Track", "Auto Liability No Injury", "Auto (PIP) non-Complex Injury"
BISEG, BICX, SENS = "Auto (BI) non-Complex Injury", "Auto Complex Injury", "Sensitive (Special Permisions)"
PNL, PLL, PLP, PBI = "Property No Liability", "Property Large Loss", "Property Liability PD Only", "Property non-Complex Injury"

# subtype -> exposure_type, loss_party, (ln mu, ln sigma) of the loss, (min, max) days exposure stays open
SPEC = {
    "coll_vd": ("VehicleDamage", INS, (8.0, 0.8), (10, 45)),
    "comp_vd": ("VehicleDamage", INS, (7.3, 0.9), (7, 40)),
    "rental_vd": ("VehicleDamage", INS, (6.3, 0.6), (5, 30)),
    "towlabor_towlabor": ("TowOnly", INS, (5.0, 0.5), (1, 10)),
    "apd_vd": ("VehicleDamage", TPL, (8.0, 0.8), (15, 60)),
    "apd_pd": ("PropertyDamage", TPL, (7.0, 0.9), (15, 60)),
    "pip_medical_cougar": ("PIPDamages", INS, (7.4, 1.0), (60, 240)),
    "pip_income_loss_cougar": ("PIPDamages", INS, (7.2, 0.8), (60, 200)),
    "pip_loss_srvce_cougar": ("PIPDamages", INS, (6.3, 0.7), (60, 200)),
    "pip_funeral_cougar": ("PIPDamages", INS, (7.3, 0.1), (20, 90)),
    "pip_survivor_cougar": ("PIPDamages", INS, (8.2, 0.4), (30, 120)),
    "abi_bid": ("BodilyInjuryDamage", TPL, (9.4, 1.2), (45, 200)),
    "uim_bid": ("BodilyInjuryDamage", INS, (9.8, 1.2), (90, 300)),
    "udim_bid": ("BodilyInjuryDamage", INS, (9.8, 1.2), (90, 300)),
    "dwl_pd": ("PropertyDamage", INS, (9.0, 1.1), (20, 120)),
    "ppd_ppd": ("PropertyDamage", INS, (8.0, 1.0), (15, 90)),
    "lu_lud": ("PropertyDamage", INS, (7.6, 0.8), (15, 90)),
    "os_pd": ("PropertyDamage", INS, (8.4, 1.0), (15, 90)),
    "pli_pd": ("PropertyDamage", TPL, (8.3, 1.0), (20, 100)),
    "pli_bi": ("BodilyInjuryDamage", TPL, (9.0, 1.2), (60, 250)),
    "liabmp_mp": ("MedPay", INS, (6.9, 0.8), (20, 100)),
}
OFFSET_DAYS = {"rental_vd": (0, 3), "pip_medical_cougar": (0, 10), "pip_income_loss_cougar": (14, 60),
               "pip_loss_srvce_cougar": (14, 60), "pip_funeral_cougar": (1, 20), "pip_survivor_cougar": (1, 20),
               "abi_bid": (5, 90), "uim_bid": (30, 150), "udim_bid": (30, 150), "apd_pd": (0, 5),
               "ppd_ppd": (0, 10), "lu_lud": (0, 10), "os_pd": (0, 10), "pli_pd": (0, 30), "pli_bi": (0, 30),
               "liabmp_mp": (0, 10), "apd_vd": (0, 2)}
FIRST_PARTY_DED = {"coll_vd", "comp_vd", "dwl_pd", "ppd_ppd", "os_pd"}
BI_SUBS = {"abi_bid", "uim_bid", "udim_bid", "pli_bi"}
PIP_SUBS = {s for s in SPEC if s.startswith("pip_")}

# (weight, parts [(subtype, probability)], loss causes); the first part (probability 1) is the primary exposure
AUTO = [
    (0.22, [("coll_vd", 1), ("rental_vd", .2), ("towlabor_towlabor", .2), ("pip_medical_cougar", .16)],
     ["rear-end collision", "intersection collision", "single-vehicle collision", "backed into object", "rollover",
      "parked vehicle struck"]),
    (0.15, [("apd_vd", 1), ("coll_vd", .85), ("apd_pd", .05), ("rental_vd", .2), ("towlabor_towlabor", .15),
            ("pip_medical_cougar", .32), ("abi_bid", .3)],
     ["rear-ended another vehicle", "failed to yield at intersection", "unsafe lane change"]),
    (0.30, [("comp_vd", 1), ("rental_vd", .1), ("towlabor_towlabor", .02)],
     ["hail", "glass break", "theft", "vandalism", "animal strike", "fire"]),
    (0.13, [("towlabor_towlabor", 1)], ["disabled vehicle", "lockout", "flat tire", "out of fuel"]),
    (0.14, [("apd_vd", 1), ("apd_pd", .03)], ["rear-ended another vehicle", "unsafe lane change"]),
    (0.06, [("coll_vd", 1), ("apd_vd", .8), ("pip_medical_cougar", 1), ("abi_bid", .7), ("rental_vd", .3),
            ("towlabor_towlabor", .2)], ["intersection collision", "head-on collision", "rear-ended another vehicle"]),
]
PR = [
    (0.75, [("dwl_pd", 1), ("lu_lud", .04), ("ppd_ppd", .13), ("os_pd", .05)],
     ["burst pipe", "appliance leak", "wind", "hail", "tree fall", "freezing", "fire"]),
    (0.12, [("ppd_ppd", 1)], ["theft", "burglary"]),
    (0.08, [("pli_pd", 1), ("pli_bi", .3)], ["guest injury", "damage to neighbor property"]),
    (0.05, [("dwl_pd", 1), ("lu_lud", .5), ("ppd_ppd", .6)], ["fire", "major water loss"]),
]
LARGE_PR = 3  # index of the large-loss property scenario
P_SUIT, SUIT_MIN_PAID = 0.6, 5000  # share of represented BI exposures paid at least this much that are in suit

TEAM = {  # group -> (job title, department)
    "#Cougar Care Team (Repairable)": ("Claims Adjuster", "Claims"), "#Cougar NON-DRP Team (Repairable)": ("Claims Adjuster", "Claims"),
    "#Express Care Team": ("Claims Adjuster", "Claims"), "#Total Loss Team": ("Specialty Adjuster", "Claims"),
    "#Auto - Tow": ("Claims Assistant", "Claims"), "#Auto Liability No Injury Team": ("Claims Adjuster", "Claims"),
    "#Auto PIP Team": ("PIP Claim Assistant", "Claims"),
    "#Bodily Injury - BI/UM - Attorney - Minor": ("Casualty Claims Adjuster", "Casualty Claims"),
    "#Bodily Injury - BI/UM - No Attorney - Minor": ("Casualty Claims Adjuster", "Casualty Claims"),
    "#Bodily Injury - BI/UM - Complex": ("Casualty Claims Examiner", "Casualty Claims"),
    "#Bodily Injury - UIM": ("Casualty Claims Adjuster", "Casualty Claims"),
    "#Bodily Injury - Litigation": ("Casualty Claims Examiner", "Casualty Claims"),
    "#Bodily Injury - Home or Fatality": ("Casualty Claims Examiner", "Casualty Claims"),
    "#Home Interior Damage Team": ("Inside Property Adjuster", "Property Claims"),
    "#Home Exterior Damage Team": ("Inside Property Adjuster", "Property Claims"),
    "#Home Fire/Smoke Damage Claims Team": ("Property Adjuster", "Property Claims"),
    "#Home Contents Only/Theft": ("Inside Property Adjuster", "Property Claims"),
    "#Home Condo/Townhome & Liability Claims Team": ("Property Adjuster", "Property Claims"),
    "#Subro: Out-Bound Undisputed": ("Subrogation Specialist", "Claims"), "#Salvage Recovery": ("Salvage Specialist", "Claims"),
}
FIRST = ["Avery", "Blake", "Casey", "Dana", "Emerson", "Finley", "Gray", "Harper", "Indigo", "Jules", "Kendall", "Logan",
         "Morgan", "Noel", "Oakley", "Parker", "Quinn", "Reese", "Sage", "Tatum", "Uri", "Vale", "Wren", "Yael"]
LAST = ["Ashdown", "Birchfield", "Castellan", "Dunmore", "Eastwick", "Farrow", "Garrity", "Holloway", "Ingram", "Jessup",
        "Kestrel", "Lockhart", "Marlowe", "Northcott", "Ormsby", "Pemberton", "Quillan", "Radcliffe", "Sutter", "Thorne",
        "Underhill", "Vance", "Whitlock", "Yardley"]
CITIES = ["Salt Lake City", "Provo", "Ogden", "St. George", "Logan", "Orem", "Sandy", "Layton", "Lehi", "Cedar City"]
SHOPS = ["Beehive Collision", "Canyon Auto Body", "Summit Repair Center", "Lakeside Auto Works"]
PROVIDERS = ["Wasatch Valley Medical", "Timpanogos Chiropractic", "Summit Physical Therapy", "Great Basin Imaging", "Red Rock Urgent Care"]
FIRMS = ["Deseret Peak Injury Law", "Wasatch Front Trial Attorneys", "Bonneville Law Group", "Uinta Legal Partners",
         "Salt Flat Injury Lawyers", "Zion Advocacy Group"]
PATTERNS = {
    "COUGAR_Review_New_Claim": "Review New Claim", "COUGAR_Verify_Coverage": "Verify coverage",
    "COUGAR_Complete_Hours": "Complete 8 hour contact", "COUGAR_Complete_Investigation": "Complete investigation",
    "COUGAR_Review_New_Exposure": "Review New Exposure", "approve_payment": "Review and approve new payment",
    "approve_reserve_change": "Review and approve reserve change", "30_day_diary": "30 day diary",
    "60_day_diary": "60 day diary", "90_day_diary": "90 day diary", "general_reminder": "General reminder (diary)",
    "iso_matches": "ISO matches found", "new_bill": "Review new bill received", "COUGAR_Fault_Analysis": "No fault analysis",
    "follow_up_insured": "Follow Up with insured", "COUGAR_Void_Check_Complete": "Void Check Complete",
    "new_mail": "Review new mail",
    "determine_claim_decision": "Determine claim decision", "quote": "Get quote for repairs/replacement",
    "review_quote": "Review and approve quote for repairs/replacement", "police_report": "Get police report",
    "get_statement_insured driver": "Obtain recorded statement from insured driver",
    "interview_claimant": "Obtain recorded statment from claimant driver",  # sic: spelling kept as written
    "witness_statement": "Get a statement from witness", "vehicle_inspection": "Get vehicle inspected",
    "scene_inspection": "Get accident scene inspected", "property_inspection": "Get property inspected",
    "initial_med_report": "Get initial medical report", "medical_report_claimant": "Get claimant medical reports",
    "follow_up_treatment": "Follow up on treatment status", "subro_check": "Determine if opportunity for recovery",
    "COUGAR_New_Subro": "New Subrogation Referral", "COUGAR_Salvage_Notice": "Notify salvage carrier of vehicle",
    "salvage_vehicle": "Salvage Vehicle Status",
}
TOPIC = {"pip": "PIP", "bi": "Bodily Injury", "tow": "Auto Glas/Roadside", "rental": "Rental", "prop": "Property", "other": "General"}


# ---- vehicles, impact points, damage ----------------------------------------------------------
FRONT = "Front bumper, grille, hood & radiator"
REAR = "Rear bumper, rear body panel, trunk lid/ liftgate"
NONCOL, NODMG = "Non-collision (comprehensive loss)", "No Damage"
VALID_FPOI = {  # the standard collision-point list
    FRONT, REAR, NONCOL, NODMG, "Rollover", "Roof panel", "Undercarriage", "Total loss",
    "Point of impact unknown (collision loss)", "Left fender - front (headlamp area)", "Left fender - side & wheel area",
    "Left front door", "Left quarter panel", "Left rear door", "Right fender - front (headlamp area)",
    "Right fender - side & wheel area", "Right front door", "Right quarter panel", "Right rear door", "Front",
    "Left front", "Left rear", "Left side", "Rear", "Right front", "Right rear", "Right side", "Top / roof"}
SIDE_ANY = ["Left fender - front (headlamp area)", "Right fender - front (headlamp area)", "Left front door", "Right front door",
            "Left rear door", "Right rear door", "Left fender - side & wheel area", "Right fender - side & wheel area",
            "Left quarter panel", "Right quarter panel"]
# cause -> (insured impact points, other-vehicle impact points or None if single vehicle, insured direction,
#           other direction, narrative). Directions come from a fixed list of vehicle movements.
IMPACT = {
    "rear-end collision": ([REAR], [FRONT], "Stopped in traffic lane", "Going straight",
                           "Insured was stopped in traffic on {street} in {city} when another vehicle struck the rear of the insured vehicle. {weather}"),
    "intersection collision": ([FRONT, "Left fender - front (headlamp area)", "Right fender - front (headlamp area)"], SIDE_ANY,
                               "Going through intersection", "Going through intersection",
                               "Insured and another vehicle collided in an intersection on {street} in {city}. {weather}"),
    "single-vehicle collision": ([FRONT, "Left fender - front (headlamp area)", "Right fender - front (headlamp area)"], None,
                                 "Negotiating curve", None,
                                 "Insured lost control on {street} in {city} and struck a {obj}. {weather}"),
    "backed into object": ([REAR], None, "Backing up", None,
                           "Insured was backing out of a parking space in {city} and struck a {obj}."),
    "rollover": (["Rollover"], None, "Negotiating curve", None,
                 "Insured vehicle left the roadway on {street} near {city} and rolled over. {weather}"),
    "parked vehicle struck": ([REAR, FRONT, "Left front door", "Right front door", "Left rear door", "Right rear door",
                               "Left quarter panel", "Right quarter panel"], [FRONT], None, "Entering parking space",
                              "Insured's vehicle was parked in a lot on {street} in {city} when another vehicle struck it."),
    "head-on collision": ([FRONT], [FRONT], "Going straight", "Going straight",
                          "Insured and an oncoming vehicle collided head-on on {street} in {city}. {weather}"),
    "rear-ended another vehicle": ([FRONT], [REAR], "Going straight", "Stopped in traffic lane",
                                   "Insured was traveling on {street} in {city} and could not stop in time, striking the rear of the vehicle ahead. {weather}"),
    "failed to yield at intersection": ([FRONT, "Left fender - front (headlamp area)", "Right fender - front (headlamp area)"],
                                        ["Left front door", "Right front door", "Left rear door", "Right rear door",
                                         "Left fender - side & wheel area", "Right fender - side & wheel area"],
                                        "Going through intersection", "Going through intersection",
                                        "Insured failed to yield at an intersection on {street} in {city} and struck the side of a crossing vehicle."),
    "unsafe lane change": (["Left fender - side & wheel area", "Right fender - side & wheel area"], [""], "Merging/changing lanes",
                           "Going straight", "Insured changed lanes on {street} in {city} and contacted the vehicle in the adjacent lane."),
    "hail": ([NONCOL], None, None, None, "A hailstorm in {city} damaged the insured vehicle while it was parked."),
    "glass break": ([NONCOL], None, None, None, "A rock struck the windshield of the insured vehicle on {street} in {city}."),
    "theft": ([NONCOL], None, None, None, "The insured vehicle was stolen from {place} in {city}."),
    "vandalism": ([NONCOL], None, None, None, "Insured found the vehicle vandalized {place} in {city}."),
    "animal strike": ([FRONT], None, "Going straight", None, "Insured struck a {animal} on {street} near {city}. {weather}"),
    "fire": ([NONCOL], None, None, None, "The insured vehicle caught fire {place} in {city}."),
    "disabled vehicle": ([NODMG], None, "Disabled in traffic lane", None,
                         "The insured vehicle broke down on {street} in {city} and could not be driven."),
    "lockout": ([NODMG], None, None, None, "Insured locked the keys in the vehicle in {city} and requested roadside assistance."),
    "flat tire": ([NODMG], None, "Stopped on shoulder of road", None,
                  "Insured had a flat tire on {street} in {city} and requested roadside assistance."),
    "out of fuel": ([NODMG], None, "Stopped on shoulder of road", None,
                    "Insured ran out of fuel on {street} in {city} and requested roadside assistance."),
}
PARKED_P = {"hail": 1, "theft": 1, "vandalism": 1, "fire": .5, "lockout": 1, "flat tire": .3, "parked vehicle struck": 1}
LABOR_ONLY = {"lockout", "flat tire", "out of fuel"}  # roadside labor, vehicle is not towed
NONCOL_TEXT = {"hail": "Hail dents across the roof, hood and trunk lid; paint cracked in places.",
               "glass break": "Windshield cracked from a rock strike; no other damage.",
               "theft": "Vehicle stolen and later recovered with ignition and interior damage.",
               "vandalism": "Paint keyed along one side and a window broken.",
               "fire": "Fire damage to the engine compartment, wiring and hood."}
BREAKDOWN = {"disabled vehicle": "Mechanical failure; no collision damage.", "lockout": "Keys locked inside; no damage.",
             "flat tire": "Flat tire; no other damage.", "out of fuel": "Out of fuel; no damage."}
ZONE = {"fender - front": ["front fender", "headlamp", "bumper corner", "wheel well"],
        "fender - side": ["fender", "front wheel", "tire", "suspension components"],
        "front door": ["front door skin", "door glass", "mirror", "door frame"],
        "rear door": ["rear door skin", "door glass", "door frame"],
        "quarter panel": ["quarter panel", "rear wheel arch", "tail lamp", "rear bumper corner"]}
FRONT_PARTS = ["front bumper cover", "grille", "hood", "headlamps", "radiator support", "radiator/condenser"]
REAR_PARTS = ["rear bumper cover", "trunk lid/liftgate", "tail lamps", "rear body panel", "rear frame rail"]
STREETS = ["State Street", "Redwood Road", "700 East", "Main Street", "State Route 89", "Bangerter Highway", "University Avenue"]
WEATHER = ["Roads were dry.", "Roads were wet.", "Roads were snow-covered.", "Clear conditions.", "It was dark with low visibility."]
OBJECTS = ["guardrail", "fence", "utility pole", "retaining wall", "mailbox"]
ANIMALS = ["deer", "elk", "dog", "coyote"]
PLACES = ["a parking lot", "the insured's driveway", "the street in front of the residence"]
ROOMS = ["kitchen", "basement", "bathroom", "laundry room", "garage", "upstairs hallway"]
PR_TEXT = {
    "burst pipe": "A supply line burst in the {room} of the insured home in {city}, soaking flooring and drywall.",
    "appliance leak": "An appliance leak in the {room} of the insured home in {city} damaged flooring and cabinets.",
    "wind": "High winds in {city} lifted shingles and damaged fencing at the insured home.",
    "hail": "Hail in {city} damaged the roof, siding and gutters of the insured home.",
    "tree fall": "A tree fell onto the roof of the insured home in {city} during a storm.",
    "freezing": "A frozen pipe burst in the {room} of the insured home in {city} while the family was away.",
    "fire": "A fire started in the {room} of the insured home in {city}, causing fire and smoke damage.",
    "theft": "Insured reported items stolen from the home in {city}.",
    "burglary": "Insured returned home in {city} to find a forced entry and electronics and jewelry missing.",
    "guest injury": "A guest slipped and fell on icy steps at the insured home in {city} and reported injuries.",
    "damage to neighbor property": "A tree limb from the insured's yard in {city} fell on a neighbor's fence.",
    "major water loss": "A major water loss in the {room} of the insured home in {city} spread to several rooms.",
}
MODELS = [  # make, model, vehicle style, new price, weight
    ("Toyota", "Camry", "Passenger car", 28000, 1), ("Honda", "Accord", "Passenger car", 29000, 1),
    ("Honda", "CR-V", "Passenger car", 33000, 1), ("Subaru", "Outback", "Passenger car", 34000, 1),
    ("Toyota", "RAV4", "Passenger car", 33000, 1), ("Hyundai", "Elantra", "Passenger car", 22000, 1),
    ("Nissan", "Altima", "Passenger car", 26000, 1), ("Mazda", "CX-5", "Passenger car", 31000, 1),
    ("Tesla", "Model 3", "Passenger car", 42000, 1), ("Jeep", "Wrangler", "Passenger car", 38000, 1),
    ("Ford", "Explorer", "Passenger car", 40000, 1), ("Chevrolet", "Equinox", "Passenger car", 28000, 1),
    ("Ford", "F-150", "Pickup", 45000, 1.3), ("Chevrolet", "Silverado 1500", "Pickup", 46000, 1.2),
    ("Ram", "1500", "Pickup", 47000, 1), ("Toyota", "Tacoma", "Pickup", 38000, 1),
    ("Honda", "Odyssey", "Van", 38000, .6), ("Dodge", "Grand Caravan", "Van", 30000, .5),
    ("Harley-Davidson", "Street Glide", "Motorcycle", 22000, .2)]
COLORS = ["White", "Black", "Silver", "Gray", "Blue", "Red", "Green", "Tan"]
VIN_SEQ = "ABCDEFGHJKLMNPRSTVWXY123456789"  # model-year code, 2010 = A
VIN_TR = {**{c: i for i, c in enumerate("0123456789")}, **dict(zip("ABCDEFGH", range(1, 9))),
          **dict(zip("JKLMN", range(1, 6))), "P": 7, "R": 9, **dict(zip("STUVWXYZ", [2, 3, 4, 5, 6, 7, 8, 9]))}
VIN_W = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]


def vin_check(v):
    s = sum(VIN_TR[c] * w for c, w in zip(v, VIN_W)) % 11
    return "X" if s == 10 else str(s)


def make_vin(R, year):
    pool = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"  # no I, O, Q
    yc = VIN_SEQ[(year - 2010) % 30 if year >= 2010 else (year - 1980) % 30]
    v = "9SY" + "".join(R.choice(pool) for _ in range(5)) + "0" + yc + "S" + "".join(R.choice("0123456789") for _ in range(6))
    return v[:8] + vin_check(v) + v[9:]


def damage_text(point, sev, cause):
    """Damage description that matches the impact point and how bad it is."""
    if point == NODMG:
        return BREAKDOWN[cause]
    if point == NONCOL:
        txt = NONCOL_TEXT[cause]
    else:
        if point == "Rollover":
            parts = ["roof panel", "A/B pillars", "door glass", "all four doors"]
        elif point == FRONT:
            parts = FRONT_PARTS
        elif point == REAR:
            parts = REAR_PARTS
        else:
            key = next(k for k in ZONE if k in point.lower())
            parts = [f"{point.split()[0].lower()} {p}" for p in ZONE[key]]
        n = {"minor": 1, "moderate": 3}.get(sev, len(parts))
        verb = {"minor": "Scuffed and dented", "moderate": "Dented and creased"}.get(sev, "Crushed and buckled")
        txt = f"{verb}: {', '.join(parts[:n])}."
        if sev in ("severe", "total_loss"):
            txt += " Structural and frame damage suspected."
    if sev == "total_loss":
        txt += " Damage exceeds repair value; vehicle declared a total loss."
    return txt


AGENCIES = ["Salt Lake City Police Department", "Utah Highway Patrol", "Provo Police Department", "Sandy Police Department"]
CONTRACTORS = ["Wasatch Restoration", "Summit Contractors", "Bonneville Builders"]
INJURIES = ["soft tissue neck and back strain", "cervical strain with headaches", "lumbar sprain", "shoulder contusion",
            "whiplash-associated disorder", "knee contusion", "concussion symptoms"]
INSURED_AT_FAULT = {"rear-ended another vehicle", "failed to yield at intersection", "unsafe lane change"}
OTHER_AT_FAULT = {"rear-end collision", "parked vehicle struck"}


def fault_pct(R, cause, subs):
    """Insured's share of fault, set by the liability decision. None where no other party is involved."""
    # About 10% of decided claims end up shared (0 < insured % < 100), some with the insured under 50%.
    if cause in INSURED_AT_FAULT:
        return R.choices([100, 80, 70, 60, 50, 40], [.91, .025, .025, .02, .01, .01])[0]
    if cause in OTHER_AT_FAULT:
        return R.choices([0, 10, 20, 30, 40], [.91, .03, .03, .02, .01])[0]
    if cause in ("intersection collision", "head-on collision"):
        if "apd_vd" in subs:  # the insured pays the other party, so the insured is at fault
            return R.choices([100, 50, 60, 70, 40, 30], [.82, .07, .04, .03, .02, .02])[0]
        return R.choices([0, 50, 30, 20, 40], [.8, .09, .05, .03, .03])[0]
    return None


def money(x):
    return f"${x:,.0f}"


class Gen:
    def __init__(self, seed):
        self.R = random.Random(seed)
        self.n = dict(claim=900000, exp=9000000, txn=90000000, act=95000000, note=97000000, cov=9100000,
                      matter=9200000, neg=9300000, user=9400000, veh=9500000, inc=9600000, chg=9700000, evt=9800000)
        self.changes = []
        self.rows = {k: [] for k in ("header", "exposures", "money", "activities", "notes", "coverages",
                                     "contact_roles", "matters", "negotiations", "users", "vehicles", "incidents")}
        self.by_group, self.users = {}, []
        self.build_users()

    def nid(self, k):
        self.n[k] += 1
        return self.n[k]

    # ---- people -------------------------------------------------------------------------------
    def new_user(self, title, dept, group):
        names = {u["name"] for u in self.users}
        while True:
            name = f"{self.R.choice(FIRST)} {self.R.choice(LAST)}"
            if name not in names:
                break
        u = dict(user_id=self.nid("user"), name=name, title=title, dept=dept, group=group)
        self.users.append(u)
        self.by_group.setdefault(group, []).append(u)
        return u

    def build_users(self):
        for g, (title, dept) in TEAM.items():
            for _ in range(4):
                self.new_user(title, dept, g)
        self.supervisors = [self.new_user("Claims Supervisor", "Claims", "Claims Supervisors") for _ in range(4)]
        self.intake = [self.new_user("Claims Intake Specialist", "Claims Intake", "Claims Intake") for _ in range(5)]
        self.system = dict(user_id=self.nid("user"), name="System User", title="Automated Process", dept="Claims Operations",
                           group="Claims Operations")
        self.users.append(self.system)
        self.rows["users"] = self.users

    def adjuster(self, group):
        return self.R.choice(self.by_group[group])

    # ---- small helpers ------------------------------------------------------------------------
    def biz(self, day):
        return dt.datetime.combine(day, dt.time(self.R.randint(8, 16), self.R.randint(0, 59), self.R.randint(0, 59)))

    def u(self, lo, hi):
        return self.R.uniform(lo, hi)

    def cents(self, x):
        return round(x + 1e-9, 2)

    def ln(self, mu, sg):
        return self.R.lognormvariate(mu, sg)

    def pick(self, scen):
        return self.R.choices(scen, weights=[s[0] for s in scen])[0]

    # ---- one claim ----------------------------------------------------------------------------
    def make_claim(self):
        R, S = self.R, self
        lob = "auto" if R.random() < 0.85 else "pr"
        scen = S.pick(AUTO if lob == "auto" else PR)
        large_pr = lob == "pr" and scen is PR[LARGE_PR]
        subs = [s for s, p in scen[1] if p == 1 or R.random() < p]
        if lob == "auto" and "pip_medical_cougar" in subs:
            for extra, p in (("pip_income_loss_cougar", .06), ("pip_loss_srvce_cougar", .03),
                             ("pip_funeral_cougar", .004), ("pip_survivor_cougar", .003)):
                if R.random() < p:
                    subs.append(extra)
        if lob == "auto" and ("pip_medical_cougar" in subs or "abi_bid" in subs) and R.random() < .03:
            subs.append(R.choice(["uim_bid", "udim_bid"]))
        cid = S.nid("claim")
        loss_day = (dt.datetime(2024, 1, 1) + D * R.randint(0, 997)).date()
        lag = R.choice([0, 0, 0, 1, 1, 2, 3, 7, 14, 30]) if lob == "auto" else R.choice([0, 1, 2, 3, 10, 30, 90])
        reported = min(S.biz(loss_day + D * lag), ASOF - 4 * H)
        reported = max(reported, dt.datetime.combine(loss_day, dt.time(7, 0)))
        opened = reported + dt.timedelta(minutes=S.u(1, 15))
        veh = S.new_vehicle(cid, "insured") if lob == "auto" else None
        ctx = dict(acv=veh["acv"] if veh else 0, total_loss=R.random() < .1,
                   pd_limit=R.choices([25000, 50000, 100000], [.55, .25, .2])[0],
                   bi_limit=R.choices([25000, 50000, 100000, 250000, 500000], [.3, .3, .25, .1, .05])[0],
                   um_limit=R.choices([25000, 50000, 100000, 250000], [.3, .3, .3, .1])[0],
                   pip_tier=R.choices([3000, 5000, 10000], [.5, .3, .2])[0],
                   dwelling=round(min(900000, max(100000, S.ln(12.3, .45))), -3), large=large_pr,
                   liab_limit=R.choice([100000, 300000]), ded=R.choice([250, 500, 1000]),
                   prop_ded=R.choice([1000, 2500]), cause=R.choice(scen[2]), city=R.choice(CITIES),
                   lob=lob, loss_day=loss_day, opened=opened, claim_id=cid)
        ctx["fault"] = fault_pct(R, ctx["cause"], subs) if lob == "auto" else None
        pts = IMPACT[ctx["cause"]] if lob == "auto" else None
        ctx["police"] = bool(pts) and (ctx["cause"] == "theft" or (
            pts[0] not in ([NONCOL], [NODMG]) and R.random() < (.6 if pts[1] is not None else .25)))
        exposures = []
        for i, sub in enumerate(subs):
            lo, hi = OFFSET_DAYS.get(sub, (0, 0))
            create = opened + dt.timedelta(minutes=S.u(2, 30)) if i == 0 or hi == 0 else opened + D * S.u(lo, hi)
            if create > ASOF - 3 * H:
                continue
            exposures.append(S.make_exposure(ctx, sub, create))
        loss_description = ctx["loss_description"] = S.make_incidents(ctx, veh, exposures)
        owner_group = exposures[0]["group"]
        owner = S.adjuster(owner_group)
        assigned = opened + dt.timedelta(minutes=S.u(2, 45))
        all_closed = all(e["state"] == "closed" for e in exposures)
        close = max(e["close_t"] for e in exposures) if all_closed else None
        hdr = dict(
            claim_id=cid, claim_number=f"9{cid - 900000:06d}", lob=lob, loss_type=lob.upper(),
            claim_state="closed" if all_closed else "open", loss_date=dt.datetime.combine(loss_day, dt.time(0, 0)),
            reported_date=reported, claim_opened=opened, close_date=close, assigned_name=owner["name"],
            assigned_title=owner["title"], assigned_group=owner_group, assignment_date=assigned,
            loss_cause=ctx["cause"], loss_city=ctx["city"], loss_description=loss_description,
            insured_fault_pct=ctx["fault"])
        S.rows["header"].append(hdr)
        n_act = len(S.rows["activities"])
        acts = S.make_activities(ctx, exposures, owner, close)
        S.make_notes(ctx, exposures, owner, close, acts)
        for e in exposures:
            S.flush_exposure(e)
        S.log_changes(ctx, owner, exposures, acts, close, hdr, S.rows["activities"][n_act:])

    # ---- change history -----------------------------------------------------------------------
    def log(self, table, row_id, claim_id, t, by, event, cols):
        """Record one new version of a row: each column that changed, with its value before and after."""
        if t is None or t > ASOF:
            return
        eid = self.nid("evt")
        for col, old, new in cols:
            self.changes.append((self.nid("chg"), eid, table, row_id, claim_id, t, by, event, col, fmt(old), fmt(new)))

    def log_changes(self, ctx, owner, exposures, acts, claim_close, hdr, act_rows):
        """Everything that happens to a row after it is created is a logged change; version 1 is the insert."""
        S, R = self, self.R
        cid, sysu, me = ctx["claim_id"], self.system["name"], owner["name"]
        sup = lambda: R.choice(S.supervisors)["name"]
        dec = acts.get("decision")
        decided = bool(dec and dec["close_date"] and ctx["fault"] is not None)
        hdr["insured_fault_pct"] = ctx["fault"] if decided else None  # exists only once the decision is made
        S.log("header", cid, cid, hdr["assignment_date"], sysu, "claim_assigned",
              [("assigned_name", None, hdr["assigned_name"]), ("assigned_group", None, hdr["assigned_group"]),
               ("assignment_date", None, hdr["assignment_date"])])
        if decided:
            S.log("header", cid, cid, dec["close_date"], me, "liability_decision", [("insured_fault_pct", None, ctx["fault"])])
        if claim_close:
            S.log("header", cid, cid, claim_close, me, "claim_closed", [("claim_state", "open", "closed"),
                                                                       ("close_date", None, claim_close)])
        for inc in ctx["incidents"]:  # the repair estimate is known once the quote activity is complete
            if inc["est_repair_cost"] is None:
                continue
            qs = [acts.get(("quote", e["pk"])) for e in exposures
                  if e["incident_id"] == inc["incident_id"] and e["sub"] in ("coll_vd", "comp_vd", "apd_vd")]
            qs = [q for q in qs if q and q["close_date"]]
            if qs:
                S.log("incidents", inc["incident_id"], cid, qs[0]["close_date"], qs[0]["closed_by_name"],
                      "estimate_received", [("est_repair_cost", None, inc["est_repair_cost"])])
            else:
                inc["est_repair_cost"] = None
        for e in exposures:
            pk = e["pk"]
            S.log("exposures", pk, cid, e["assign"], sysu, "exposure_assigned",
                  [("assigned_name", None, e["user"]["name"]), ("assigned_group", None, e["group"]),
                   ("assignment_date", None, e["assign"])])
            cum = 0.0
            for p in sorted(e["payments"], key=lambda r: r["submit_date"]):
                new = S.cents(cum + p["amount"])
                cols = [("paid_to_date", cum, new)]
                if new > 0 and new >= e["limit"] - .005 and not (cum > 0 and cum >= e["limit"] - .005):
                    cols.append(("limit_reached", False, True))
                S.log("exposures", pk, cid, p["submit_date"], p["created_by_name"], "payment_recorded", cols)
                cum = new
            if e["state"] == "closed":
                S.log("exposures", pk, cid, e["close_t"], e["user"]["name"], "exposure_closed",
                      [("state", "open", "closed"), ("close_date", None, e["close_t"])])
            for r in e["money"]:
                tx = r["txn_id"]
                if r["_approval"]:
                    a = acts.get(("approval", tx))
                    S.log("money", tx, cid, r["submit_date"], a["closed_by_name"] if a and a["closed_by_name"] else sup(),
                          "approved", [("status", "submitting", "submitted"), ("submit_date", None, r["submit_date"])])
                if r["check_issue_date"]:
                    S.log("money", tx, cid, r["check_issue_date"], sysu, "check_issued",
                          [("check_issue_date", None, r["check_issue_date"]), ("check_status", None, "issued")])
                    if r["check_status"] == "cleared":
                        S.log("money", tx, cid, r["check_clear_date"], sysu, "check_cleared",
                              [("check_status", "issued", "cleared"), ("check_clear_date", None, r["check_clear_date"])])
                    if r["status"] == "voided":
                        S.log("money", tx, cid, r["_void_t"], sup(), "payment_voided",
                              [("status", "submitted", "voided"), ("check_status", "issued", "voided")])
            for m in e["extra"]["matters"]:  # a suit is entered when filed and updated when served
                S.log("matters", m["matter_id"], cid, m["service_date"], me, "suit_served", [("service_date", None, m["service_date"])])
        for r in act_rows:
            if r["status"] == "complete":
                S.log("activities", r["act_pk"], cid, r["close_date"], r["closed_by_name"], "activity_completed",
                      [("status", "open", "complete"), ("close_date", None, r["close_date"]),
                       ("closed_by_name", None, r["closed_by_name"])])

    # ---- vehicles and incidents ---------------------------------------------------------------
    def new_vehicle(self, claim_id, role):
        R, S = self.R, self
        make, model, style, price, _ = R.choices(MODELS, weights=[m[4] for m in MODELS])[0]
        year = max(2004, 2026 - int(R.expovariate(1 / 7)))
        acv = round(min(60000, max(2500, price * .86 ** (2026 - year))), -2)
        v = dict(vehicle_id=S.nid("veh"), claim_id=claim_id, role=role, vin=make_vin(R, year), year=year, make=make,
                 model=model, style=style, color=R.choice(COLORS),
                 license_plate=f"{R.choice('ABCDEFGHJKLMNPRSTUVWXYZ')}{R.randint(10, 99)} {R.randint(0, 9)}"
                               f"{R.choice('ABCDEFGHJKLMNPRSTUVWXYZ')}{R.choice('ABCDEFGHJKLMNPRSTUVWXYZ')}",
                 plate_state="UT" if R.random() < .93 else R.choice(["ID", "NV", "CO", "AZ", "WY"]), acv=acv)
        S.rows["vehicles"].append({k: v[k] for k in v if k != "acv"})
        return v

    def make_incidents(self, ctx, veh, exposures):
        """One incident per vehicle (first point of impact, direction, damage) and the claim's incident description."""
        R, S = self.R, self
        ctx["incidents"] = []
        cause, city = ctx["cause"], ctx["city"]
        if ctx["lob"] == "pr":
            return PR_TEXT[cause].format(city=city, room=R.choice(ROOMS))
        ins_pts, oth_pts, ins_dir, oth_dir, narrative = IMPACT[cause]
        ins_pt = R.choice(ins_pts)
        oth_pt = None
        if oth_pts is not None:
            oth_pt = (("Right quarter panel" if ins_pt.startswith("Left") else "Left quarter panel")
                      if cause == "unsafe lane change" else R.choice(oth_pts))
        by = {e["sub"]: e for e in exposures}
        ins_exp = by.get("coll_vd") or by.get("comp_vd")
        apd = by.get("apd_vd")

        def severity(pt, loss, acv, total=False):
            if pt == NODMG:
                return "none"
            if total:
                return "total_loss"
            if loss is None:
                return R.choices(["minor", "moderate", "severe"], [.5, .35, .15])[0]
            r = loss / acv
            return "minor" if r < .15 else "moderate" if r < .45 else "severe"

        def incident(v, role, party, pt, direction, sev, loss, total=False, tow_exp=False):
            p_driv = {"none": 1.0, "minor": .98, "moderate": .7, "severe": .15, "total_loss": .4}[sev]
            if cause in ("disabled vehicle", "flat tire", "out of fuel") or (tow_exp and cause not in LABOR_ONLY):
                p_driv = 0
            collision = pt not in (NODMG, NONCOL)
            parked = role == "insured" and R.random() < PARKED_P.get(cause, 0)
            drivable = R.random() < p_driv
            towed = cause not in LABOR_ONLY and (cause == "disabled vehicle" or tow_exp or (not drivable and R.random() < .9))
            inc = dict(incident_id=S.nid("inc"), claim_id=ctx["claim_id"], vehicle_id=v["vehicle_id"], role=role,
                       loss_party=party, first_point_of_impact=pt, vehicle_direction=None if parked else direction,
                       vehicle_parked=parked, vehicle_towed=towed, total_loss=sev == "total_loss", damage_severity=sev,
                       damage_description=damage_text(pt, sev, cause), drivable=drivable,
                       airbags_deployed=collision and sev in ("severe", "total_loss") and R.random() < .4,
                       est_repair_cost=None if loss is None or sev == "none" else S.cents(
                           v["acv"] * S.u(.9, 1.3) if total else loss), vehicle_acv=v["acv"])
            S.rows["incidents"].append(inc)
            ctx["incidents"].append(inc)
            ctx.setdefault("veh_by_id", {})[v["vehicle_id"]] = v
            ctx.setdefault("inc_by_id", {})[inc["incident_id"]] = inc
            return inc

        total = ctx["total_loss"] and ins_exp is not None and ins_pt != NODMG
        ins_sev = severity(ins_pt, ins_exp["loss"] if ins_exp else None, veh["acv"], total)
        ins_inc = incident(veh, "insured", INS, ins_pt, ins_dir, ins_sev, ins_exp["loss"] if ins_exp else None, total,
                           tow_exp="towlabor_towlabor" in by)
        oth_inc = None
        if oth_pt is not None:
            oveh = S.new_vehicle(ctx["claim_id"], "third_party")
            oth_inc = incident(oveh, "third_party", TPL, oth_pt, oth_dir, severity(oth_pt, apd["loss"] if apd else None,
                                                                                    oveh["acv"]), apd["loss"] if apd else None)
        for e in exposures:
            if e["sub"] in ("coll_vd", "comp_vd", "rental_vd", "towlabor_towlabor"):
                e["incident_id"] = ins_inc["incident_id"]
            elif e["sub"] == "apd_vd" and oth_inc:
                e["incident_id"] = oth_inc["incident_id"]
        return narrative.format(street=R.choice(STREETS), city=city, weather=R.choice(WEATHER), obj=R.choice(OBJECTS),
                                animal=R.choice(ANIMALS), place=R.choice(PLACES))

    # ---- one exposure -------------------------------------------------------------------------
    def make_exposure(self, ctx, sub, create):
        R, S = self.R, self
        etype, party, (mu, sg), (dlo, dhi) = SPEC[sub]
        limit = {"coll_vd": ctx["acv"], "comp_vd": ctx["acv"], "rental_vd": R.choice([900, 1200, 1500]),
                 "towlabor_towlabor": R.choice([100, 250]), "apd_vd": ctx["pd_limit"], "apd_pd": ctx["pd_limit"],
                 "pip_medical_cougar": ctx["pip_tier"], "pip_income_loss_cougar": 13000, "pip_loss_srvce_cougar": 7300,
                 "pip_funeral_cougar": 1500, "pip_survivor_cougar": 5000, "abi_bid": ctx["bi_limit"],
                 "uim_bid": ctx["um_limit"], "udim_bid": ctx["um_limit"], "dwl_pd": ctx["dwelling"],
                 "ppd_ppd": round(ctx["dwelling"] * .5), "lu_lud": round(ctx["dwelling"] * .2),
                 "os_pd": round(ctx["dwelling"] * .1), "pli_pd": ctx["liab_limit"], "pli_bi": ctx["liab_limit"],
                 "liabmp_mp": R.choice([1000, 5000])}[sub]
        ded = ctx["ded"] if sub in ("coll_vd", "comp_vd") else ctx["prop_ded"] if sub in FIRST_PARTY_DED else 0
        if sub in ("coll_vd", "comp_vd") and ctx["total_loss"]:
            loss = limit * S.u(.85, 1.0)
        elif sub in ("coll_vd", "comp_vd"):
            loss = min(S.ln(mu, sg), limit * .8)
        elif sub == "dwl_pd" and ctx["large"]:
            loss = S.ln(11.9, .6)
        else:
            loss = S.ln(mu, sg)
        if sub == "pip_funeral_cougar":
            loss = limit
        claimed = max(loss - ded, 0)
        if sub in ("apd_vd", "apd_pd", "abi_bid") and ctx["fault"] is not None:
            claimed *= ctx["fault"] / 100  # liability payments to the other party cover only the insured's share
        no_pay = R.random() < .05 and sub not in BI_SUBS and sub not in PIP_SUBS
        paid_total = 0.0 if no_pay else S.cents(min(claimed, limit))
        attorney = sub in BI_SUBS and R.random() < (.85 if loss > 20000 else .35 if sub == "abi_bid" else .75)
        suit, suit_plan = attorney and paid_total >= SUIT_MIN_PAID and R.random() < P_SUIT, None
        if suit:  # plan the suit now so it is only kept if it was already filed by the as-of date
            sdur = S.u(450, 900)
            assigned_s = create + D * sdur * S.u(.05, .3)
            filing_s = assigned_s + D * S.u(60, 200)
            suit_plan = (sdur, assigned_s, filing_s)
            suit = filing_s + 3 * D <= ASOF
        if sub in PIP_SUBS:
            seg = SENS if sub in ("pip_funeral_cougar", "pip_survivor_cougar") else PIPSEG
            group = "#Bodily Injury - Home or Fatality" if seg == SENS else "#Auto PIP Team"
        elif sub in BI_SUBS:
            complex_ = loss >= 75000
            seg = (BICX if complex_ else BISEG) if ctx["lob"] == "auto" else PBI
            group = ("#Bodily Injury - Litigation" if suit else "#Bodily Injury - BI/UM - Complex" if complex_
                     else "#Bodily Injury - UIM" if sub in ("uim_bid", "udim_bid")
                     else "#Bodily Injury - BI/UM - Attorney - Minor" if attorney
                     else "#Bodily Injury - BI/UM - No Attorney - Minor")
        elif sub == "towlabor_towlabor":
            seg, group = "Towing & Roadside", "#Auto - Tow"
        elif sub in ("apd_vd", "apd_pd"):
            seg, group = NOINJ, "#Auto Liability No Injury Team"
        elif sub in ("coll_vd", "comp_vd", "rental_vd"):
            seg = FAST
            ctx.setdefault("vd_group", R.choice(["#Cougar Care Team (Repairable)", "#Cougar NON-DRP Team (Repairable)",
                                                 "#Express Care Team"]))
            group = "#Total Loss Team" if ctx["total_loss"] and sub != "rental_vd" else ctx["vd_group"]
        else:
            seg = PLL if loss >= 100000 else PLP if sub == "pli_pd" else PNL
            c = ctx["cause"]
            group = ("#Home Condo/Townhome & Liability Claims Team" if sub in ("pli_pd", "pli_bi", "liabmp_mp")
                     else "#Home Contents Only/Theft" if c in ("theft", "burglary")
                     else "#Home Fire/Smoke Damage Claims Team" if c in ("fire", "major water loss")
                     else "#Home Exterior Damage Team" if c in ("wind", "hail", "tree fall")
                     else "#Home Interior Damage Team")
        user = S.adjuster(group)
        dur = S.u(dlo, dhi)
        if attorney:
            dur = S.u(150, 540)
        if suit:
            dur = suit_plan[0]
        e = dict(pk=S.nid("exp"), claim_id=ctx["claim_id"], sub=sub, etype=etype, seg=seg, party=party, group=group,
                 user=user, create=create, assign=create + dt.timedelta(minutes=S.u(1, 30)), limit=limit, ded=ded,
                 loss=loss, paid_total=paid_total, attorney=attorney, suit=suit, money=[],
                 extra=dict(roles=[], matters=[], negs=[]), cov_id=S.nid("cov"), payments=[], incident_id=None,
                 end=create + D * dur, recov=None, first_pay=None)
        e["suit_plan"] = suit_plan if suit else None
        # plan every money event time first, then close the exposure after the last one
        npay = {"pip_medical_cougar": R.randint(2, 6), "pip_income_loss_cougar": R.randint(1, 4),
                "pip_loss_srvce_cougar": R.randint(1, 3), "dwl_pd": R.choice([1, 2, 2, 3]),
                "coll_vd": R.choice([1, 1, 1, 2]), "comp_vd": R.choice([1, 1, 1, 2]),
                "abi_bid": 2 if suit else 1}.get(sub, 1)
        if paid_total == 0:
            npay = 0
        fr = sorted(S.u(.2, .98) for _ in range(max(npay - 1, 0))) + [1.0]
        weights = [S.u(.5, 1.5) for _ in range(npay)]
        parts = [S.cents(paid_total * w / sum(weights)) for w in weights[:-1]] if npay else []
        if npay:
            parts.append(S.cents(paid_total - sum(parts)))
        pays = [(create + D * dur * f, a, "final" if k == npay - 1 else
                 ("supplement" if sub in ("coll_vd", "comp_vd", "dwl_pd") else "partial"))
                for k, (f, a) in enumerate(zip(fr, parts))]
        streams = [("COUGAR_indemnity", "indemnity", "Reserve", "Payment", pays,
                    max(paid_total * S.u(.7, 1.3), 100) if npay else max(claimed * .5, 100))]
        if sub in ("coll_vd", "comp_vd", "apd_vd", "dwl_pd") and R.random() < .6:
            fee = R.choice([8.5, 10.5, 17.5, 25.0, 45.0])
            streams.append(("aoexpense", "COUGAR_otherphysdam", "Reserve", "Payment",
                            [(create + D * S.u(1, 10), fee, "final")], fee))
        if suit:
            dcc = sorted(S.u(.3, 1.0) for _ in range(R.randint(2, 6)))
            streams.append(("dccexpense", "COUGAR_legalLiability", "Reserve", "Payment",
                            [(create + D * dur * f, S.cents(S.u(500, 6000)), "partial") for f in dcc], 15000))
        recov = None
        total_loss = ctx["total_loss"] and sub in ("coll_vd", "comp_vd")
        fault = ctx["fault"]
        p_rec = .9 if total_loss else (.85 if sub == "coll_vd" and fault is not None and fault < 100 else
                                       .02 if sub == "comp_vd" else 0)
        salv = total_loss and R.random() < .95
        if paid_total and R.random() < p_rec and (salv or sub == "comp_vd" or (fault is not None and fault < 100)):
            share = 1.0 if fault is None else (100 - fault) / 100  # other party's share of what was paid
            amt = S.cents(loss * S.u(.12, .3) if salv else paid_total * share * S.u(.85, 1.0))
            t = max(p[0] for p in pays) + D * S.u(20, 120)
            recov = ("COUGAR_indemnity", "indemnity", "RecoveryReserve", "Recovery", [(t, amt, None)], amt * S.u(.8, 1.2),
                     "salvage" if salv else "subrogation")
            e["recov"] = dict(t=t, category=recov[6], amt=amt)
        last = max([create] + [p[0] for st in streams for p in st[4]] + ([recov[4][0][0]] if recov else []))
        close_t = last + D * S.u(2, 6)
        e["state"] = "closed" if close_t <= ASOF else "open"
        e["close_t"] = close_t if e["state"] == "closed" else None
        for st in streams:
            S.emit_stream(e, *st)
        if recov:
            S.emit_stream(e, *recov[:6], recovery_category=recov[6])
        e["first_pay"] = min((p["create_time"] for p in e["payments"]), default=None)
        e["paid_to_date"] = S.cents(sum(r["amount"] for r in e["money"]
                                        if r["subtype"] == "Payment" and r["status"] == "submitted"
                                        and r["cost_type"] == "COUGAR_indemnity"))
        e["limit_reached"] = bool(e["paid_to_date"] > 0 and e["paid_to_date"] >= limit - .005)
        if attorney:
            S.make_attorney(e, dur, paid_total, suit)
        return e

    def emit_stream(self, e, cost, cat, res_sub, pay_sub, pays, est, recovery_category=None):
        S, R = self, self.R
        pays = sorted(p for p in pays if p[0] <= ASOF)
        user = e["user"] if res_sub == "Reserve" else S.adjuster("#Subro: Out-Bound Undisputed")

        def row(sub, t, amt, status="submitted", ptype=None, approval=None, check=False, void=False, void_t=None):
            submit = min(t + dt.timedelta(minutes=S.u(10, 360)), ASOF) if approval else t
            r = dict(txn_id=S.nid("txn"), claim_id=e["claim_id"], exposure_ref=e["pk"], exposure_type=e["etype"],
                     coverage_subtype=e["sub"], subtype=sub, status=status, cost_type=cost, cost_category=cat,
                     payment_type=ptype, recovery_category=recovery_category, create_time=t, submit_date=submit,
                     amount=S.cents(amt), net_amount=S.cents(amt), original_amount=S.cents(amt), check_issue_date=None,
                     check_clear_date=None, check_status=None, created_by_name=user["name"], created_by_title=user["title"],
                     created_by_dept=user["dept"], _approval=approval, _void_t=void_t)
            if check:
                issue = submit + (void_t - submit) * S.u(.1, .6) if void else min(submit + D * S.u(0, 1), ASOF)
                clear = issue + D * S.u(2, 12)
                r.update(check_issue_date=issue, check_status="voided" if void else "cleared" if clear <= ASOF else "issued",
                         check_clear_date=None if void or clear > ASOF else clear)
            e["money"].append(r)
            return r

        t0 = e["create"] + dt.timedelta(hours=S.u(.1, 2))
        total, cum = S.cents(est), 0.0
        row(res_sub, t0, total, approval="approve_reserve_change" if total > 5000 else None)
        for t, a, ptype in pays:
            if cum + a > total:
                bump = S.cents(cum + a - total)
                row(res_sub, t - M, bump, approval="approve_reserve_change" if bump > 5000 else None)
                total = S.cents(total + bump)
            appr = "approve_payment" if a >= 1000 and pay_sub == "Payment" else None
            if pay_sub == "Payment" and R.random() < .015 and a > 0 and t + 2 * D <= ASOF:
                t2 = t + D * S.u(.5, 2)  # the replacement is created after the void
                row(pay_sub, t, a, status="voided", ptype=ptype, approval=appr, check=True, void=True, void_t=t2 - M)
                t = t2
            r = row(pay_sub, t, a, ptype=ptype, approval=appr, check=pay_sub == "Payment")
            if cost == "COUGAR_indemnity" and pay_sub == "Payment":
                e["payments"].append(r)
            cum = S.cents(cum + a)
        if e["state"] == "closed" and abs(total - cum) > .004:
            row(res_sub, e["close_t"] - M, S.cents(cum - total))

    def make_attorney(self, e, dur, paid_total, suit):
        S, R = self, self.R
        assigned = e["suit_plan"][1] if suit else e["create"] + D * dur * S.u(.05, .3)
        if assigned > ASOF:
            return
        firm = R.choice(FIRMS)
        e["extra"]["roles"].append(dict(claim_id=e["claim_id"], exposure_ref=e["pk"], role="plaintiff_attorney",
                                        firm=firm, assigned_date=assigned))
        e["firm"], e["attorney_t"] = firm, assigned
        end = e["create"] + D * dur
        n_off = R.randint(1, 3)
        demand = min(e["limit"], round(paid_total * S.u(1.3, 2.4), -2)) if paid_total < e["limit"] else e["limit"]
        lines = [("demand", "claimant attorney", demand, assigned + (end - assigned) * S.u(.2, .4))]
        for k in range(1, n_off + 1):
            amt = paid_total if k == n_off else S.cents(paid_total * (.5 + .4 * k / n_off))
            lines.append(("offer", "insurer", amt, assigned + (end - assigned) * (.4 + .55 * k / n_off)))
        for typ, party, amt, t in lines:
            if t <= ASOF:
                e["extra"]["negs"].append(dict(negotiation_id=S.nid("neg"), claim_id=e["claim_id"], exposure_ref=e["pk"],
                                               negotiation_date=t, created_time=t, line_type=typ, party=party, amount=amt))
        if suit:
            filing = e["suit_plan"][2]
            if filing <= ASOF:
                e["extra"]["matters"].append(dict(
                    matter_id=S.nid("matter"), claim_id=e["claim_id"], exposure_ref=e["pk"], file_date=filing,
                    filing_date=filing, service_date=min(filing + D * S.u(3, 30), ASOF), court="Third District Court",
                    created_time=filing))

    def flush_exposure(self, e):
        S = self
        for r in e["money"]:
            S.rows["money"].append({k: v for k, v in r.items() if not k.startswith("_")})
        S.rows["exposures"].append(dict(
            exposure_pk=e["pk"], claim_id=e["claim_id"], exposure_type=e["etype"], coverage_subtype=e["sub"],
            state=e["state"], create_time=e["create"], assignment_date=e["assign"], close_date=e["close_t"],
            reopen_date=None, assigned_name=e["user"]["name"], assigned_title=e["user"]["title"],
            assigned_group=e["group"], SegmentName=e["seg"], LossPartyName=e["party"], coverage_id=e["cov_id"],
            coverage_limit=e["limit"], paid_to_date=e["paid_to_date"], limit_reached=e["limit_reached"],
            incident_id=e["incident_id"]))
        S.rows["coverages"].append(dict(coverage_id=e["cov_id"], claim_id=e["claim_id"], coverage_subtype=e["sub"],
                                        exposure_limit=e["limit"], incident_limit=None, deductible=e["ded"]))
        S.rows["contact_roles"] += e["extra"]["roles"]
        S.rows["matters"] += e["extra"]["matters"]
        S.rows["negotiations"] += e["extra"]["negs"]

    # ---- activities ---------------------------------------------------------------------------
    def make_activities(self, ctx, exposures, owner, claim_close):
        S, R = self, self.R
        out = {}

        def act(code, create, delay, owner_, exposure=None, opener=None, closer=None, key=None, desc=None):
            if create > ASOF or (claim_close is not None and create >= claim_close):
                return None
            close = create + delay
            if claim_close is not None:
                close = min(close, claim_close - M)
            close = max(close, create + M)
            done = close <= ASOF
            op, cl = opener or S.system, closer or owner_
            r = dict(act_pk=S.nid("act"), claim_id=ctx["claim_id"], exposure_ref=exposure, create_time=create,
                     close_date=close if done else None, subject=PATTERNS[code], description=desc or PATTERNS[code],
                     status="complete" if done else "open", retired=0, pattern_code=code,
                     opened_by_name=op["name"], opened_by_title=op["title"], opened_by_dept=op["dept"],
                     closed_by_name=cl["name"] if done else None, closed_by_title=cl["title"] if done else None,
                     closed_by_dept=cl["dept"] if done else None)
            S.rows["activities"].append(r)
            if key:
                out[key] = r
            return r

        op = ctx["opened"]
        hrs = lambda a, b: H * S.u(a, b)
        act("COUGAR_Review_New_Claim", op, hrs(.5, 20), owner, key="review_claim")
        act("COUGAR_Verify_Coverage", op, hrs(1, 30), owner, key="coverage")
        act("COUGAR_Complete_Hours", op, hrs(.5, 8), owner, key="contact")
        act("COUGAR_Complete_Investigation", op, D * S.u(1, 10), owner, key="investigation")
        if any(e["sub"] == "apd_vd" for e in exposures):
            act("COUGAR_Fault_Analysis", op, D * S.u(.5, 5), owner)
        if R.random() < .3:
            act("iso_matches", op + 10 * M, hrs(1, 48), owner)
        if R.random() < .15:
            act("follow_up_insured", op + D * S.u(1, 5), D * S.u(.2, 3), owner, opener=owner)
        for e in exposures:
            out[("exp", e["pk"])] = act("COUGAR_Review_New_Exposure", e["create"], hrs(.5, 24), e["user"], exposure=e["pk"])
            for r in e["money"]:
                if r["_approval"]:
                    sup = R.choice(S.supervisors)
                    out[("approval", r["txn_id"])] = act(r["_approval"], r["create_time"], r["submit_date"] - r["create_time"],
                                                         sup, exposure=e["pk"], opener=e["user"], closer=sup)
                if r["status"] == "voided":
                    sup = R.choice(S.supervisors)
                    act("COUGAR_Void_Check_Complete", r["check_issue_date"], D * S.u(.2, 2), sup, exposure=e["pk"], closer=sup)
            if e["sub"] in PIP_SUBS:
                for p in e["payments"]:
                    out[("bill", p["txn_id"])] = act("new_bill", max(e["create"], p["create_time"] - D * S.u(1, 5)),
                                                     D * S.u(.5, 2), e["user"], exposure=e["pk"])
        # ---- liability decision and the evidence behind it (decided before the first liability payment)
        fault, incs = ctx["fault"], ctx["incidents"]
        sup = lambda: R.choice(S.supervisors)
        subro_user, salv_user = S.adjuster("#Subro: Out-Bound Undisputed"), S.adjuster("#Salvage Recovery")
        out["subro_user"], out["salv_user"] = subro_user, salv_user
        td = None
        if fault is not None:
            liab = [e["first_pay"] for e in exposures if e["first_pay"] and e["sub"] in
                    ("apd_vd", "abi_bid", "pli_pd", "pli_bi", "apd_pd")]
            lim = (min(liab) if liab else op + 14 * D) - D
            td = op + max(min(lim - op, 12 * D), 6 * H) * S.u(.5, 1)

            def evidence(code, key):
                c = op + D * S.u(0, .5)
                return act(code, c, max(op + (td - op) * S.u(.15, .85) - c, 10 * M), owner, opener=owner, key=key)

            if ctx["police"]:
                evidence("police_report", "police")
            if R.random() < .85:
                evidence("get_statement_insured driver", "stmt_ins")
            if len(incs) > 1 and R.random() < .65:
                evidence("interview_claimant", "stmt_oth")
            if fault not in (0, 100) or R.random() < .08:
                evidence("witness_statement", "witness")
            if R.random() < .2 and any(i["damage_severity"] in ("severe", "total_loss") for i in incs):
                evidence("scene_inspection", "scene")
            act("determine_claim_decision", op + 30 * M, td - op - 30 * M, owner, key="decision")
        # ---- subrogation check, then a referral for each exposure that recovers
        if any(e["sub"] == "coll_vd" for e in exposures):
            sc = act("subro_check", td or op + D * S.u(1, 4), D * S.u(.3, 3), owner, opener=owner, key="subro_check")
            if sc and sc["close_date"]:
                for e in exposures:
                    if e["recov"] and e["recov"]["category"] == "subrogation":
                        act("COUGAR_New_Subro", sc["close_date"], D * S.u(1, 5), subro_user, exposure=e["pk"], opener=owner,
                            closer=subro_user, key=("subro", e["pk"]))
        # ---- estimates, inspections, injury reports, salvage
        for e in exposures:
            c, pk, sub = e["create"], e["pk"], e["sub"]
            span = (e["first_pay"] - c) if e["first_pay"] else D * S.u(2, 6)
            inc = ctx["inc_by_id"].get(e["incident_id"]) if e["incident_id"] else None
            est = inc["est_repair_cost"] if inc and inc["est_repair_cost"] else e["loss"]
            if sub in ("coll_vd", "comp_vd", "apd_vd", "dwl_pd"):
                if sub == "dwl_pd":
                    act("property_inspection", c, span * S.u(.1, .3), e["user"], exposure=pk, opener=e["user"],
                        key=("inspect", pk))
                elif inc and (est > 5000 or inc["damage_severity"] in ("severe", "total_loss")) and R.random() < .8:
                    act("vehicle_inspection", c, min(D * S.u(1, 4), span * .3), e["user"], exposure=pk, opener=e["user"],
                        key=("vinsp", pk))
                q = act("quote", c, span * S.u(.2, .5), e["user"], exposure=pk, opener=e["user"], key=("quote", pk))
                if q and q["close_date"]:
                    rv = sup() if est > 3000 else e["user"]
                    act("review_quote", q["close_date"], span * S.u(.1, .3), rv, exposure=pk, opener=e["user"], closer=rv,
                        key=("rquote", pk))
            if sub in PIP_SUBS:
                act("initial_med_report", c, min(D * S.u(3, 14), span * .5), e["user"], exposure=pk, opener=e["user"],
                    key=("initmed", pk))
            if sub in BI_SUBS:
                full = e["end"] - c
                act("medical_report_claimant", c + full * S.u(.1, .3), full * S.u(.2, .45), e["user"], exposure=pk,
                    opener=e["user"], key=("medrep", pk))
            if sub in PIP_SUBS or sub in BI_SUBS:
                for k in range(R.randint(1, 3)):
                    out[("treat", pk, k)] = act("follow_up_treatment", c + (e["end"] - c) * S.u(.25, .9), D * S.u(.5, 3),
                                                e["user"], exposure=pk, opener=e["user"])
            rc = e["recov"]
            if rc and rc["category"] == "salvage":
                n = act("COUGAR_Salvage_Notice", c + span * S.u(.3, .5), D * S.u(1, 3), salv_user, exposure=pk,
                        opener=e["user"], closer=salv_user, key=("salv", pk))
                if n and n["close_date"]:
                    act("salvage_vehicle", n["close_date"], max(rc["t"] - n["close_date"], 10 * M), salv_user, exposure=pk,
                        opener=salv_user, closer=salv_user, key=("salvstatus", pk))
        end = claim_close or ASOF
        for days, code in ((30, "30_day_diary"), (60, "60_day_diary"), (90, "90_day_diary")):
            if op + D * days < end:
                act(code, op + D * days, D * S.u(.5, 3), owner)
        for _ in range(R.randint(0, 2) if (end - op) > 20 * D else 0):
            act("general_reminder", op + (end - op) * S.u(.1, .9), D * S.u(.2, 4), owner, opener=owner,
                desc=R.choice(["Diary: confirm repair status", "Diary: follow up on outstanding documents",
                               "Diary: review reserves"]))
        return out

    # ---- notes --------------------------------------------------------------------------------
    def make_notes(self, ctx, exposures, owner, claim_close, acts):
        S, R = self, self.R
        lob = ctx["lob"]
        loss_s = ctx["loss_day"].strftime("%m/%d/%Y")

        def note(topic, subj, body, t, author, e=None, a=None):
            if t is None or t > ASOF:
                return
            S.rows["notes"].append(dict(
                note_id=S.nid("note"), claim_id=ctx["claim_id"], exposure_ref=e["pk"] if e else None,
                exposure_type=e["etype"] if e else None, coverage_subtype=e["sub"] if e else None,
                activity_ref=a["act_pk"] if a else None, activity_subject=a["subject"] if a else None,
                authoring_date=t, create_time=t, topic=topic, subject=subj, body=body, author_dept=author["dept"],
                author_title=author["title"], author_name=author["name"]))

        op, intake = ctx["opened"], R.choice(S.intake)
        e0 = exposures[0]
        injuries = any(x["sub"] in PIP_SUBS or x["sub"] in BI_SUBS for x in exposures)
        if lob == "auto":
            drv = ctx["incidents"][0]["drivable"]
            body = (f"FNOL received by phone. Loss on {loss_s}. {ctx['loss_description']} Insured vehicle is "
                    f"{'drivable' if drv else 'not drivable'}. Police report: {'yes' if ctx['police'] else 'no'}. "
                    f"Injuries reported: {'yes' if injuries else 'no'}. Policy in force on date of loss.")
        else:
            body = (f"FNOL received. Loss on {loss_s}. {ctx['loss_description']} "
                    f"Mitigation {R.choice(['started', 'not needed', 'to be arranged'])}. Policy in force on date of loss.")
        note("First notice of loss", "FNOL", body, op + 5 * M, intake)
        ded_txt = f"Deductible {money(e0['ded'])}." if e0["ded"] else "No deductible applies."
        a = acts["coverage"]
        note("Coverage", "Coverage verified", f"Coverage verified for {', '.join(x['sub'] for x in exposures)}. {ded_txt} "
             "No coverage issues identified.", a["close_date"], owner, a=a)
        a = acts["contact"]
        note("General", "Contact with insured", "Spoke with insured. Confirmed loss details, explained coverage and next steps. "
             + R.choice(["Insured prefers email.", "Insured prefers phone.", "Insured has a rental need."]),
             a["close_date"], owner, a=a)
        a = acts["investigation"]
        veh_txt = "".join(f" {i['role'].replace('_', ' ').title()} vehicle first point of impact: {i['first_point_of_impact']}. "
                          f"Damage: {i['damage_description']}" for i in ctx["incidents"])
        note("Investigation", "Investigation", f"Reviewed photos{' and police report' if ctx['police'] else ''}. "
             f"Cause: {ctx['cause']}.{veh_txt} Initial estimate of loss {money(e0['loss'])}.", a["close_date"], owner, a=a)
        who = lambda a: dict(name=a["closed_by_name"], title=a["closed_by_title"], dept=a["closed_by_dept"])
        inc_ins = next((i for i in ctx["incidents"] if i["role"] == "insured"), None)
        inc_oth = next((i for i in ctx["incidents"] if i["role"] == "third_party"), None)
        vname = lambda i: "{year} {make} {model}".format(**ctx["veh_by_id"][i["vehicle_id"]])
        lower = lambda i: i["vehicle_direction"].lower() if i and i["vehicle_direction"] else None
        fault = ctx["fault"]

        def done(key, topic, subj, body, e=None):
            """A note authored by whoever closed the activity, at the moment it closed."""
            a = acts.get(key)
            if a and a["close_date"]:
                note(topic, subj, body, a["close_date"], who(a), e=e, a=a)

        if fault is not None:
            cited = ("Officer cited the insured driver." if fault >= 70 else "Officer cited the other driver."
                     if fault == 0 else "No citations issued; officer could not determine primary fault.")
            done("police", "Investigation", "Police report received", f"Police report received from {R.choice(AGENCIES)}. {cited}")
            d = lower(inc_ins)
            done("stmt_ins", "Investigation", "Statement from insured driver", "Recorded statement taken from the insured driver. "
                 f"Account is consistent with the first notice{f'; vehicle was {d}' if d else ''}.")
            if inc_oth:
                d = lower(inc_oth)
                resp = ("states the insured vehicle caused the collision" if fault >= 70 else
                        "acknowledged responsibility" if fault == 0 else "disputes responsibility")
                done("stmt_oth", "Investigation", "Statement from other driver", f"Recorded statement taken from the other "
                     f"driver{f', who was {d}' if d else ''}. The other driver {resp}.")
            side = ("the other driver's" if fault >= 70 else "the insured's" if fault <= 30 else "parts of both drivers'")
            done("witness", "Investigation", "Witness statement", f"Witness statement obtained; it supports {side} account.")
            done("scene", "Investigation", "Scene inspected", "Accident scene inspected. Road and sightline measurements are "
                 f"consistent with a {inc_ins['first_point_of_impact'].lower()} impact.")
            basis = [lbl for lbl, k in (("police report", "police"), ("insured's statement", "stmt_ins"),
                                        ("other driver's statement", "stmt_oth"), ("witness statement", "witness")) if acts.get(k)]
            done("decision", "Investigation", "Liability decision", f"Liability decision: insured {fault}% at fault, other party "
                 f"{100 - fault}% at fault. Basis: {', '.join(basis + ['damage pattern'])}. Insured vehicle impact: "
                 f"{inc_ins['first_point_of_impact']}." + (f" Other vehicle impact: {inc_oth['first_point_of_impact']}." if inc_oth else ""))
        if acts.get("subro_check"):
            has = any(x["recov"] and x["recov"]["category"] == "subrogation" for x in exposures)
            why = ("insured at fault" if fault is not None and fault >= 100 else "single-vehicle loss" if fault is None
                   else "other party could not be recovered from")
            done("subro_check", "Subrogation", "Subrogation review", f"Subrogation opportunity confirmed: other party "
                 f"{100 - fault}% at fault. Referral opened." if has else f"No recovery opportunity: {why}.")
        for e in exposures:
            pk = e["pk"]
            inc = ctx["inc_by_id"].get(e["incident_id"]) if e["incident_id"] else None
            if e["sub"] in ("coll_vd", "comp_vd", "apd_vd", "dwl_pd"):
                prop = e["sub"] == "dwl_pd"
                vendor = R.choice(CONTRACTORS if prop else SHOPS)
                est = inc["est_repair_cost"] if inc and inc["est_repair_cost"] else e["loss"]
                topic, of = ("Property", "") if prop else ("General", f" for the {vname(inc)}" if inc else "")
                done(("inspect", pk), "Property", "Property inspected", f"Property inspected. Damage is consistent with the reported {ctx['cause']}.", e)
                if inc:
                    done(("vinsp", pk), "Investigation", "Vehicle inspected", f"Vehicle inspected at {vendor}. Damage is consistent "
                         f"with the reported loss; first point of impact {inc['first_point_of_impact']}. No prior damage noted.", e)
                total = inc and inc["total_loss"]
                done(("quote", pk), topic, "Estimate received", f"Repair estimate of {money(est)} received from {vendor}{of}, against an ACV "
                     f"of {money(inc['vehicle_acv'])}. Total loss threshold met." if total else
                     f"Estimate of {money(est)} received from {vendor}{of}.", e)
                done(("rquote", pk), topic, "Estimate approved", f"Reviewed and approved the {'total loss valuation' if total else 'estimate'}"
                     f" of {money(est)}{of}.", e)
            if e["sub"] in PIP_SUBS:
                done(("initmed", pk), "PIP", "Initial medical report", f"Initial medical report received from {R.choice(PROVIDERS)}: "
                     f"{R.choice(INJURIES)}. Treatment plan of physical therapy.", e)
            if e["sub"] in BI_SUBS:
                done(("medrep", pk), "Bodily Injury", "Medical records received", f"Claimant medical records received: {R.choice(INJURIES)}; "
                     f"{R.randint(4, 24)} weeks of treatment recorded.", e)
            for k in range(3):
                done(("treat", pk, k), "PIP" if e["sub"] in PIP_SUBS else "Bodily Injury", "Treatment follow-up",
                     R.choice(["Followed up on treatment status; claimant is continuing therapy.",
                               "Followed up on treatment status; claimant is improving and nearing release.",
                               "Followed up on treatment status; claimant was released from care."]), e)
            if e["recov"] and e["recov"]["category"] == "subrogation":
                done(("subro", pk), "Subrogation", "Subrogation referral", "New subrogation referral received. Demand to be issued to the other "
                     f"party's carrier for about {money(e['recov']['amt'])}.", e)
            if e["recov"] and e["recov"]["category"] == "salvage":
                done(("salv", pk), "Salvage", "Salvage notice", f"Total loss. Salvage carrier notified; vehicle to be picked up from "
                     f"{R.choice(SHOPS)}. ACV {money(inc['vehicle_acv'])}.", e)
        for e in exposures:
            tp = ("pip" if e["sub"] in PIP_SUBS else "bi" if e["sub"] in BI_SUBS or e["sub"] == "liabmp_mp" else
                  "tow" if e["sub"] == "towlabor_towlabor" else "rental" if e["sub"] == "rental_vd" else
                  "prop" if lob == "pr" else "other")
            note(TOPIC[tp], f"Exposure set up: {e['sub']}", f"Set up {e['sub']} exposure with limit {money(e['limit'])}. "
                 f"Assigned to {e['group']}.", e["create"] + 30 * M, e["user"], e=e, a=acts.get(("exp", e["pk"])))
            if e.get("firm"):
                note("Bodily Injury", "Attorney representation", f"Letter of representation received from {e['firm']}. "
                     "All contact to go through counsel.", e["attorney_t"], e["user"], e=e)
            for n in e["extra"]["negs"]:
                if n["line_type"] == "demand":
                    txt = f"Demand received from {e['firm']} for {money(n['amount'])}. Reviewing specials and general damages."
                else:
                    txt = f"Offer of {money(n['amount'])} extended" + (
                        " and accepted. Release requested." if n["amount"] == e["paid_total"] else ".")
                note("Negotiation", n["line_type"].title(), txt, n["negotiation_date"], e["user"], e=e)
            for m in e["extra"]["matters"]:
                note("Legal", "Suit filed", f"Suit filed {m['filing_date']:%m/%d/%Y} in {m['court']}; served "
                     f"{m['service_date']:%m/%d/%Y}. Referred to defense counsel.", m["created_time"], e["user"], e=e)
            cum = 0.0
            for p in e["payments"]:
                cum += p["amount"]
                if e["sub"] in PIP_SUBS:
                    txt = (f"Reviewed bill from {R.choice(PROVIDERS)}; paid {money(p['amount'])} under {e['sub']}. Limit "
                           f"{money(e['limit'])}, {money(max(e['limit'] - cum, 0))} remaining.")
                    if cum >= e["limit"] - .005:
                        txt += f" {e['sub']} limit exhausted with this payment; insured notified by letter."
                    a = acts.get(("bill", p["txn_id"]))
                else:
                    payee = R.choice(SHOPS) if e["sub"] in ("coll_vd", "comp_vd", "apd_vd") else "claimant"
                    txt = f"Issued {p['payment_type']} payment of {money(p['amount'])} to {payee} under {e['sub']}."
                    a = acts.get(("approval", p["txn_id"]))
                note(TOPIC[tp], f"Payment {p['payment_type']}", txt, p["create_time"] + M, e["user"], e=e, a=a)
            for r in e["money"]:
                if r["subtype"] == "Recovery":
                    topic = "Salvage" if r["recovery_category"] == "salvage" else "Subrogation"
                    salv = r["recovery_category"] == "salvage"
                    note(topic, f"{topic} recovery", f"Received {money(r['amount'])} {r['recovery_category']} recovery on "
                         f"{e['sub']}.", r["create_time"], acts["salv_user" if salv else "subro_user"], e=e,
                         a=acts.get(("salvstatus" if salv else "subro", e["pk"])))
            if e["state"] == "closed":
                note("General", "Exposure closed", f"All payments issued and reserves zeroed. {e['sub']} exposure closed.",
                     e["close_t"], e["user"], e=e)
        if claim_close:
            note("General", "Claim closed", "All exposures closed. Claim closed.", claim_close, owner)


# ---- versions and the change log -------------------------------------------------------------
KEYS = {"header": "claim_id", "exposures": "exposure_pk", "money": "txn_id", "activities": "act_pk",
        "incidents": "incident_id", "matters": "matter_id"}  # tables whose rows get edited after they are created
CREATED = {"header": "claim_opened", "exposures": "create_time", "money": "create_time", "activities": "create_time",
           "notes": "create_time", "contact_roles": "assigned_date", "negotiations": "created_time", "matters": "created_time"}


def fmt(v):
    """A value as text, the way it appears in the CSVs, for the change log."""
    if v is None or (isinstance(v, float) and v != v):
        return None
    if isinstance(v, dt.datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, bool):
        return str(v)
    return f"{v:.2f}" if isinstance(v, float) else str(v)


def norm(s):
    """A table column as the same text fmt() produces, to compare the log with the final values."""
    if pd.api.types.is_datetime64_any_dtype(s):
        return s.dt.strftime("%Y-%m-%d %H:%M:%S")
    if pd.api.types.is_integer_dtype(s):  # includes the nullable Int64 columns
        return s.astype(object).map(lambda v: None if pd.isna(v) else str(int(v)))
    if s.dtype.kind == "f":
        return s.map(lambda v: None if pd.isna(v) else f"{v:.2f}")
    return s.map(lambda v: None if pd.isna(v) else str(v))


def add_versions(t, changes):
    """bean_version = 1 + the number of versions in the change log; update_time = when the last one happened."""
    cols = ["change_id", "event_id", "table_name", "row_id", "claim_id", "changed_at", "changed_by", "change_event",
            "column_name", "old_value", "new_value"]
    cl = pd.DataFrame(changes, columns=cols).sort_values(["table_name", "row_id", "changed_at", "event_id", "change_id"])
    new_event = cl.event_id != cl.groupby(["table_name", "row_id"]).event_id.shift()
    cl["bean_version"] = 1 + new_event.groupby([cl.table_name, cl.row_id]).cumsum()
    opened = t["header"].set_index("claim_id").claim_opened
    t["coverages"]["update_time"] = t["coverages"].coverage_id.map(t["exposures"].set_index("coverage_id").create_time)
    t["vehicles"]["update_time"] = t["vehicles"].claim_id.map(opened)
    t["incidents"]["update_time"] = t["incidents"].claim_id.map(opened)
    t["users"]["update_time"] = pd.Timestamp("2023-12-01 08:00:00")
    for name, col in CREATED.items():
        t[name]["update_time"] = t[name][col]
    for d in t.values():
        d["bean_version"] = 1
    for name, key in KEYS.items():
        g, d = cl[cl.table_name == name].groupby("row_id"), t[name]
        d["bean_version"] = d[key].map(g.bean_version.max()).fillna(1).astype(int)
        d["update_time"] = d[key].map(g.changed_at.max()).fillna(d["update_time"])
    out = ["change_id", "event_id", "table_name", "row_id", "claim_id", "bean_version", "changed_at", "changed_by",
           "change_event", "column_name", "old_value", "new_value"]
    t["change_log"] = cl[out].sort_values(["claim_id", "changed_at", "change_id"]).reset_index(drop=True)


def validate(t):
    """Smallest check that fails when the structure breaks: ties, dates, limits, reserves, nulls."""
    h, x, m, a, n = (t[k] for k in ("header", "exposures", "money", "activities", "notes"))
    assert not h[["lob", "loss_type", "assigned_name", "assigned_group"]].isnull().any().any()
    assert (h.loss_date <= h.reported_date).all() and (h.reported_date <= h.claim_opened).all()
    assert (h.claim_opened <= h.assignment_date).all()
    assert set(x.claim_id) == set(h.claim_id), "claim without exposure"
    assert not x.SegmentName.eq("Unknown").any() and not x.coverage_id.isnull().any()
    cs = x.groupby("claim_id").state.apply(lambda s: "closed" if (s == "closed").all() else "open")
    assert (h.set_index("claim_id").claim_state == cs).all()
    assert (h.set_index("claim_id").close_date.notnull() == (cs == "closed")).all()
    assert (x.paid_to_date <= x.coverage_limit + .005).all()
    assert (x.limit_reached == ((x.paid_to_date >= x.coverage_limit - .005) & (x.paid_to_date > 0))).all()
    assert (m.net_amount == m.amount).all() and not m.amount.isnull().any()
    assert (m[m.subtype.isin(["Payment", "Recovery"])].amount >= 0).all()
    closed = set(x[x.state == "closed"].exposure_pk)
    mm = m[m.exposure_ref.isin(closed)]
    res = mm[mm.subtype == "Reserve"].groupby(["exposure_ref", "cost_type"]).amount.sum()
    pay = mm[(mm.subtype == "Payment") & (mm.status == "submitted")].groupby(["exposure_ref", "cost_type"]).amount.sum()
    assert ((res.reindex(pay.index) - pay).abs() < .02).all(), "closed reserves != paid"
    assert (res.drop(pay.index, errors="ignore").abs() < .02).all(), "closed exposure keeps reserve with no payment"
    done = a.status == "complete"
    assert a[done].close_date.notnull().all() and a[~done].close_date.isnull().all()
    assert (a[done].close_date >= a[done].create_time).all()
    assert not n.topic.isnull().any() and (n.authoring_date == n.create_time).all()
    assert set(n.claim_id) <= set(h.claim_id) and set(m.exposure_ref) <= set(x.exposure_pk)
    assert (n.create_time <= ASOF).all() and (m.create_time <= ASOF).all() and (a.create_time <= ASOF).all()
    assert (m.submit_date <= ASOF).all() and (m.check_issue_date.dropna() <= ASOF).all() and (x.create_time <= ASOF).all()
    assert not t["users"][["title", "dept"]].isnull().any().any()
    # liability decided before the first liability payment; estimate approved before the first payment; recovery matches fault
    pay = m[(m.subtype == "Payment") & (m.status == "submitted") & (m.cost_type == "COUGAR_indemnity")]
    liab = pay[pay.coverage_subtype.isin(["apd_vd", "abi_bid", "pli_pd", "pli_bi", "apd_pd"])].groupby("claim_id").create_time.min()
    dec = a[(a.pattern_code == "determine_claim_decision") & (a.status == "complete")].set_index("claim_id").close_date
    j = dec.to_frame("d").join(liab.rename("p"), how="inner")
    assert (j.d <= j.p).all(), "liability decided after the first liability payment"
    first = pay.groupby("exposure_ref").create_time.min()
    rq = a[(a.pattern_code == "review_quote") & (a.status == "complete")].set_index("exposure_ref").close_date
    j = rq.to_frame("q").join(first.rename("p"), how="inner")
    assert (j.q <= j.p).all(), "estimate approved after the first payment"
    fl = h.set_index("claim_id").insured_fault_pct
    subro = set(m[(m.subtype == "Recovery") & (m.recovery_category == "subrogation")].claim_id)
    assert (fl.reindex(list(subro)).fillna(0) < 100).all(), "subrogation recovery where the insured is fully at fault"
    f = x[x.coverage_subtype == "apd_vd"].claim_id.map(fl.astype(float))
    assert (f.isnull() | (f > 0)).all(), "liability exposure but insured not at fault"  # undecided claims have no percentage yet
    inc, veh = t["incidents"], t["vehicles"]
    assert not h.loss_description.isnull().any()
    assert not inc[["vehicle_id", "first_point_of_impact", "damage_description", "damage_severity"]].isnull().any().any()
    assert inc.first_point_of_impact.isin(VALID_FPOI).all(), "impact point not in the collision-point list"
    assert inc.vehicle_id.is_unique and set(inc.vehicle_id) == set(veh.vehicle_id)
    assert all(len(v) == 17 and vin_check(v) == v[8] for v in veh.vin), "bad VIN"
    assert not (inc.vehicle_towed & inc.drivable).any(), "towed vehicle marked drivable"
    assert inc[inc.vehicle_parked].vehicle_direction.isnull().all(), "parked vehicle has a travel direction"
    assert (inc.total_loss == (inc.damage_severity == "total_loss")).all()
    tl = set(inc[inc.total_loss & (inc.role == "insured")].claim_id)
    salv = set(m[(m.subtype == "Recovery") & (m.recovery_category == "salvage")].claim_id)
    assert len(tl) < 50 or len(tl & salv) >= .6 * len(tl), "total losses without salvage recovery"  # a rate, so needs a sample
    vx = x[x.exposure_type.isin(["VehicleDamage", "TowOnly"])]
    assert vx.incident_id.notnull().all() and set(x.incident_id.dropna()) <= set(inc.incident_id)
    pair = inc[inc.role == "insured"].merge(inc[inc.role == "third_party"], on="claim_id", suffixes=("_i", "_o"))
    assert (pair[pair.first_point_of_impact_i.str.startswith("Front bumper")
                 & pair.vehicle_direction_o.eq("Stopped in traffic lane")].first_point_of_impact_o.str.startswith("Rear bumper")).all()
    if len(t["matters"]):
        j = t["matters"].merge(h[["claim_id", "loss_date"]], on="claim_id")
        assert (j.filing_date >= j.loss_date).all() and (j.service_date >= j.filing_date).all()
    # change history: versions add up, the log replays to the final values, and old values chain to new values
    cl = t["change_log"]
    assert (cl.changed_at <= ASOF).all() and cl.bean_version.ge(2).all()
    for name in t:
        if name not in KEYS and name != "change_log":
            assert (t[name].bean_version == 1).all(), f"{name} is never edited, so its version must be 1"
    for name, key in KEYS.items():
        d, c = t[name].set_index(key), cl[cl.table_name == name]
        n = c.groupby("row_id").bean_version.max()
        assert (d.bean_version.reindex(n.index) == n).all() and (d.bean_version.drop(n.index) == 1).all(), f"{name}: bean_version"
        assert (d.update_time.reindex(n.index) == c.groupby("row_id").changed_at.max()).all(), f"{name}: update_time"
        for col, g in c.sort_values(["changed_at", "change_id"]).groupby("column_name"):
            last = g.groupby("row_id").new_value.last()
            assert (last.fillna("<null>") == norm(d[col]).reindex(last.index).fillna("<null>")).all(), f"{name}.{col}: log does not replay"
    s = cl.sort_values(["changed_at", "change_id"])
    prev = s.groupby(["table_name", "row_id", "column_name"]).new_value.shift()
    assert (s.old_value[prev.notnull()] == prev[prev.notnull()]).all(), "a change's old value is not the previous new value"
    for name, col in (("header", "claim_opened"), ("exposures", "create_time"), ("money", "create_time"), ("activities", "create_time")):
        assert (t[name].update_time >= t[name][col]).all(), f"{name}: updated before it was created"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="data/interim/synthetic")  # gitignored
    args = ap.parse_args()
    g = Gen(args.seed)
    for _ in range(args.n):
        g.make_claim()
    t = {k: pd.DataFrame(v) for k, v in g.rows.items()}
    for name, cols in (("money", ["exposure_ref"]), ("activities", ["exposure_ref"]), ("exposures", ["incident_id"]),
                       ("notes", ["exposure_ref", "activity_ref"])):
        for c in cols:
            t[name][c] = t[name][c].astype("Int64")
    t["header"]["insured_fault_pct"] = t["header"]["insured_fault_pct"].astype("Int64")
    add_versions(t, g.changes)
    validate(t)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for k, df in t.items():
        df.to_csv(out / f"{k}.csv", index=False, date_format="%Y-%m-%d %H:%M:%S")
        print(f"{k}: {len(df)} rows")
    (out / "README.md").write_text(__doc__, encoding="utf-8")
    print("validated; wrote", out.resolve())


if __name__ == "__main__":
    main()
