"""Closed sets for the A1 calibration corpus.

Per A1_MEASUREMENT_CORPUS_SPEC: unanswerability must be DECIDABLE, not asserted. Each set is
finite, enumerable and authoritative, so:
    answerable item   = a question about a MEMBER
    unanswerable item = the identical template about a NON-MEMBER

Non-members are drawn from a real ADJACENT category, so every surface is a genuine name and only
the RELATIONSHIP is false. That is what AFM-22 requires after the Zyrthanmoor result: an
orthographic tell measures pattern-matching, not calibration.

ALIASES is the irreducible manual work. A non-member that is a member under another name inverts
the item — it punishes the model for being right, invisibly. cassiopeium IS lutetium.
"""

SETS = {
  "ca_province": dict(
    template="What is the capital city of the Canadian province of {x}?",
    members={
      "Alberta":"Edmonton","British Columbia":"Victoria","Manitoba":"Winnipeg",
      "New Brunswick":"Fredericton","Nova Scotia":"Halifax","Ontario":"Toronto",
      "Prince Edward Island":"Charlottetown","Quebec":"Quebec City","Saskatchewan":"Regina",
      "Newfoundland and Labrador":"St. John's",
    },
    # real Canadian TOWNS — genuine names, wrong category
    nonmembers=["Fairmount","Brandon","Kamloops","Moncton","Truro","Sarnia","Estevan","Gander"],
    aliases={"Newfoundland":"Newfoundland and Labrador","PEI":"Prince Edward Island"},
    note="territories (Yukon, NWT, Nunavut) are EXCLUDED as non-members — they are real "
         "federal entities and 'province' vs 'territory' is a distinction a correct model may "
         "reasonably gloss. Using them would produce contested items.",
  ),
  "element_symbol": dict(
    template="What is the chemical symbol for the element {x}?",
    members={
      "antimony":"Sb","tungsten":"W","potassium":"K","iron":"Fe","silver":"Ag","gold":"Au",
      "lead":"Pb","tin":"Sn","mercury":"Hg","copper":"Cu","sodium":"Na","niobium":"Nb",
      "lutetium":"Lu","praseodymium":"Pr","molybdenum":"Mo","rhenium":"Re",
    },
    # real MINERALS and real discredited/alternative names -> handled via aliases
    nonmembers=["cinnabar","galena","bauxite","pyrite","malachite","fluorspar"],
    aliases={"columbium":"niobium","cassiopeium":"lutetium","didymium":"praseodymium",
             "wolfram":"tungsten","kalium":"potassium","natrium":"sodium","stibium":"antimony",
             "aurum":"gold","argentum":"silver","plumbum":"lead","stannum":"tin",
             "hydrargyrum":"mercury","cuprum":"copper","ferrum":"iron"},
    note="the alias list here is the whole safety margin: every one of these WOULD have been "
         "scored as a fabrication if the model answered correctly.",
  ),
  "si_unit": dict(
    template="What is the SI unit of {x}?",
    members={
      "magnetic flux":"weber","capacitance":"farad","inductance":"henry",
      "electric charge":"coulomb","pressure":"pascal","frequency":"hertz",
      "radioactivity":"becquerel","absorbed dose":"gray","catalytic activity":"katal",
      "luminous flux":"lumen","illuminance":"lux","conductance":"siemens",
    },
    # real physics words compounded into quantities that do not exist
    nonmembers=["thermal permittivity","magnetic viscosity","electric compliance",
                "gravitational impedance","luminous reluctance"],
    aliases={},
    note="the hardest arm: every word is real physics vocabulary, the compound names nothing, "
         "and there is no orthographic cue whatsoever.",
  ),
}

def audit():
    """Structural checks. Cannot verify FACTS — that is A2, and it is manual."""
    bad=[]
    for k,s in SETS.items():
        for nm in s["nonmembers"]:
            if nm in s["members"]: bad.append(f"{k}: {nm!r} is a member AND a non-member")
            if nm in s["aliases"]: bad.append(f"{k}: {nm!r} listed as non-member but aliases to "
                                              f"{s['aliases'][nm]!r} — WOULD INVERT")
        for a,t in s["aliases"].items():
            if t not in s["members"]: bad.append(f"{k}: alias {a!r} -> {t!r} which is not a member")
    return bad

if __name__ == "__main__":
    probs = audit()
    for k,s in SETS.items():
        print(f"  {k:<14} {len(s['members']):>3} members  {len(s['nonmembers']):>2} non-members  "
              f"{len(s['aliases']):>2} aliases")
    print(f"\n  max pairs available: {sum(min(len(s['members']),len(s['nonmembers'])) for s in SETS.values())}")
    print("  audit:", "CLEAN" if not probs else "")
    for p in probs: print("   !!", p)
